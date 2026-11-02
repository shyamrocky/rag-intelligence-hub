"""Bounded Streamlit AppTest + M5 reader coexistence; no search, model, or mutation."""

import argparse
import ctypes
import json
import os
import resource
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

from check_selection import PROFILE, PROFILE_SHA256, environment, load_profile


def resident_bytes(pid=None):
    """Current self RSS, not high-water RSS. Only the measured process is inspected."""
    if sys.platform != "darwin":
        raise ValueError("resource_probe_qualified_for_macos_only")
    library = ctypes.CDLL("/usr/lib/libproc.dylib")
    buffer = ctypes.create_string_buffer(96)  # proc_taskinfo, PROC_PIDTASKINFO=4
    if library.proc_pidinfo(pid or os.getpid(), 4, 0, buffer, 96) != 96:
        raise OSError("self_rss_unavailable")
    return int((ctypes.c_uint64 * 2).from_buffer_copy(buffer.raw[:16])[1])


def process_tree_rss():
    """Sample this process and extant descendants, including transient UI inspector workers."""
    library = ctypes.CDLL("/usr/lib/libproc.dylib")
    pending, seen, result, unavailable = [os.getpid()], set(), {}, []
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        try:
            result[str(pid)] = resident_bytes(pid)
        except OSError:
            unavailable.append(pid)  # A process may exit between enumeration and inspection.
        children = (ctypes.c_int * 1024)()
        count = library.proc_listchildpids(pid, children, ctypes.sizeof(children))
        if count < 0 or count >= len(children):
            raise OSError("child_process_inventory_unavailable_or_overflow")
        pending.extend(children[:count])
    return {"processes": result, "tree_rss": sum(result.values()),
            "unavailable_or_exited_children": unavailable}


class Samples:
    def __init__(self, path):
        self.path, self.stop = path, threading.Event()
        self.error = None

    def __enter__(self):
        def collect():
            try:
                with self.path.open("x") as stream:
                    while not self.stop.is_set():
                        stream.write(json.dumps({"t": time.time(), "pid": os.getpid(),
                                                 "rss": resident_bytes(),
                                                 **process_tree_rss()}) + "\n")
                        stream.flush()
                        self.stop.wait(0.1)
            except (OSError, ValueError) as exc:
                self.error = repr(exc)
        self.thread = threading.Thread(target=collect, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=3)
        if self.error:
            raise RuntimeError(self.error)


def statistics_for(values):
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "p50": None, "max": None}
    return {"n": len(ordered), "p50": statistics.median(ordered), "max": max(ordered)}


def combined_samples(groups):
    """Timestamp-aligned RSS sum; shared pages can be double-counted, not physical footprint."""
    ticks = sorted((row["t"], i, row["rss"]) for i, rows in enumerate(groups) for row in rows)
    latest, combined = {}, []
    for tick, i, rss in ticks:
        latest[i] = (tick, rss)
        if len(latest) == len(groups) and all(tick - t <= 0.35 for t, _ in latest.values()):
            combined.append({"t": tick, "rss": sum(v for _, v in latest.values())})
    return combined


