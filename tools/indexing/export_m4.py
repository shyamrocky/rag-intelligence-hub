"""Read accepted M4 live bindings with its own locked interpreter; never encode."""

import argparse
import json
import resource
import time
from pathlib import Path

from m5_index import UPSTREAM, encoded, local, metadata, no_network, read_bound, sha

from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog


def export(root, output):
    no_network()
    started = time.perf_counter()
    for path, digest in UPSTREAM.items():
        read_bound(root, path, digest)
    corpus = load_durable_corpus(root)
    catalog = QualifiedChunkCatalog(root, corpus,
                                   selector="config/retrieval-chunks-m3-durable-v1.json")
    artifacts = EmbeddingArtifacts(root, catalog,
                                  selector="config/embedding-artifacts-m4-durable-v1.json")
    bindings = (corpus.binding_manifest()["files"] | catalog.bound.fingerprints()
                | artifacts.bound.fingerprints() | UPSTREAM)
    rows = []
    for i, row in enumerate(catalog.list_chunks(limit=1000)["items"]):
        cid = row["chunk_id"]
        vector, record = artifacts.get_vector(cid)
        artifacts.open_bound_chunk(cid)  # Full authority and qualification validation.
        if sha(vector.tobytes()) != record["vector_sha256"] or record["row_index"] != i:
            raise ValueError("m5_live_vector_binding_changed")
        rows.append({"id": cid, "metadata": metadata(record,
            artifacts.manifest["catalog_manifest_sha256"],
            artifacts.manifest["model_configuration"]["sha256"])})
        if i % 100 == 0:
            print(f"Verified {i + 1}/992 live parent/input/vector bindings", flush=True)
    artifacts.check()
    if len(rows) != 992 or corpus.catalog.get_corpus_summary()["units"] != 553:
        raise ValueError("m5_incomplete_live_corpus")
    payload = {"schema": "m5-verified-export-1.0", "bindings": bindings,
               "rows": rows, "verified_live_bindings": len(rows)}
    path = local(root, output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(encoded(payload))
    print(json.dumps({"status": "PASS", "rows": len(rows), "bindings": len(bindings),
                      "payload_sha256": sha(encoded(payload)), "inference": False,
                      "seconds": time.perf_counter() - started,
                      "max_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    export(Path(args.root).resolve(), args.output)
