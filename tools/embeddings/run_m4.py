"""Generate the exact accepted M3 catalog embeddings offline, with live parents."""

import argparse
import io
import json
import platform
import resource
import socket
import time
from collections import Counter
from importlib.metadata import distributions
from pathlib import Path

import numpy as np

from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.chunk_preparation import write_once
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.embedding_inputs import embedding_id, embedding_input
from rag_hub.local_embeddings import LocalBGE, validate_vectors
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.unified_models import encode, sha

SELECTOR = "config/retrieval-chunks-m3-c14-scope-v2.json"
MANIFEST_SHA = "f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c"
MODEL = "config/m4-embedding-baseline-v1.json"
WORK = "workspace/rag-implementation/v1/m4-embeddings-v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-sha256", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    work = root / WORK
    start = time.perf_counter()
    selected = json.loads((root / SELECTOR).read_bytes())
    if selected["manifest_sha256"] != MANIFEST_SHA:
        raise ValueError("M4_not_the_accepted_M3_release")
    model = LocalBGE(root, configuration=MODEL, expected_sha256=args.model_sha256)
    print("Pinned CPU BGE model loaded, offline", flush=True)
    corpus = load_c14_verified_corpus(root)
    catalog = QualifiedChunkCatalog(root, corpus, selector=SELECTOR)
    rows = catalog.list_chunks(limit=1000)["items"]
    assert len(rows) == 992
    prior = json.loads((root / "workspace/rag-implementation/v1/m3-owner-closure-v1/CHUNK_INPUT_BINDINGS.json").read_bytes())
    prior = {v["chunk_id"]: v for v in prior["bindings"]}
    texts, records, limits, inputs = [], [], [], []
    for i, row in enumerate(rows, 1):
        # open_chunk performs original live source/qualification/parent checks.
        # Do not repeat validate_view (which opens the same large parent again).
        view = catalog.open_chunk(row["chunk_id"])
        text, binding = embedding_input(view)
        assert binding["input_text_sha256"] == prior[row["chunk_id"]]["input_text_sha256"]
        limit = catalog.manifest["configurations"][row["configuration_id"]]["total_tokens"]
        ids = model.token_ids([text], [limit])[0]
        assert len(ids) == row["token_count"]
        binding.update(row_index=i - 1, token_ids_sha256=sha(encode(ids)),
            total_token_limit=limit, embedding_id=embedding_id(
                args.model_sha256, row["chunk_id"], binding["input_text_sha256"]))
        texts.append(text)
        limits.append(limit)
        records.append(binding)
        inputs.append({"chunk_id": row["chunk_id"], "text": text,
                       "authority": "FROZEN_NUMERIC_REPLAY_INPUT_NOT_EVIDENCE_AUTHORIZATION"})
        if i % 50 == 0 or i == len(rows):
            print(f"Prepared live authorized inputs {i}/992", flush=True)
    assert len({r["unit_id"] for r in records}) == 553
    prepared_seconds = time.perf_counter() - start
    # All four larger-token cases + protected examples + prose/table/math scopes.
    sample = sorted({0, len(rows) - 1} | {i for i, r in enumerate(rows)
        if r["token_count"] > 384} | {next(i for i, r in enumerate(rows)
        if r["document_id"] == d) for d in sorted({r["document_id"] for r in rows})}
        | {next(i for i, r in enumerate(rows) if r["source"]["content_type"] == kind)
           for kind in sorted({r["source"]["content_type"] for r in rows})})
    controls = model.verify_cls_normalization([texts[i] for i in sample], [limits[i] for i in sample])
    inference_start = time.perf_counter()
    vectors = []
    for a in range(0, len(texts), 16):
        vectors.append(model.encode(texts[a:a + 16], limits[a:a + 16]))
        if a % 128 == 0:
            print(f"Encoded {min(a + 16, len(texts))}/992", flush=True)
    vectors = np.concatenate(vectors)
    validate_vectors(vectors, 992, 384)
    inference_seconds = time.perf_counter() - inference_start
    # Entire catalog numerical repeat in the same pinned CPU process; separate
    # fresh-process replay is performed by replay_m4.py on frozen inputs later.
    repeat_start = time.perf_counter()
    repeated = np.concatenate([model.encode(texts[a:a + 16], limits[a:a + 16])
                               for a in range(0, len(texts), 16)])
    exact_repeat = bool(np.array_equal(vectors, repeated))
    if not exact_repeat:
        raise ValueError("embedding_same_process_reproduction_failed")
    for record, vector in zip(records, vectors, strict=True):
        record["vector_sha256"] = sha(vector.tobytes())
    release = "m4-bge-v1-" + args.model_sha256[:16]
    dest = root / "data/embeddings" / release
    dest.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    np.save(buffer, vectors, allow_pickle=False)
    payloads = {"vectors.npy": buffer.getvalue(),
        "records.jsonl": b"".join(encode(r) + b"\n" for r in records),
        "inputs.jsonl": b"".join(encode(r) + b"\n" for r in inputs)}
    runtime = {"python": platform.python_version(), "platform": platform.platform(),
        "machine": platform.machine(), "loaded_implementation_sha256": model.loaded_components,
        "packages": dict(sorted((d.metadata["Name"], d.version) for d in distributions()
                                if d.metadata.get("Name")))}
    payloads["runtime.json"] = encode(runtime)
    for name, raw in payloads.items():
        write_once(dest / name, raw)
    catalog.check()
    model.bound.check()
    manifest = {"schema": "embedding-manifest-1.0",
        "authority": "DERIVED_VECTORS_NOT_EVIDENCE_AUTHORIZATION", "release_id": release,
        "model_configuration": {"path": MODEL, "sha256": args.model_sha256},
        "catalog_selector": {"path": SELECTOR, "sha256": sha((root / SELECTOR).read_bytes())},
        "catalog_manifest_sha256": MANIFEST_SHA,
        "chunks": len(records), "units": 553, "documents": 16, "dimension": 384,
        "dtype": "float32", "normalization": "L2", "pooling": "CLS",
        "files": {str((dest / name).relative_to(root)): sha(raw) for name, raw in payloads.items()},
        "records_path": str((dest / "records.jsonl").relative_to(root)),
        "inputs_path": str((dest / "inputs.jsonl").relative_to(root)),
        "vectors_path": str((dest / "vectors.npy").relative_to(root)),
        "future_consumer_requirement": "Vectors/search inputs are not evidence. Rehydrate and validate "
            "the full parent through the accepted M3 reader; preserve qualifications and citations.",
        "retrieval_quality": "NOT_EVALUATED; provisional baseline; comparisons deferred to M9"}
    write_once(dest / "manifest.json", encode(manifest))
    selector = {"schema": "embedding-selection-1.0", "manifest_path": str((dest / "manifest.json").relative_to(root)),
                "manifest_sha256": sha(encode(manifest))}
    write_once(root / "config/embedding-artifacts-m4-v1.json", encode(selector))
    artifacts = EmbeddingArtifacts(root, catalog, selector="config/embedding-artifacts-m4-v1.json")
    for record in records:
        vector, replay_record = artifacts.get_vector(record["chunk_id"])
        assert sha(vector.tobytes()) == record["vector_sha256"] and replay_record == record
    for i in sample:
        artifacts.open_bound_chunk(records[i]["chunk_id"])
    result = {"status": "PASS", "chunks": 992, "units": 553, "shape": list(vectors.shape),
        "per_document": dict(Counter(r["document_id"] for r in records)),
        "per_format": dict(Counter(r["format"] for r in records)),
        "norm_min": float(np.min(np.linalg.norm(vectors, axis=1))),
        "norm_max": float(np.max(np.linalg.norm(vectors, axis=1))),
        "exact_input_hash_matches_M3_closure": 992, "exact_runtime_token_parity": 992,
        "token_max": max(r["tokens_including_specials"] for r in records),
        "budgets": dict(Counter(limits)), "CLS_normalization_controls": controls,
        "same_process_full_repeat_exact": exact_repeat,
        "repeat_seconds": time.perf_counter() - repeat_start,
        "source_preparation_and_load_seconds": prepared_seconds,
        "inference_seconds": inference_seconds, "total_seconds": time.perf_counter() - start,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "manifest_sha256": selector["manifest_sha256"], "release_id": release,
        "new_admissions": 0, "M5_started": False, "retrieval_quality_evaluated": False}
    write_once(work / "GENERATION_RESULTS.json", encode(result))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    def offline(*_args, **_kwargs):
        raise RuntimeError("M4_inference_offline_only")

    socket.socket.connect = offline
    main()
