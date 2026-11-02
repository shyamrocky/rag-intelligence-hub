"""M8 composition contract; native publications alone authorize source evidence."""

import json
import math
import re
from pathlib import Path

from tools.indexing.m5_index import encoded, read_bound, sha
from tools.retrieval.contract import AUTHORITY, META, load_release, parameters

SCHEMA = "m8-evidence-package-1.0"
M7_SELECTOR = "config/hybrid-retrieval-m7-v1.json"
M7_SHA = "87110b099e59aca1460bfd5dc847e073964c392ccf42b559ecf88483cddb37f9"
COMPONENTS = ("tools/evidence/contract.py", "tools/evidence/service.py",
              "tools/evidence/token_worker.py")
POLICY = {"version": "m8-atomic-bge-json-1.0", "tokenizer_spec": "config/bge-tokenizer-v1.json",
    "tokenizer_spec_sha256": "03d41df1a646ed13d41bd8b485c573864da5821109e57750135bf94f0dbde577",
    "counting": "canonical UTF-8 JSON blocks; pinned BGE tokens with special tokens; no truncation",
    "selection": "ascending best final candidate rank; unit ID ties; skip oversized whole parents",
    "scope": "llm_evidence only; complete authorized consumer, context, citations and qualifications",
    "llm_window": "UNSPECIFIED; BGE measurement is not a promise about an M10 tokenizer"}


def load_configuration(root, selector, selector_sha256):
    root = Path(root).resolve(strict=True)
    selected = json.loads(read_bound(root, selector, selector_sha256))
    if set(selected) != {"schema", "manifest_path", "manifest_sha256"} or selected[
            "schema"] != "m8-selection-1.0":
        raise ValueError("m8_wrong_selection")
    manifest = json.loads(read_bound(root, selected["manifest_path"], selected["manifest_sha256"]))
    spec = manifest["spec"]
    if (set(manifest) != {"schema", "identity", "spec"} or manifest["schema"] != "m8-composition-1.0"
            or manifest["identity"] != sha(encoded(spec))
            or selected["manifest_path"] != "data/evidence/m8-v1/" + manifest["identity"] + "/manifest.json"
            or spec["m7"] != {"path": M7_SELECTOR, "sha256": M7_SHA}
            or spec["budget_policy"] != POLICY or set(spec["components"]) != set(COMPONENTS)
            or spec["authority"] != "ASSEMBLY_ONLY_NOT_ADMISSION"):
        raise ValueError("m8_incompatible_configuration")
    m7, files, inventory = load_release(root, M7_SELECTOR, M7_SHA)
    if spec["m7_manifest_sha256"] != sha(encoded(m7)):
        raise ValueError("m8_m7_manifest_changed")
    files |= spec["components"] | {selector: selector_sha256,
        selected["manifest_path"]: selected["manifest_sha256"]}
    for name, digest in files.items():
        read_bound(root, name, digest)
    return manifest, m7, files, inventory


def validate_candidates(value, m7, inventory):
    """Validate untrusted transport. Ranking metadata is not an attestation or admission."""
    keys = {"schema", "authority", "complete_parent_rehydration_required", "retrieval_mode",
            "release_identity", "selection", "index_release_bindings", "query_sha256",
            "parameters", "candidates", "diagnostics"}
    if (not isinstance(value, dict) or set(value) != keys or value["schema"] != "m7-candidates-1.0"
            or value["authority"] != AUTHORITY
            or value["complete_parent_rehydration_required"] is not True
            or value["release_identity"] != m7["identity"]
            or value["selection"] != {"path": M7_SELECTOR, "sha256": M7_SHA}
            or value["index_release_bindings"] != m7["spec"]["selections"]
            or not isinstance(value["query_sha256"], str)
            or re.fullmatch("[0-9a-f]{64}", value["query_sha256"]) is None):
        raise ValueError("m8_invalid_or_cross_release_candidate_envelope")
    p = value["parameters"]
    if not isinstance(p, dict) or set(p) != {"top_k", "candidate_depth", "rrf_k", "filters"}:
        raise ValueError("m8_invalid_candidate_parameters")
    mode = value["retrieval_mode"]
    parameters("", mode, p["top_k"], p["candidate_depth"], p["rrf_k"], p["filters"], inventory)
    hits = value["candidates"]
    if not isinstance(hits, list) or len(hits) > p["top_k"]:
        raise ValueError("m8_excessive_or_invalid_candidates")
    seen, native_ranks = set(), {"vector": set(), "bm25": set()}
    candidate_keys = META | {"chunk_id", "rank", "retrieval_mode", "contributing_retrievers",
        "rrf_score", "vector_rank", "vector_distance", "bm25_rank", "bm25_score",
        "complete_parent_rehydration_required"}
    for rank, hit in enumerate(hits, 1):
        if not isinstance(hit, dict) or set(hit) != candidate_keys:
            raise ValueError("m8_detached_text_or_invalid_candidate_fields")
        cid = hit["chunk_id"]
        if (not isinstance(cid, str) or cid not in inventory or cid in seen
                or type(hit["rank"]) is not int or hit["rank"] != rank
                or hit["retrieval_mode"] != mode or hit["complete_parent_rehydration_required"] is not True
                or any(hit[k] != inventory[cid][k] for k in META)
                or any(hit[k] != v for k, v in p["filters"].items())):
            raise ValueError("m8_unknown_duplicate_or_forged_candidate_identity")
        seen.add(cid)
        names = hit["contributing_retrievers"]
        allowed = {"vector", "bm25"} if mode == "hybrid" else {mode}
        if (not isinstance(names, list) or not names or any(type(n) is not str for n in names)
                or names != sorted(set(names)) or not set(names) <= allowed
                or mode != "hybrid" and set(names) != allowed):
            raise ValueError("m8_invalid_retriever_contributions")
        for name, metric in (("vector", "vector_distance"), ("bm25", "bm25_score")):
            n, score = hit[name + "_rank"], hit[metric]
            if name in names:
                if (type(n) is not int or not 1 <= n <= p["candidate_depth"]
                        or n in native_ranks[name] or type(score) not in {int, float}
                        or not math.isfinite(score) or name == "vector" and score < 0):
                    raise ValueError("m8_invalid_native_diagnostics")
                native_ranks[name].add(n)
            elif n is not None or score is not None:
                raise ValueError("m8_conflicting_native_diagnostics")
        score = hit["rrf_score"]
        if mode == "hybrid":
            expected = sum(1 / (p["rrf_k"] + hit[n + "_rank"]) for n in names)
            if type(score) not in {int, float} or score != expected:
                raise ValueError("m8_forged_rrf_score")
        elif score is not None:
            raise ValueError("m8_unexpected_rrf_score")
    key = (lambda h: (-h["rrf_score"], h["chunk_id"])) if mode == "hybrid" else (
        lambda h: (h[mode + "_rank"], h["chunk_id"]))
    if hits != sorted(hits, key=key):
        raise ValueError("m8_invalid_final_ranking")
    for name in ("vector", "bm25"):
        metric = name + ("_distance" if name == "vector" else "_score")
        rows = sorted((h for h in hits if name in h["contributing_retrievers"]),
                      key=lambda h: h[name + "_rank"])
        sign = 1 if name == "vector" else -1
        if rows != sorted(rows, key=lambda h: (sign * h[metric], h["chunk_id"])):
            raise ValueError("m8_conflicting_native_ranking")
    return hits


def budget_limit(value):
    if type(value) is not int or not 1 <= value <= 1000000:
        raise ValueError("m8_budget_must_be_integer_1_to_1000000")
    return value
