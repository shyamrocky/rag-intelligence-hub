"""Local three-mode candidate retrieval; never an evidence or QA authority."""

import argparse
import atexit
import contextlib
import json
import os
import selectors
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from tools.indexing.m5_index import encoded, sha
from tools.retrieval.contract import AUTHORITY, check_files, fuse, load_release, parameters

ENVIRONMENTS = {"encode": "tools/embeddings", "vector": "tools/indexing", "bm25": "tools/lexical"}


class Process:
    def __init__(self, root, kind, selector, selector_sha256, identity):
        interpreter = root / ENVIRONMENTS[kind] / ".venv/bin/python"
        if not interpreter.is_file():
            raise ValueError("m7_missing_locked_environment:" + kind)
        env = dict(os.environ)
        for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
            env.pop(key, None)
        env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1",
                   TRANSFORMERS_OFFLINE="1", ANONYMIZED_TELEMETRY="false", OTEL_SDK_DISABLED="true")
        self.resources = contextlib.ExitStack()
        self.errors = self.resources.enter_context(tempfile.TemporaryFile(mode="w+t"))  # noqa: SIM115
        self.process = subprocess.Popen([str(interpreter), "-m", "tools.retrieval.worker",
            "--root", str(root), "--kind", kind, "--selector", selector,
            "--selector-sha256", selector_sha256], cwd=root, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=self.errors, text=True, bufsize=1)
        self.identity, self.kind = identity, kind
        try:
            ready = self.read()
            if ready.get("status") != "READY" or ready.get("identity") != identity or ready.get("kind") != kind:
                raise ValueError("m7_worker_start_failed:" + ready.get("error", "invalid handshake"))
            self.load_seconds = ready["seconds"]
        except Exception:
            self.close()
            raise

    def read(self):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=180):
                raise ValueError("m7_worker_timeout_no_fallback")
        line = self.process.stdout.readline(2_000_000)
        if not line or not line.endswith("\n"):
            raise ValueError("m7_worker_closed_or_invalid_output")
        return json.loads(line)

    def request(self, request):
        if self.process.poll() is not None:
            raise ValueError("m7_worker_unavailable_no_fallback")
        self.process.stdin.write(encoded(request).decode() + "\n")
        self.process.stdin.flush()
        value = self.read()
        if (value.get("status") != "PASS" or value.get("identity") != self.identity
                or value.get("kind") != self.kind or value.get("authority") != AUTHORITY):
            raise ValueError("m7_worker_failure_no_fallback:" + value.get("error", "invalid binding"))
        return value

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write('{"close":true}\n')
                self.process.stdin.flush()
                self.process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait(timeout=10)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()
        self.resources.close()


class RetrievalService:
    """Explicit compatible release; lazily reused workers with a live integrity lease."""

    def __init__(self, root, *, selector, selector_sha256):
        self.root = Path(root).resolve(strict=True)
        self.selector, self.selector_sha256 = selector, selector_sha256
        self.manifest, self.files, self.inventory = load_release(self.root, selector, selector_sha256)
        self._workers = {}
        self._lock = threading.RLock()
        self._closed = False
        atexit.register(self.close)

    def _request(self, kind, request):
        if kind not in self._workers:
            self._workers[kind] = Process(self.root, kind, self.selector, self.selector_sha256,
                                         self.manifest["identity"])
        return self._workers[kind].request(request)

    def check(self):
        if self._closed:
            raise ValueError("m7_service_closed_reconstruct_explicitly")
        check_files(self.root, self.files)

    def search(self, query, *, mode="hybrid", top_k=10, candidate_depth=50, rrf_k=60, filters=None):
        with self._lock:
            return self._search(query, mode, top_k, candidate_depth, rrf_k, filters)

    def _search(self, query, mode, top_k, candidate_depth, rrf_k, filters):
        start = time.perf_counter()
        self.check()
        query, filters = parameters(query, mode, top_k, candidate_depth, rrf_k, filters, self.inventory)
        lists, metrics = {}, {}
        names = ["vector", "bm25"] if mode == "hybrid" else [mode]
        try:
            if query and any(c.isalnum() for c in query):
                for name in names:
                    request = {"query": query, "depth": candidate_depth, "filters": filters}
                    if name == "vector":
                        encoding = self._request("encode", {"query": query})
                        request["query_vector"] = encoding["result"]
                        metrics["encode"] = {k: encoding[k] for k in ("seconds", "peak_rss_bytes")}
                        metrics["query_binding"] = {k: v for k, v in encoding["result"].items() if k != "vector"}
                    response = self._request(name, request)
                    lists[name] = response["result"]
                    if len(lists[name]) > candidate_depth:
                        raise ValueError("m7_worker_excessive_candidates")
                    metrics[name] = {k: response[k] for k in ("seconds", "peak_rss_bytes")}
            else:
                lists = {name: [] for name in names}
            candidates = fuse(lists, mode=mode, top_k=top_k, rrf_k=rrf_k,
                              inventory=self.inventory, filters=filters)
            self.check()
        except Exception:
            # No stale cached candidates or partial hybrid success after worker/integrity failure.
            self.close()
            raise
        identities = {k: dict(v) for k, v in self.manifest["spec"]["selections"].items()}
        return {"schema": "m7-candidates-1.0", "authority": AUTHORITY,
            "complete_parent_rehydration_required": True, "retrieval_mode": mode,
            "release_identity": self.manifest["identity"],
            "selection": {"path": self.selector, "sha256": self.selector_sha256},
            "index_release_bindings": identities, "query_sha256": sha(query.encode()),
            "parameters": {"top_k": top_k, "candidate_depth": candidate_depth, "rrf_k": rrf_k,
                           "filters": filters}, "candidates": candidates,
            "diagnostics": {"seconds": time.perf_counter() - start, "workers": metrics,
                "worker_load_seconds": {k: v.load_seconds for k, v in self._workers.items()},
                "quality": "NOT_EVALUATED_M9", "evidence": "NOT_PROVIDED_USE_VERIFIED_PARENT_READER"}}

    def close(self):
        with self._lock:
            for worker in self._workers.values():
                worker.close()
            self._workers.clear()
            self._closed = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--selector-sha256", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--mode", choices=["vector", "bm25", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-depth", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--filters", default="{}")
    args = parser.parse_args()
    service = RetrievalService(args.root, selector=args.selector, selector_sha256=args.selector_sha256)
    try:
        result = service.search(args.query, mode=args.mode, top_k=args.top_k,
            candidate_depth=args.candidate_depth, rrf_k=args.rrf_k, filters=json.loads(args.filters))
        print(json.dumps(result, allow_nan=False, sort_keys=True))
    finally:
        service.close()


if __name__ == "__main__":
    main()
