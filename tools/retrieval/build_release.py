"""Seal an additive M7 execution contract; never build or mutate upstream indexes."""

import argparse
import json
from pathlib import Path

from tools.indexing.m5_index import UPSTREAM, encoded, local, read_bound, sha
from tools.lexical.bindings import M5_SELECTOR, M5_SHA, PROFILE, PROFILE_SHA
from tools.retrieval.contract import COMPONENTS, PREFIX, SCHEMA

M6_SELECTOR = "config/keyword-index-m6-v1.json"
M6_SHA = "d9d8125ee77b4c88c0480526de9ed8da7c0b90cde37d235cc0c5da0744d65df0"
SELECTOR = "config/hybrid-retrieval-m7-v1.json"


def build(root):
    selections = {k: {"path": p, "sha256": UPSTREAM[p]} for k, p in (
        ("qa", "config/pdf-durable-admission-publication-v1.json"),
        ("unified", "config/unified-durable-selection-v1.json"),
        ("m3", "config/retrieval-chunks-m3-durable-v1.json"),
        ("m4", "config/embedding-artifacts-m4-durable-v1.json"))}
    selections.update(m5={"path": M5_SELECTOR, "sha256": M5_SHA},
                      m6={"path": M6_SELECTOR, "sha256": M6_SHA},
                      operations={"path": PROFILE, "sha256": PROFILE_SHA})
    m6s = json.loads(read_bound(root, M6_SELECTOR, M6_SHA))
    m6 = json.loads(read_bound(root, m6s["manifest_path"], m6s["manifest_sha256"]))
    files = m6["spec"]["bindings"] | m6["spec"]["components"] | {
        M6_SELECTOR: M6_SHA, m6s["manifest_path"]: m6s["manifest_sha256"],
        m6["records_path"]: m6["spec"]["records_sha256"],
        m6["payload_path"]: m6["spec"]["payload_sha256"]}
    m5s = json.loads(read_bound(root, M5_SELECTOR, M5_SHA))
    store = local(root, m5s["manifest_path"]).parent / "chroma"
    physical = {str(p.relative_to(root)): sha(p.read_bytes()) for p in store.rglob("*") if p.is_file()}
    files.update(physical)
    files.update({p: sha(local(root, p).read_bytes()) for p in (
        "uv.lock", "apps/ingestion_dashboard/uv.lock", "tools/chunking/uv.lock")})
    for p, h in files.items():
        read_bound(root, p, h)
    spec = {"selections": selections, "files": files,
        "components": {p: sha(local(root, p).read_bytes()) for p in COMPONENTS},
        "authority": "CANDIDATE_SEARCH_NOT_EVIDENCE", "records": 992, "parents": 553,
        "query_policy": {"version": "bge-query-instruction-1.0", "outer_whitespace": "strip",
            "instruction": PREFIX, "max_tokens_including_instruction_and_specials": 512,
            "overflow": "REJECT_NO_TRUNCATION", "normalization": "NONE"},
        "defaults": {"top_k": 10, "candidate_depth": 50, "rrf_k": 60},
        "runtime": "EXISTING_SIX_LOCKS_PYTHON_3_12_15_MACOS_ARM64",
        "vector_store": {"policy": "VERIFIED_TEMPORARY_COPY_NATIVE_M5_QUERY_ORIGINAL_UNOPENED",
                         "physical_witnesses": physical},
        "tie_policy": "native_metric_then_exact_chunk_id;RRF_descending_then_exact_chunk_id"}
    identity = sha(encoded(spec))
    path = "data/retrieval/m7-hybrid-v1/" + identity + "/manifest.json"
    manifest = {"schema": SCHEMA, "identity": identity, "spec": spec}
    target = local(root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != encoded(manifest):
        raise ValueError("m7_immutable_manifest_conflict")
    if not target.exists():
        with target.open("xb") as handle:
            handle.write(encoded(manifest))
    selection = {"schema": "m7-selection-1.0", "manifest_path": path,
                 "manifest_sha256": sha(encoded(manifest))}
    # Only the new, explicitly opt-in M7 candidate selector is written.
    local(root, SELECTOR).write_bytes(encoded(selection))
    return {"identity": identity, "selector": SELECTOR,
            "selector_sha256": sha(encoded(selection)), **selection, "bound_files": len(files)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve(strict=True)), sort_keys=True))
