"""Exact accepted M3/M4/M5 references; no new admission or raw-section path."""

import json
from pathlib import Path

from tools.indexing.m5_index import UPSTREAM, encoded, local, metadata, read_bound, sha

M5_SELECTOR = "config/vector-index-m5-v1-1.json"
M5_SHA = "3ee50fc59ee126f0473332a7ca7d40ed35fd4b88baf3254cfd3b19a19d52503b"
PROFILE = "config/operations-durable-m0-m5-v1.json"
PROFILE_SHA = "c9c28c7d5b35b965c7044d3817e3063b1fe4b0d8705fcb73344527e1d004e4a4"
EXPORT_SCHEMA = "m6-verified-source-export-1.0"
ROW_FIELDS = {"chunk_id", "text", "input_text_sha256", "document_id", "format", "unit_id",
              "reference_classification", "qualification_sha256"}


def accepted(root):
    """Hash-check accepted immutable records. Saved text is comparison evidence only."""
    root = Path(root).resolve(strict=True)
    selection = json.loads(read_bound(root, M5_SELECTOR, M5_SHA))
    manifest = json.loads(read_bound(root, selection["manifest_path"], selection["manifest_sha256"]))
    if manifest["schema"] != "m5-chroma-1.1" or manifest["records"] != 992:
        raise ValueError("m6_incompatible_m5_release")
    payload = json.loads(read_bound(root, manifest["payload_path"], manifest["spec"]["payload_sha256"]))
    bindings = (payload["bindings"] | manifest["spec"]["components"] | UPSTREAM |
                {M5_SELECTOR: M5_SHA, selection["manifest_path"]: selection["manifest_sha256"],
                 manifest["payload_path"]: manifest["spec"]["payload_sha256"], PROFILE: PROFILE_SHA})
    if (any(payload["bindings"].get(p) != h for p, h in UPSTREAM.items())
            or manifest["upstream_bindings"] != payload["bindings"]):
        raise ValueError("m6_mixed_upstream_releases")
    for p, h in bindings.items():
        if p.startswith(("workspace/", "archive/", "releases/")):
            raise ValueError("m6_nondurable_dependency")
        read_bound(root, p, h)
    m4s = json.loads(read_bound(root, "config/embedding-artifacts-m4-durable-v1.json",
                               UPSTREAM["config/embedding-artifacts-m4-durable-v1.json"]))
    m4 = json.loads(read_bound(root, m4s["manifest_path"], m4s["manifest_sha256"]))
    for p, h in m4["files"].items():
        read_bound(root, p, h)
        bindings[p] = h
    records = [json.loads(s) for s in local(root, m4["records_path"]).read_text().splitlines()]
    inputs = [json.loads(s) for s in local(root, m4["inputs_path"]).read_text().splitlines()]
    want = []
    for record, source in zip(records, inputs, strict=True):
        if source["chunk_id"] != record["chunk_id"] or sha(source["text"].encode()) != record["input_text_sha256"]:
            raise ValueError("m6_altered_accepted_text")
        want.append({"id": record["chunk_id"], "metadata": metadata(record,
            m4["catalog_manifest_sha256"], m4["model_configuration"]["sha256"])})
    if (len(want) != 992 or len({r["id"] for r in want}) != 992
            or encoded(want) != encoded(payload["rows"])):
        raise ValueError("m6_incomplete_m5_m4_bijection")
    return bindings, records, inputs


def validate_payload(root, payload):
    bindings, records, inputs = accepted(root)
    if (set(payload) != {"schema", "bindings", "rows", "live_verified_chunks"}
            or payload["schema"] != EXPORT_SCHEMA or payload["bindings"] != bindings
            or type(payload["live_verified_chunks"]) is not int or payload["live_verified_chunks"] != 992):
        raise ValueError("m6_invalid_or_mixed_export")
    rows = payload["rows"]
    if len(rows) != 992 or len({r["chunk_id"] for r in rows}) != 992:
        raise ValueError("m6_missing_duplicate_chunk_ids")
    for row, record, source in zip(rows, records, inputs, strict=True):
        expected = {key: record[key] for key in ROW_FIELDS - {"text"}}
        expected["text"] = source["text"]
        if set(row) != ROW_FIELDS or encoded(row) != encoded(expected):
            raise ValueError("m6_unauthorized_or_altered_lexical_record")
    return bindings, rows
