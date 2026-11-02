"""Optional M5 metadata inspection via the isolated numerical-store interpreter."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

SELECTOR = "config/vector-index-m5-v1-1.json"
# Filled only after immutable candidate construction and verification.
SELECTOR_SHA256 = "3ee50fc59ee126f0473332a7ca7d40ed35fd4b88baf3254cfd3b19a19d52503b"


def inspect_index(root, *, document=None, chunk_id=None):
    root = Path(root).resolve()
    path = root / SELECTOR
    if hashlib.sha256(path.read_bytes()).hexdigest() != SELECTOR_SHA256:
        raise ValueError("m5_dashboard_selector_changed_or_not_published")
    selected = json.loads(path.read_bytes())
    manifest_path = root / selected["manifest_path"]
    if (not manifest_path.resolve().is_relative_to(root / "data/indexes/m5-chroma-v1")
            or hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            != selected["manifest_sha256"]):
        raise ValueError("m5_dashboard_manifest_changed")
    manifest = json.loads(manifest_path.read_bytes())
    for name, digest in manifest["spec"]["components"].items():
        component = root / name
        if (not component.resolve().is_relative_to(root / "tools/indexing")
                or hashlib.sha256(component.read_bytes()).hexdigest() != digest):
            raise ValueError("m5_dashboard_component_changed")
    worker = root / "tools/indexing/m5_index.py"
    interpreter = root / "tools/indexing/.venv/bin/python"
    if not worker.is_file() or not interpreter.is_file():
        raise ValueError("m5_locked_runtime_not_installed")
    command = [str(interpreter), str(worker), "inspect", "--root", str(root),
               "--selector", SELECTOR, "--selector-sha256", SELECTOR_SHA256]
    if document:
        command += ["--document", document]
    if chunk_id:
        command += ["--chunk-id", chunk_id]
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", ANONYMIZED_TELEMETRY="false",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", OTEL_SDK_DISABLED="true")
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True,
                            timeout=120, check=False)
    try:
        value = json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError("m5_worker_unavailable_no_evidence_fallback") from exc
    if (result.returncode or value.get("status") != "PASS"
            or value.get("authority") != "INSPECTION_ONLY_NOT_EVIDENCE"):
        raise ValueError("m5_index_verification_failed:" + value.get("error", "unknown"))
    return value


def open_parent(state, chunk_id):
    state["view"] = "Chunk Inspector"
    state["chunk_entered"] = chunk_id
    state["chunk_selected"] = ""
    state["chunk_unit_filter"] = ""
    state["chunk_section_filter"] = ""
    state["chunk_document"] = "All"


def render(root, *, selector, document_ids):
    import streamlit as st

    with st.expander("M5 · Persistent local ChromaDB index", expanded=False):
        st.caption("INSPECTION_ONLY · numerical lookup store; source evidence still requires "
                   "the complete authorized parent. No semantic search or generation.")
        if selector != "config/retrieval-chunks-m3-durable-v1.json":
            st.info("Select the durable operational release to inspect its opt-in M5 index. "
                    "Historical modes keep their original catalogs.")
            return
        st.caption(f"Explicit index selector: {SELECTOR}")
        st.caption("The separate locked M5 worker validates the entire selected index on demand. "
                   "No detached authorization or text payload is cached.")
        with st.form("m5-index-inspection"):
            did = st.selectbox("Index document filter", ["All", *document_ids], key="m5_document")
            cid = st.text_input("Index exact Chunk ID (optional)", key="m5_chunk")
            submitted = st.form_submit_button("Verify selected M5 index")
        if not submitted:
            return
        try:
            with st.spinner("Checking persistent records and frozen upstream bindings…"):
                value = inspect_index(root, document=None if did == "All" else did,
                                      chunk_id=cid.strip() or None)
            st.success("Selected index integrity verified · all 992 authorized records reconcile.")
            a, b, c = st.columns(3)
            a.metric("Indexed / expected", f"{value['records']} / 992")
            b.metric("Vector dimensions", value["dimension"])
            c.metric("Database bytes", f"{value['disk_bytes']:,}")
            st.text(f"Collection: {value['collection']}")
            st.text(f"Storage: {value['storage']}")
            st.text(f"Model: {value['model']}")
            st.text(f"Manifest SHA-256: {value['manifest_sha256']}")
            st.dataframe([{"Document": k, "Indexed records": v}
                          for k, v in value["document_counts"].items()], hide_index=True)
            st.caption(f"{value['matching_records']} matching records · "
                       f"fresh worker check {value['seconds']:.2f}s")
            record = value["exact_record"]
            if record:
                st.text(record["chunk_id"])
                with st.expander("Whitelisted identity metadata — no source text"):
                    st.json(record["metadata"])
                st.button("Inspect complete authorized parent", key="m5-open-parent",
                          on_click=open_parent, args=(st.session_state, record["chunk_id"]))
        except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
            st.error("M5 index unavailable or invalid. No database content is shown as evidence.")
            st.text(str(exc))
