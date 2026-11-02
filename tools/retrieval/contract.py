"""M7 candidate-only contract; immutable selectors, no admission decisions."""

import json
import math
import unicodedata
from pathlib import Path

from tools.indexing.m5_index import encoded, read_bound, sha

SCHEMA = "m7-retrieval-1.0"
AUTHORITY = "CANDIDATES_ONLY_NOT_AUTHORIZED_EVIDENCE"
PREFIX = "Represent this sentence for searching relevant passages: "
META = {"document_id", "format", "reference_classification"}
COMPONENTS = ("tools/retrieval/contract.py", "tools/retrieval/service.py",
              "tools/retrieval/worker.py")


def load_release(root, selector, selector_sha256):
    root = Path(root).resolve(strict=True)
    selected = json.loads(read_bound(root, selector, selector_sha256))
    if set(selected) != {"schema", "manifest_path", "manifest_sha256"} or selected[
            "schema"] != "m7-selection-1.0":
        raise ValueError("m7_wrong_selector")
    manifest = json.loads(read_bound(root, selected["manifest_path"], selected["manifest_sha256"]))
    spec = manifest["spec"]
    if (set(manifest) != {"schema", "identity", "spec"} or manifest["schema"] != SCHEMA
            or manifest["identity"] != sha(encoded(spec))
            or selected["manifest_path"] != "data/retrieval/m7-hybrid-v1/" +
                manifest["identity"] + "/manifest.json"
            or spec["query_policy"] != {"version": "bge-query-instruction-1.0",
                "outer_whitespace": "strip", "instruction": PREFIX,
                "max_tokens_including_instruction_and_specials": 512,
                "overflow": "REJECT_NO_TRUNCATION", "normalization": "NONE"}
            or spec["defaults"] != {"top_k": 10, "candidate_depth": 50, "rrf_k": 60}
            or set(spec["components"]) != set(COMPONENTS)):
        raise ValueError("m7_incompatible_manifest")
    for name, digest in (spec["files"] | spec["components"]).items():
        if name.startswith(("workspace/", "archive/", "releases/")):
            raise ValueError("m7_nondurable_runtime_dependency")
        read_bound(root, name, digest)
    files = spec["files"] | spec["components"] | {selector: selector_sha256,
                  selected["manifest_path"]: selected["manifest_sha256"]}
    m5 = spec["selections"]["m5"]
    ms = json.loads(read_bound(root, m5["path"], m5["sha256"]))
    mm = json.loads(read_bound(root, ms["manifest_path"], ms["manifest_sha256"]))
    payload = json.loads(read_bound(root, mm["payload_path"], mm["spec"]["payload_sha256"]))
    inventory = {r["id"]: {k: r["metadata"][k] for k in META} for r in payload["rows"]}
    if len(inventory) != 992 or len(payload["rows"]) != 992:
        raise ValueError("m7_wrong_inventory")
    for binding in spec["selections"].values():
        if spec["files"].get(binding["path"]) != binding["sha256"]:
            raise ValueError("m7_unbound_selection")
    return manifest, files, inventory


def check_files(root, files):
    for name, digest in files.items():
        read_bound(root, name, digest)


def parameters(query, mode, top_k, candidate_depth, rrf_k, filters, inventory):
    if mode not in {"vector", "bm25", "hybrid"}:
        raise ValueError("m7_mode_must_be_vector_bm25_hybrid")
    for name, value, lower, upper in (("top_k", top_k, 1, 992),
            ("candidate_depth", candidate_depth, top_k, 992), ("rrf_k", rrf_k, 1, 10000)):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError("m7_invalid_" + name)
    if not isinstance(query, str):
        raise TypeError("m7_query_must_be_text")
    if len(query) > 16384 or any(unicodedata.category(c) == "Cs" for c in query):
        raise ValueError("m7_query_invalid_or_excessive")
    filters = {} if filters is None else filters
    if not isinstance(filters, dict) or set(filters) - META:
        raise ValueError("m7_unsupported_filter")
    for key, value in filters.items():
        if type(value) is not str or value not in {m[key] for m in inventory.values()}:
            raise ValueError("m7_unknown_filter_value")
    return query.strip(), dict(filters)


