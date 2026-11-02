"""Offline M3 catalog builder. No QA publication, embeddings or retrieval execution."""

import argparse
import importlib.metadata
import json
import resource
import socket
import time
from collections import Counter
from pathlib import Path

from rag_hub.chunk_preparation import ChunkPreparation, write_once
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.retrieval_chunks import from_proposal
from rag_hub.structure_chunking import StructureAwarePilot
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

COMPONENTS = [
    "src/rag_hub/retrieval_chunks.py", "src/rag_hub/chunk_catalog.py",
    "src/rag_hub/structure_chunking.py", "src/rag_hub/chunk_preparation.py",
    "src/rag_hub/chunk_inputs.py", "src/rag_hub/m2_tokenizer.py",
    "tools/chunking/build_catalog.py", "tools/chunking/pyproject.toml", "tools/chunking/uv.lock",
    "config/bge-tokenizer-v1.json",
]


def build(root, output, documents, budget=384, *, engine_factory=StructureAwarePilot,
          component_paths=()):
    start = time.perf_counter()
    paths = [*COMPONENTS, *component_paths]
    components = {p: sha((root / p).read_bytes()) for p in paths}
    corpus = load_verified_corpus(root)
    load_seconds = time.perf_counter() - start
    preparation = ChunkPreparation(corpus)
    tokenizer = PinnedBgeTokenizer(root)
    pilot = engine_factory(preparation, tokenizer)
    config = {"schema": "m3-configuration-1.0", "total_tokens": budget,
              "default_is_provisional_not_quality_winner": True,
              "tokenizer": tokenizer.metadata(), "overlap": 0,
              "components": components, "prefix_policy": "literal_required_source_headings_only"}
    config_id = "chunk-config:" + sha(encode(config))
    units = corpus.catalog.list_units()
    if documents:
        units = [u for u in units if u["document_id"] in documents]
    chunks, outcomes = [], []
    for index, meta in enumerate(units):
        record = preparation.prepare(meta["unit_id"])
        result = pilot.chunk(record, total_tokens=budget)
        proposals = result["chunks"]
        values = [from_proposal(p, meta, config_id).model_dump(mode="json") for p in proposals]
        chunks.extend(values)
        non_indexable = result.get("non_indexable", [])
        status = ("PARTIALLY_BLOCKED" if values else "BLOCKED") if result["unresolved"] else (
            "CHUNKED" if values else "NON_INDEXABLE")
        outcome = {"unit_id": record.unit_id, "document_id": record.document_id,
                   "format": record.format, "chunk_ids": [v["chunk_id"] for v in values],
                   "status": status,
                   "source_coverage": result["source_results"],
                   "unresolved": result["unresolved"], "non_indexable": non_indexable,
                   "source_field_count": len(record.indexable_source_content),
                   "protected_projection_count": len(record.protected_consumable_projections)}
        outcomes.append(outcome)
        if (index + 1) % 25 == 0:
            print(f"Prepared/cataloged {index + 1}/{len(units)} units", flush=True)
    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("duplicate_chunk_identity")
    actual_docs = sorted({u["document_id"] for u in units})
    summary = {"schema": "m3-coverage-report-1.0", "authority": "INSPECTION_ONLY",
               "units": len(outcomes), "chunks": len(chunks), "documents": actual_docs,
               "unit_dispositions": dict(Counter(o["status"] for o in outcomes)),
               "lineage_precision": dict(Counter(c["lineage"]["precision"] for c in chunks)),
               "unknown_token_occurrences": sum(len(c["unknown_token_offsets"]) for c in chunks),
               "display_character_accounting": "Per-unit authorized fields, not unique PDF codepoints",
               "no_additional_within_unit_overlap": True,
               "by_document": {d: {
                   "units": sum(o["document_id"] == d for o in outcomes),
                   "chunks": sum(c["document_id"] == d for c in chunks),
                   "unique_sections": len({m["section_id"] for u in units
                                           if u["document_id"] == d for m in u["memberships"]}),
                   "source_characters": sum(s["source_characters"] for o in outcomes
                                            if o["document_id"] == d for s in o["source_coverage"]),
                   "chunked_characters": sum(s["chunked_characters"] for o in outcomes
                                             if o["document_id"] == d for s in o["source_coverage"]),
                   "unresolved_characters": sum(s["unresolved_characters"] for o in outcomes
                                                if o["document_id"] == d for s in o["source_coverage"]),
               } for d in actual_docs}}
    files = {}

    def save(name, raw):
        path = output / name
        write_once(path, raw)
        files[str(path.relative_to(root))] = sha(raw)
        return str(path.relative_to(root))

    chunks_path = save("chunks.jsonl", b"".join(encode(c) + b"\n" for c in chunks))
    units_path = save("unit-outcomes.json", encode(outcomes))
    save("COVERAGE.json", encode(summary))
    assert components == {p: sha((root / p).read_bytes()) for p in paths}
    manifest = {"schema": "retrieval-chunk-catalog-1.0", "authority": "DERIVED_NOT_ADMISSION",
                "documents": actual_docs, "components": components, "files": files,
                "upstream_files": corpus.binding_manifest()["files"],
                "chunks_path": chunks_path, "units_path": units_path,
                "configurations": {config_id: config}, "default_configuration_id": config_id,
                "summary": summary}
    write_once(output / "manifest.json", encode(manifest))
    corpus.catalog.get_corpus_summary()
    runtime = {"load_seconds": load_seconds, "total_seconds": time.perf_counter() - start,
               "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               "rss_units": "bytes_on_macOS", "manifest_sha256": sha(encode(manifest)),
               "packages": {p: importlib.metadata.version(p)
                            for p in ["pydantic", "tokenizers", "langchain-text-splitters"]}}
    return manifest, runtime


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--document", action="append")
    p.add_argument("--selector", type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    output = root / args.output
    attempts = []
    connect = socket.socket.connect

    def offline(sock, address):
        attempts.append(str(address))
        raise RuntimeError("M3_network_not_authorized")

    socket.socket.connect = offline
    try:
        manifest, runtime = build(root, output, args.document)
        assert not attempts
        if args.selector:
            write_once(root / args.selector, encode({
                "schema": "chunk-catalog-selection-1.0",
                "manifest_path": str((output / "manifest.json").relative_to(root)),
                "manifest_sha256": sha(encode(manifest))}))
        print(json.dumps({"summary": manifest["summary"], "runtime": runtime,
                          "network_attempts": attempts}, indent=2), flush=True)
    finally:
        socket.socket.connect = connect


if __name__ == "__main__":
    main()
