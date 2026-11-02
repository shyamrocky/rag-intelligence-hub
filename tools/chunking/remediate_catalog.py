"""Opt-in bounded successor: keep all prior Chunk IDs, touch only 22 exceptions."""

import argparse
import copy
import json
import resource
import socket
import time
from collections import Counter
from pathlib import Path

from rag_hub.chunk_catalog import ChunkCatalog
from rag_hub.chunk_preparation import write_once
from rag_hub.chunk_remediation import BoundedRemediator
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.retrieval_chunks import from_proposal
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

WORK = "workspace/rag-implementation/v1/m3-remediation-v1"
REVIEW = WORK + "/FROZEN_CASE_REVIEW.json"


def build(root, output):
    started = time.perf_counter()
    corpus = load_verified_corpus(root)
    prior = ChunkCatalog(root, corpus)
    old_manifest = copy.deepcopy(prior.manifest)
    review = json.loads((root / REVIEW).read_bytes())
    if review["baseline_manifest_sha256"] != sha((root / "data/chunking/m3-corpus-v2/manifest.json").read_bytes()):
        raise ValueError("wrong_remediation_predecessor")
    paths = ["src/rag_hub/chunk_remediation.py", "tools/chunking/remediate_catalog.py", REVIEW,
             "data/chunking/m3-corpus-v2/manifest.json"]
    components = old_manifest["components"] | {p: sha((root / p).read_bytes()) for p in paths}
    tokenizer = PinnedBgeTokenizer(root)
    engine = BoundedRemediator(prior.preparation, tokenizer)
    config = {"schema": "m3-bounded-remediation-config-1.0", "total_tokens": 384,
              "tokenizer": tokenizer.metadata(), "overlap": 0, "components": components,
              "prefix_policy": "literal_required_source_headings_only",
              "source_scope": "original_22_exception_fields_only",
              "no_eligibility_or_authorization_change": True}
    config_id = "chunk-config:" + sha(encode(config))
    configurations = copy.deepcopy(old_manifest["configurations"])
    configurations[config_id] = config
    old_chunks = [json.loads(l) for l in (root / old_manifest["chunks_path"]).read_text().splitlines()]
    outcomes = prior.outcomes()
    by_unit = {o["unit_id"]: o for o in outcomes}
    metadata = {u["unit_id"]: u for u in corpus.catalog.list_units()}
    new_chunks, evidence, results = [], [], []
    records = {}
    for case in review["cases"]:
        uid, pointer = case["unit_id"], case["source_pointer"]
        if uid not in records:
            records[uid] = prior.preparation.prepare(uid)
        record = records[uid]
        if case["classification"] == "AUTHORIZATION_RESTRICTED":
            if any(s.source_pointer == pointer for s in record.indexable_source_content):
                raise ValueError("protected_projection_unexpectedly_indexable")
            results.append({**case, "outcome": "UNCHANGED_NON_INDEXABLE"})
            continue
        source = next(s for s in record.indexable_source_content if s.source_pointer == pointer)
        if (sha(source.text.encode()) != case["source_text_sha256"]
                or sha(encode(source.native_source)) != case["native_source_sha256"]):
            raise ValueError("frozen_case_source_or_structure_changed")
        outcome = by_unit[uid]
        target = [u for u in outcome["unresolved"] if u["source_pointer"] == pointer]
        if len(target) != 1 or target[0]["display_start"] != 0 or target[0]["display_end"] != len(source.text):
            raise ValueError("exception_scope_changed_or_not_whole_original_field")
        result = engine.remediate(record, pointer)
        if case["classification"] == "REQUIRES_OWNER_REVIEW" and result["chunks"]:
            raise ValueError("review_required_case_was_automatically_chunked")
        evidence.append({"case_id": case["case_id"], **result["evidence"]})
        values = [from_proposal(p, metadata[uid], config_id).model_dump(mode="json")
                  for p in result["chunks"]]
        new_chunks.extend(values)
        outcome["unresolved"] = [u for u in outcome["unresolved"] if u["source_pointer"] != pointer]
        outcome["unresolved"].extend(result["unresolved"])
        outcome.setdefault("context_intervals", []).extend(result["context_intervals"])
        for row in outcome["source_coverage"]:
            if row["source_pointer"] == pointer:
                row["chunked_characters"] = sum(v["source"]["end"] - v["source"]["start"] for v in values)
                row["unresolved_characters"] = sum(u["display_end"] - u["display_start"] for u in result["unresolved"])
                row["context_only_characters"] = sum(u["display_end"] - u["display_start"] for u in result["context_intervals"])
                if sum(row.get(k, 0) for k in ["chunked_characters", "unresolved_characters", "context_only_characters"]) != row["source_characters"]:
                    raise ValueError("source_field_not_completely_accounted")
        emitted = sum(v["source"]["end"] - v["source"]["start"] for v in values)
        context = sum(u["display_end"] - u["display_start"] for u in result["context_intervals"])
        remaining = sum(u["display_end"] - u["display_start"] for u in result["unresolved"])
        results.append({**case, "outcome": "RESOLVED_AS_PARENT_CONTEXT" if context else (
            "FULLY_RECOVERED" if not remaining else "PARTIALLY_RECOVERED" if emitted else "OWNER_REVIEW_REQUIRED"),
            "new_chunk_ids": [v["chunk_id"] for v in values], "emitted_characters": emitted,
            "parent_context_characters": context, "remaining_characters": remaining,
            "remaining_intervals": result["unresolved"]})
        print(f"{case['case_id']} {case['strategy']}: {len(values)} new chunks; {remaining} unresolved chars", flush=True)
    units_order = {o["unit_id"]: i for i, o in enumerate(outcomes)}
    chunks = sorted(old_chunks + new_chunks, key=lambda c: (
        units_order[c["unit_id"]], int(c["source"]["pointer"].rsplit("/", 1)[1]), c["source"]["start"]))
    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("duplicate_remediation_chunk_id")
    for outcome in outcomes:
        values = [c for c in chunks if c["unit_id"] == outcome["unit_id"]]
        outcome["chunk_ids"] = [v["chunk_id"] for v in values]
        if outcome["unresolved"]:
            outcome["status"] = "PARTIALLY_BLOCKED" if values else "BLOCKED"
        elif outcome.get("context_intervals"):
            outcome["status"] = "CHUNKED_WITH_PARENT_CONTEXT_ONLY_FIELDS"
        else:
            outcome["status"] = "CHUNKED" if values else "NON_INDEXABLE"
    documents = old_manifest["documents"]
    summary = {"schema": "m3-remediation-coverage-1.0", "authority": "INSPECTION_ONLY_NOT_QA",
        "units": len(outcomes), "chunks": len(chunks), "documents": documents,
        "previous_chunks_preserved": len(old_chunks), "new_chunks": len(new_chunks),
        "unit_dispositions": dict(Counter(o["status"] for o in outcomes)),
        "lineage_precision": dict(Counter(c["lineage"]["precision"] for c in chunks)),
        "unknown_token_occurrences": sum(len(c["unknown_token_offsets"]) for c in chunks),
        "no_additional_within_unit_overlap": True,
        "display_character_accounting": "Per-unit fields, not unique source codepoints; context separate",
        "by_document": {did: {"units": sum(o["document_id"] == did for o in outcomes),
            "chunks": sum(c["document_id"] == did for c in chunks),
            "unique_sections": old_manifest["summary"]["by_document"][did]["unique_sections"],
            **{key: sum(s.get(key, 0) for o in outcomes if o["document_id"] == did
                        for s in o["source_coverage"]) for key in ["source_characters", "chunked_characters", "unresolved_characters", "context_only_characters"]}}
            for did in documents}}
    files = {}

    def save(name, raw):
        path = output / name
        write_once(path, raw)
        files[str(path.relative_to(root))] = sha(raw)
        return str(path.relative_to(root))

    chunks_path = save("chunks.jsonl", b"".join(encode(c) + b"\n" for c in chunks))
    units_path = save("unit-outcomes.json", encode(outcomes))
    save("COVERAGE.json", encode(summary))
    save("STRUCTURE_EVIDENCE.json", encode({"authority": "SOURCE_BOUND_MACHINE_EVIDENCE_NOT_OWNER_APPROVAL", "fields": evidence}))
    save("CASE_RESULTS.json", encode({"cases": results}))
    save("FROZEN_CASE_REVIEW.json", encode(review))
    for p, h in components.items():
        if sha((root / p).read_bytes()) != h:
            raise ValueError("remediation_component_or_predecessor_changed_during_execution")
    manifest = {"schema": "retrieval-chunk-catalog-1.0", "authority": "DERIVED_NOT_ADMISSION",
        "documents": documents, "components": components, "files": files,
        "upstream_files": corpus.binding_manifest()["files"], "chunks_path": chunks_path,
        "units_path": units_path, "configurations": configurations,
        "default_configuration_id": config_id, "summary": summary,
        "predecessor": {"path": "data/chunking/m3-corpus-v2/manifest.json",
                        "sha256": review["baseline_manifest_sha256"]}}
    write_once(output / "manifest.json", encode(manifest))
    prior.check()
    return manifest, {"seconds": time.perf_counter() - started,
                      "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "rss_units": "bytes_on_macOS", "manifest_sha256": sha(encode(manifest))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("data/chunking/m3-remediation-v1"))
    p.add_argument("--selector", type=Path)
    args = p.parse_args()
    root = Path.cwd()
    original = socket.socket.connect

    def offline(sock, address):
        raise RuntimeError("bounded_M3_is_offline_only")

    socket.socket.connect = offline
    try:
        manifest, runtime = build(root, root / args.output)
        if args.selector:
            write_once(root / args.selector, encode({"schema": "chunk-catalog-selection-1.0",
                "manifest_path": str(args.output / "manifest.json"), "manifest_sha256": sha(encode(manifest))}))
        print(json.dumps({"summary": manifest["summary"], "runtime": runtime}, indent=2), flush=True)
    finally:
        socket.socket.connect = original


if __name__ == "__main__":
    main()
