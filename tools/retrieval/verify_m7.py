"""Bounded live functional/resource report; no human relevance judgments."""

import argparse
import json
import resource
import statistics
import time
from pathlib import Path

from tools.retrieval.service import RetrievalService


def verify(root, selector, selector_sha256):
    start = time.perf_counter()
    service = RetrievalService(root, selector=selector, selector_sha256=selector_sha256)
    load_seconds = time.perf_counter() - start
    reports = []
    try:
        for query in ("How does retrieval augmented generation work?", "BM25 RRF",
                      "ChromaDB", "GraphRAG", "0.25", "C++", ""):
            for mode in ("vector", "bm25", "hybrid"):
                result = service.search(query, mode=mode, top_k=5, candidate_depth=20)
                reports.append({"query": query, "mode": mode, "result": result})
        latencies = {}
        for mode in ("vector", "bm25", "hybrid"):
            values = [r["result"]["diagnostics"]["seconds"] for r in reports
                      if r["mode"] == mode and r["query"] not in {reports[0]["query"], ""}]
            latencies[mode] = {"samples": len(values), "median_seconds": statistics.median(values),
                               "maximum_seconds": max(values)}
        peak_by_worker = {kind: max(r["result"]["diagnostics"]["workers"].get(kind, {}).get(
            "peak_rss_bytes", 0) for r in reports) for kind in ("encode", "vector", "bm25")}
        service.check()
        return {"status": "PASS_FUNCTIONAL_NOT_RELEVANCE", "release_identity": service.manifest["identity"],
            "records": len(service.inventory), "parents": 553, "documents": 16,
            "coordinator_load_seconds": load_seconds, "queries": reports,
            "warm_query_latency": latencies, "worker_peak_rss_bytes": peak_by_worker,
            "coordinator_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "sum_of_separate_worker_peaks_bytes": sum(peak_by_worker.values()),
            "resource_limitations": "Separate peak RSS sum is not simultaneous resident memory; "
                "no OS process sampler available in sandbox. No concurrency, browser or long-run SLA claimed.",
            "elapsed_seconds": time.perf_counter() - start, "document_embedding_regeneration": False,
            "model_or_dependency_downloads": False, "M8_implementation": False}
    finally:
        service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--selector-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve(strict=True), args.selector, args.selector_sha256),
                     sort_keys=True, indent=2))
