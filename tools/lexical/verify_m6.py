"""Bounded functional checks and measurements, not a relevance benchmark."""

import argparse
import json
import resource
import statistics
import time
from pathlib import Path

from tools.indexing.m5_index import no_network
from tools.lexical.bm25_index import BM25Index

QUERIES = ("BM25", "RRF", "ChromaDB", "GraphRAG", "RAG", "retrieval augmented generation",
           "retrieval-augmented", "all-MiniLM-L6-v2", "similarity_search", "400M", "0.25",
           "C++", "Precision_Ω", "zzzxnotinthecorpus918729", "")


def verify(root, selector, selector_sha256):
    no_network()
    tick = time.perf_counter()
    index = BM25Index(root, selector=selector, selector_sha256=selector_sha256)
    load_seconds = time.perf_counter() - tick
    queries = []
    latencies = []
    for query in QUERIES:
        tick = time.perf_counter()
        result = index.search(query, top_k=5)
        latencies.append(time.perf_counter() - tick)
        if result != index.search(query, top_k=5):
            raise ValueError("m6_unstable_ranking")
        queries.append({"query": query, "candidate_count_top5": len(result["candidates"]),
                        "result": result, "seconds": latencies[-1]})
    metadata = index.inspect()
    token_lengths = [len(r["tokens"]) for r in index._rows]
    return {"status": "PASS_FUNCTIONAL_NOT_RELEVANCE_EVALUATION", "index": metadata,
            "load_seconds": load_seconds, "search_seconds_median": statistics.median(latencies),
            "search_seconds_max": max(latencies), "queries": queries,
            "lexical_tokens": sum(token_lengths), "empty_lexical_records": token_lengths.count(0),
            "records_with_at_most_two_tokens": sum(n <= 2 for n in token_lengths),
            "disk_version_bytes": sum((root / n).stat().st_size for n in index._files
                if n.startswith("data/indexes/m6-bm25-v1/") and not n.endswith("verified-inputs.json")),
            "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "bound_files": len(index._files), "numerical_inference": False,
            "parent_rehydration": "MANDATORY_EXISTING_GATEWAY_NOT_IMPLEMENTED_BY_SEARCH",
            "quality_limit": "No Recall@K, MRR or owner relevance labels; deferred to M9"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--selector", required=True)
    p.add_argument("--selector-sha256", required=True)
    args = p.parse_args()
    print(json.dumps(verify(args.root.resolve(strict=True), args.selector, args.selector_sha256),
                     sort_keys=True))