def native_hits(hits, retriever, inventory, filters):
    metric = "distance" if retriever == "vector" else "score"
    seen = set()
    for rank, hit in enumerate(hits, 1):
        cid = hit["chunk_id"]
        if (set(hit) != META | {"chunk_id", "rank", metric} or cid not in inventory
                or cid in seen or type(hit["rank"]) is not int or hit["rank"] != rank
                or any(hit[k] != inventory[cid][k] for k in META)
                or any(hit[k] != v for k, v in filters.items())
                or type(hit[metric]) not in {int, float} or not math.isfinite(hit[metric])
                or retriever == "vector" and hit[metric] < 0):
            raise ValueError("m7_invalid_or_unauthorized_native_candidate")
        seen.add(cid)
    direction = 1 if retriever == "vector" else -1
    if hits != sorted(hits, key=lambda h: (direction * h[metric], h["chunk_id"])):
        raise ValueError("m7_invalid_native_ranking")
    return hits


def fuse(lists, *, mode, top_k, rrf_k, inventory, filters):
    expected = {"vector", "bm25"} if mode == "hybrid" else {mode}
    if set(lists) != expected:
        raise ValueError("m7_retriever_failure_no_fallback")
    combined = {}
    for name in sorted(lists):
        for hit in native_hits(lists[name], name, inventory, filters):
            cid = hit["chunk_id"]
            row = combined.setdefault(cid, {"chunk_id": cid, **inventory[cid],
                "retrieval_mode": mode, "contributing_retrievers": [], "rrf_score": None,
                "vector_rank": None, "vector_distance": None, "bm25_rank": None,
                "bm25_score": None, "complete_parent_rehydration_required": True})
            row["contributing_retrievers"].append(name)
            row[name + "_rank"] = hit["rank"]
            row[name + ("_distance" if name == "vector" else "_score")] = hit[
                "distance" if name == "vector" else "score"]
    rows = list(combined.values())
    if mode == "hybrid":
        for row in rows:
            row["rrf_score"] = sum(1.0 / (rrf_k + row[n + "_rank"])
                                    for n in row["contributing_retrievers"])
        rows.sort(key=lambda r: (-r["rrf_score"], r["chunk_id"]))
    else:
        rows.sort(key=lambda r: r[mode + "_rank"])
    return [{**r, "rank": i} for i, r in enumerate(rows[:top_k], 1)]


def validate_query_vector(packet, query):
    """Internal bridge only; public API accepts text, never supplied vectors."""
    import numpy as np

    fields = {"vector", "vector_sha256", "query_sha256", "encoded_text_sha256",
              "token_ids_sha256", "tokens", "model_configuration_sha256", "policy"}
    if (set(packet) != fields or packet["policy"] != "bge-query-instruction-1.0"
            or packet["query_sha256"] != sha(query.encode())
            or packet["encoded_text_sha256"] != sha((PREFIX + query).encode())
            or packet["model_configuration_sha256"] !=
                "2444f602babc045234dba3258e89fa4a7ea26572fa748576c6df0509dc24e3de"
            or type(packet["tokens"]) is not int or not 2 <= packet["tokens"] <= 512
            or not isinstance(packet["token_ids_sha256"], str)
            or len(packet["token_ids_sha256"]) != 64
            or not isinstance(packet["vector"], list)
            or any(type(v) is not float for v in packet["vector"])):
        raise ValueError("m7_forged_query_binding")
    vector = np.asarray(packet["vector"], dtype=np.float32)
    if (vector.shape != (384,) or not np.isfinite(vector).all()
            or not np.isclose(np.linalg.norm(vector), 1.0, atol=2e-6, rtol=0)
            or sha(vector.tobytes()) != packet["vector_sha256"]):
        raise ValueError("m7_query_vector_dimension_norm_or_integrity")
    return vector