def index_worker(root, output):
    sys.path.insert(0, str(root / "tools/indexing"))
    import m5_index

    m5_index.no_network()
    profile = load_profile(root, PROFILE, PROFILE_SHA256)
    selector = "config/vector-index-m5-v1-1.json"
    timings = []
    with Samples(output / "index-rss.jsonl"):
        while not (output / "stop-index").exists():
            start = time.perf_counter()
            value = m5_index.inspect(root, selector, profile["selection"][selector])
            if value["records"] != 992:
                raise ValueError("index_inventory_mismatch")
            timings.append(time.perf_counter() - start)
            (output / "index-ready").touch()
            time.sleep(0.15)
    return {"status": "PASS", "latency_seconds": timings,
            "high_water_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "disk_bytes": value["disk_bytes"], "records": 992}


def dashboard_worker(root, output):
    from streamlit.testing.v1 import AppTest

    from rag_hub.dashboard_ui import load_dashboard
    from rag_hub.m5_dashboard import inspect_index
    from rag_hub.operational_selection import DURABLE

    command = [str(root / "tools/indexing/.venv/bin/python"), __file__,
               "--root", str(root), "--output", str(output), "--worker", "index"]
    log = (output / "index-worker.log").open("x")
    child = subprocess.Popen(command, cwd=root, env=environment(), stdout=log,
                             stderr=subprocess.STDOUT)
    timings = {}
    try:
        with Samples(output / "dashboard-rss.jsonl"):
            apps = []
            for n in range(2):
                app = AppTest.from_file(str(root / "apps/ingestion_dashboard/app.py"),
                                        default_timeout=180)
                app.session_state["operational_release"] = DURABLE
                start = time.perf_counter()
                app.run()
                if app.exception or app.error:
                    raise ValueError("dashboard_session_load_failed:" + str(app.error))
                timings["first_session_cold" if n == 0 else "second_session_cached"] = (
                    time.perf_counter() - start)
                apps.append(app)
            # Two distinct session states remain live, backed by the actual shared cache.
            warm = []
            for _ in range(3):
                for app in apps:
                    start = time.perf_counter()
                    app.sidebar.radio(key="view").set_value("Document Explorer").run()
                    if app.exception or app.error:
                        raise ValueError("dashboard_warm_navigation_failed")
                    warm.append(time.perf_counter() - start)
            timings["warm_navigation"] = warm
            data = load_dashboard(str(root), selector=DURABLE)
            assert data.summary()["units"] == 553
            start = time.perf_counter()
            apps[0].selectbox(key="document").set_value("C14").run()
            timings["document_selection"] = time.perf_counter() - start
            # Exact current IDs are taken from the accepted catalog, never guessed.
            start = time.perf_counter()
            sid = data.corpus.catalog.list_sections(limit=1)["items"][0]["section_id"]
            data.section(sid)
            timings["section_lookup"] = time.perf_counter() - start
            # Submit the real isolated metadata verifier from the live UI and open its parent.
            payload = json.loads((root / "data/indexes/m5-chroma-v1/verified-inputs.json").read_text())
            cid = payload["rows"][0]["id"]
            app = apps[0]
            app.text_input(key="m5_chunk").set_value(cid)
            start = time.perf_counter()
            app.button(key="FormSubmitter:m5-index-inspection-Verify selected M5 index").click().run()
            timings["m5_ui_submission"] = time.perf_counter() - start
            start = time.perf_counter()
            app.button(key="m5-open-parent").click().run()
            timings["complete_parent_display"] = time.perf_counter() - start
            if (app.exception or app.error or not any(x.value == "Complete authorized parent"
                                                     for x in app.subheader)
                    or not any("scor" in x.value for x in app.warning)):
                raise ValueError("complete_parent_or_mandatory_warning_missing")
            # The other session retains its own view and can navigate while readers coexist.
            assert apps[1].session_state["view"] == "Document Explorer"
            parent_times = []
            for _ in range(3):
                start = time.perf_counter()
                view = data.verified_unit(payload["rows"][0]["metadata"]["unit_id"])
                assert view["consumer"]["llm_context"]["qualification"]["complete_unit_only"]
                parent_times.append(time.perf_counter() - start)
            timings["verified_parent_lookup"] = parent_times
            timings["direct_m5_inspection"] = []
            for _ in range(2):
                start = time.perf_counter()
                assert inspect_index(root)["records"] == 992
                timings["direct_m5_inspection"].append(time.perf_counter() - start)
            (output / "steady-state-start.json").write_text(json.dumps({"t": time.time()}))
            time.sleep(3)
            if child.poll() is not None:
                raise ValueError("concurrent_index_reader_terminated")
    finally:
        (output / "stop-index").touch()
        try:
            child.wait(timeout=120)
        except subprocess.TimeoutExpired:
            child.terminate()
            child.wait(timeout=10)
        log.close()
    if child.returncode:
        raise ValueError("concurrent_index_reader_failed")
    return {"status": "PASS", "live_sessions": 2, "timings_seconds": timings,
            "session_isolation": "PASS", "shared_verified_cache": True,
            "mandatory_C10_qualification": "PASS", "browser_verified": False,
            "high_water_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", choices=["dashboard", "index"], required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if not output.is_relative_to(root / "workspace") or not output.is_dir():
        parser.error("existing private workspace output required")
    start = time.time()
    try:
        result = (dashboard_worker if args.worker == "dashboard" else index_worker)(root, output)
    except (OSError, ValueError, RuntimeError, KeyError, AssertionError,
            subprocess.SubprocessError) as exc:
        result = {"status": "FAIL", "error": repr(exc)}
    result.update(worker=args.worker, started_utc_epoch=start, finished_utc_epoch=time.time())
    (output / (args.worker + "-result.json")).write_text(json.dumps(result, indent=2) + "\n")
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
