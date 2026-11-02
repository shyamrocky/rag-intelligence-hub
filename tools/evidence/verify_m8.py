"""Bounded offline reconstruction evidence; fixed-ID controls are not relevance judgments."""

import argparse
import json
import resource
import time
from pathlib import Path

from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from tools.evidence.contract import M7_SELECTOR, M7_SHA
from tools.evidence.service import EvidenceService
from tools.indexing.m5_index import encoded, sha
from tools.retrieval.contract import fuse
from tools.retrieval.service import RetrievalService


def verify(root, selector, selector_sha256):
    start = time.perf_counter()
    service = EvidenceService(root, selector=selector, selector_sha256=selector_sha256)
    load_seconds = time.perf_counter() - start
    retriever = RetrievalService(root, selector=M7_SELECTOR, selector_sha256=M7_SHA)
    modes = []
    try:
        for mode in ["bm25", "vector", "hybrid"]:
            t = time.perf_counter()
            candidate = retriever.search("reciprocal rank fusion", mode=mode, top_k=3,
                                        candidate_depth=12, filters={"document_id": "C10"})
            package = service.assemble(candidate, token_budget=100000)
            service.validate(package, candidate)
            modes.append({"mode": mode, "status": package["status"], "counts": package["counts"],
                "tokens": package["budget"]["exact_llm_evidence_tokens"],
                "package_sha256": sha(encoded(package)), "seconds": time.perf_counter() - t})
        rows = service.catalog.list_chunks(limit=1000)["items"]
        # One exact authorized parent per source, all protected C04 units and the
        # separate corrected bibliography/appendix scopes. Machine engineering controls.
        chosen = {}
        for row in rows:
            chosen.setdefault(row["document_id"], row["chunk_id"])
        ids = set(chosen.values())
        for row in rows:
            config = service.catalog.manifest["configurations"][row["configuration_id"]]
            if config.get("schema") == "m3-qualified-config-1.0" and row["document_id"] == "C04":
                ids.add(row["chunk_id"])
            if row["document_id"] == "C14" and row["unit_id"].endswith((
                    "3e2beb72996c1337f96faee2", "d2cdf35ce50452daa3e6181b",
                    "2264d5177709cb80a8c67762", "927c731b2d70ec0478a3f01f")):
                ids.add(row["chunk_id"])
        hits = [{"chunk_id": cid, **service.inventory[cid], "rank": i,
                 "score": float(len(ids) - i)} for i, cid in enumerate(sorted(ids), 1)]
        candidate.update(retrieval_mode="bm25", query_sha256=sha(b"M8_FIXED_ID_GATEWAY_CONTROL"),
            parameters={"top_k": len(ids), "candidate_depth": len(ids), "rrf_k": 60, "filters": {}},
            diagnostics={"origin": "MACHINE_FIXED_ID_CONTROL_NOT_ACTUAL_RETRIEVAL_RANKING"})
        candidate["candidates"] = fuse({"bm25": hits}, mode="bm25", top_k=len(ids),
                                      rrf_k=60, inventory=service.inventory, filters={})
        t = time.perf_counter()
        package = service.assemble(candidate, token_budget=1000000)
        assert {p["evidence"]["document_id"] for p in package["parents"]} == set(chosen)
        repeated = service.assemble(candidate, token_budget=1000000)
        assert encoded(package) == encoded(repeated)
        # Independent vocab/config construction, no model inference or LLM tokenizer claim.
        tokenizer = PinnedBgeTokenizer(root).reference_tokenizer()
        independent_count = len(tokenizer.encode(package["llm_evidence"], add_special_tokens=True).ids)
        assert independent_count == package["budget"]["exact_llm_evidence_tokens"]
        per_parent = []
        for item in package["parents"]:
            b = item["evidence"]; p = b["verified_parent"]
            assert service.corpus.evidence.validate(p)
            per_parent.append({"unit_id": p["unit_id"], "document_id": p["document_id"],
                "classification": p["reference_classification"], "token_count": item["token_count"],
                "source_evidence_sha256": sha(encoded(p)), "memberships": len(p["memberships"]),
                "citation_locators": len(p["citation_locators"]),
                "contributing_chunks": [c["chunk_id"] for c in b["contributing_candidates"]],
                "expiration": p["consumer"].get("publication_expiration", {}).get("status"),
                "qa_observations": len(p["consumer"]["llm_context"]["qa_observations"])})
        service.check()
        return {"status": "PASS", "live_modes": modes, "load_seconds": load_seconds,
            "fixed_id_controls": {"origin": "MACHINE_ENGINEERING_CONTROLS_NOT_M7_SEARCH_OR_HUMAN_LABELS",
                "documents": len(chosen), "counts": package["counts"], "parents": per_parent,
                "tokens": independent_count, "repeated_package_identical": True,
                "independent_vocabulary_token_count_match": True,
                "seconds_two_assemblies": time.perf_counter() - t},
            "accepted_inventory": {"parents": 553, "chunks": 992, "vectors": 992,
                                   "chroma_records": 992, "bm25_records": 992},
            "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "elapsed_seconds": time.perf_counter() - start,
            "limitations": ["Not a relevance benchmark, answer-support test or human acceptance.",
                "BGE counts are not a future generation model's token window.",
                "Same-host engineering timings, not concurrency/SLA qualification."]}
    finally:
        retriever.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selector", required=True)
    p.add_argument("--selector-sha256", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    root = Path.cwd().resolve()
    target = args.output.resolve()
    if not target.is_relative_to(root / "workspace") or target.exists():
        raise ValueError("m8_report_requires_new_private_workspace_path")
    report = verify(root, args.selector, args.selector_sha256)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
