"""Source-only live export in the unchanged M4 environment. Never run inference."""

import argparse
import json
import resource
import time
from pathlib import Path

from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.embedding_inputs import embedding_input
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from tools.indexing.m5_index import encoded, local, no_network, sha
from tools.lexical.bindings import EXPORT_SCHEMA, ROW_FIELDS, accepted, validate_payload


def export(root, output):
    no_network()
    tick = time.perf_counter()
    bindings, _, _ = accepted(root)
    corpus = load_durable_corpus(root)
    catalog = QualifiedChunkCatalog(root, corpus, selector="config/retrieval-chunks-m3-durable-v1.json")
    artifacts = EmbeddingArtifacts(root, catalog, selector="config/embedding-artifacts-m4-durable-v1.json")
    summary = corpus.catalog.get_corpus_summary()
    if (summary["units"], summary["sections"], summary["membership_edges"]) != (553, 3040, 3727):
        raise ValueError("m6_wrong_corpus")
    rows = []
    for i, row in enumerate(catalog.list_chunks(limit=1000)["items"], 1):
        cid = row["chunk_id"]
        view = artifacts.open_bound_chunk(cid)
        text, binding = embedding_input(view)
        # No source envelope flattening: the existing source-only contract is reused.
        item = {k: binding[k] for k in ROW_FIELDS - {"text"}}
        item["text"] = text
        rows.append(item)
        if i % 50 == 0:
            print(f"Verified {i}/992 live source-only lexical inputs", flush=True)
    artifacts.check()
    payload = {"schema": EXPORT_SCHEMA, "bindings": bindings, "rows": rows,
               "live_verified_chunks": len(rows)}
    validate_payload(root, payload)
    path = local(root, output)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = encoded(payload)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("m6_export_exists_with_different_content")
    else:
        with path.open("xb") as f:
            f.write(raw)
    print(json.dumps({"status": "PASS", "chunks": len(rows), "units": 553,
                      "bindings": len(bindings), "payload_sha256": sha(raw),
                      "seconds": time.perf_counter() - tick,
                      "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "inference": False}))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    export(args.root.resolve(strict=True), args.output)
