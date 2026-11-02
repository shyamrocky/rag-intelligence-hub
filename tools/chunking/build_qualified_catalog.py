"""Build a source-bound, opt-in qualified M3 successor. No QA or embeddings."""
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
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.qualified_chunk_catalog import QUALIFIED_CONFIG, SELECTOR
from rag_hub.qualified_chunking import QualifiedChunker
from rag_hub.qualified_preparation import QualifiedPreparation
from rag_hub.retrieval_chunks import from_proposal
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

WORK = "workspace/rag-implementation/v1/m3-qualified-recovery-v1"
PRIOR = "data/chunking/m3-remediation-v1/manifest.json"
BEFORE = "config/retrieval-chunks-m3-remediation-v1.json"
FROZEN = WORK + "/FROZEN_BOUNDARIES.json"
DATA = "data/chunking/m3-qualified-v2"
COMPONENTS = ["src/rag_hub/qualified_preparation.py", "src/rag_hub/qualified_chunking.py",
              "src/rag_hub/qualified_chunk_catalog.py", "tools/chunking/build_qualified_catalog.py",
              WORK + "/AUTHORIZATION.md", FROZEN, PRIOR]


def build(root, output):
    started = time.perf_counter()
    corpus = load_verified_corpus(root)
    old = ChunkCatalog(root, corpus, selector=BEFORE)
    prep = QualifiedPreparation(root, corpus)
    tokenizer = PinnedBgeTokenizer(root)
    chunker = QualifiedChunker(prep, tokenizer)
    components = old.manifest["components"] | {p: sha((root / p).read_bytes()) for p in COMPONENTS}
    metadata = {u["unit_id"]: u for u in corpus.catalog.list_units()}
    frozen = json.loads((root / FROZEN).read_bytes())
    configs = copy.deepcopy(old.manifest["configurations"])
    chunks = [json.loads(l) for l in (root / old.manifest["chunks_path"]).read_text().splitlines()]
    original_ids = {c["chunk_id"] for c in chunks}
    outcomes = old.outcomes()
    by_unit = {o["unit_id"]: o for o in outcomes}
    cases, structure = [], []
    for case in frozen["cases"]:
        uid = case["unit_id"]
        if case.get("deferred"):
            cases.append({**case, "status": "DEFERRED_C14_SCOPE_REVIEW", "new_chunks": 0})
            continue
        prepared = prep.prepare(uid)
        outcome = by_unit[uid]
        fields = prepared["search_sources"]
        if case["case_id"].startswith("M3R"):
            fields = [s for s in fields if s["source_pointer"] == case["source_pointer"]]
            if len(fields) != 1 or sha(fields[0]["text"].encode()) != case["text_sha256"]:
                raise ValueError("frozen_source_field_mismatch")
        else:
            record = prepared["record"]
            projection = record["protected_consumable_projections"][0]["native_source"]["restricted_projection"]
            if projection["projection_sha256"] != case["projection_sha256"]:
                raise ValueError("frozen_protected_projection_mismatch")
        added, residues, field_reports = [], [], []
        for source in fields:
            pointer = source["source_pointer"]
            result = chunker.chunk(prepared, pointer)
            if case.get("cuts") and result["evidence"].get("cuts") not in (None, case["cuts"]):
                raise ValueError("frozen_source_statement_or_prompt_map_disagreement")
            for proposal in result["chunks"]:
                config = {"schema": QUALIFIED_CONFIG, "total_tokens": proposal["budget_limit"],
                    "default_total_tokens": 384, "maximum_selective_exception": 512,
                    "tokenizer": tokenizer.metadata(), "overlap": 0,
                    "prefix_policy": "all_literal_required_source_headings_including_nested_HTML",
                    "authorized_search_fields": [[uid, pointer]], "complete_parent_required": True,
                    "source_and_QA_separate": True, "components": components}
                cid = "chunk-config:" + sha(encode(config))
                configs[cid] = config
                value = from_proposal(proposal, metadata[uid], cid).model_dump(mode="json")
                chunks.append(value)
                added.append(value)
            outcome["unresolved"] = [x for x in outcome["unresolved"] if x["source_pointer"] != pointer]
            outcome["unresolved"].extend(result["unresolved"])
            residues.extend(result["unresolved"])
            accounting = {"source_pointer": pointer, "content_type": source["content_type"],
                "source_characters": result["source_characters"],
                "chunked_characters": sum(p["display_end"] - p["display_start"] for p in result["chunks"]),
                "unresolved_characters": sum(p["display_end"] - p["display_start"] for p in result["unresolved"]),
                "context_only_characters": 0}
            if accounting["source_characters"] != accounting["chunked_characters"] + accounting["unresolved_characters"]:
                raise ValueError("incomplete_qualified_field_accounting")
            existing = next((i for i, v in enumerate(outcome["source_coverage"])
                             if v["source_pointer"] == pointer), None)
            if existing is None:
                outcome["source_coverage"].append(accounting)
            else:
                outcome["source_coverage"][existing] = accounting
            field_reports.append({**accounting, "source_text_sha256": sha(source["text"].encode()),
                "token_counts": [p["token_count"] for p in result["chunks"]],
                "budget_limits": [p["budget_limit"] for p in result["chunks"]],
                "new_chunk_ids": [v["chunk_id"] for v in added if v["source"]["pointer"] == pointer]})
            structure.append({"case_id": case["case_id"], "unit_id": uid, "pointer": pointer,
                              "source_text_sha256": sha(source["text"].encode()), **result["evidence"]})
        if prepared["record"]["protected_consumable_projections"]:
            # Current search accounting must not carry an obsolete zero-source
            # diagnosis as if it were a present unit-level restriction.
            outcome["historical_preparation_limits"] = outcome.pop("non_indexable", [])
            outcome["native_preparation_source_field_count"] = outcome["source_field_count"]
            outcome["source_field_count"] = len(outcome["source_coverage"])
            outcome["non_indexable"] = []
            outcome["search_representation_contract"] = "source_only_parent_bound_qualified_projection"
            outcome["unindexed_native_envelopes"] = [
                {"pointer": p["source_pointer"],
                 "reason": "Full warning/label envelope is not embedding source text; "
                           "only explicit primary quotations are search-only derivatives."}
                for p in prepared["record"]["protected_consumable_projections"]]
        if prepared["parent_only_projection_segments"]:
            outcome["protected_projection_parent_only_segments"] = prepared["parent_only_projection_segments"]
        cases.append({"case_id": case["case_id"], "unit_id": uid,
            "status": "FULLY_RECOVERED_SEARCH_FIELDS" if not residues else "PARTIALLY_RECOVERED",
            "new_chunks": len(added), "fields": field_reports,
            "parent_only_projection_segments": prepared["parent_only_projection_segments"],
            "unresolved": residues, "QA_admission_unchanged": "ADMITTED"})
        print(case["case_id"], len(added), "new chunks;", len(residues), "residues", flush=True)
    order = {o["unit_id"]: i for i, o in enumerate(outcomes)}
    chunks.sort(key=lambda c: (order[c["unit_id"]], c["source"]["pointer"], c["source"]["start"]))
    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("duplicate_qualified_chunk")
    for o in outcomes:
        values = [c for c in chunks if c["unit_id"] == o["unit_id"]]
        o["chunk_ids"] = [v["chunk_id"] for v in values]
        if o["unresolved"]:
            o["status"] = "PARTIALLY_BLOCKED" if values else "BLOCKED"
        elif o.get("context_intervals"):
            o["status"] = "CHUNKED_WITH_PARENT_CONTEXT_ONLY_FIELDS"
        else:
            o["status"] = "CHUNKED" if values else "NON_INDEXABLE"
    total_keys = ["source_characters", "chunked_characters", "unresolved_characters", "context_only_characters"]
    docs = old.manifest["documents"]
    new_chunks = [c for c in chunks if c["chunk_id"] not in original_ids]
    summary = {"schema": "m3-qualified-coverage-1.0", "authority": "INSPECTION_ONLY_NOT_QA",
        "units": len(outcomes), "chunks": len(chunks), "units_with_chunks": sum(bool(o["chunk_ids"]) for o in outcomes),
        "documents": docs, "previous_chunks_preserved": len(original_ids), "new_chunks": len(new_chunks),
        "new_chunk_token_distribution": dict(sorted(Counter(c["token_count"] for c in new_chunks).items())),
        "new_chunk_budget_distribution": dict(Counter(configs[c["configuration_id"]]["total_tokens"] for c in new_chunks)),
        "unit_dispositions": dict(Counter(o["status"] for o in outcomes)),
        "by_document": {did: {"units": sum(o["document_id"] == did for o in outcomes),
            "chunks": sum(c["document_id"] == did for c in chunks),
            "unique_sections": old.manifest["summary"]["by_document"][did]["unique_sections"],
            **{k: sum(s.get(k, 0) for o in outcomes if o["document_id"] == did for s in o["source_coverage"]) for k in total_keys}}
            for did in docs},
        "denominator_note": "Per-unit source-display fields; now includes primary protected source quotations. "
            "Context-only quotations and QA commentary not independently indexed; shared source not deduplicated."}
    files = {}

    def save(name, raw):
        path = output / name
        write_once(path, raw)
        files[str(path.relative_to(root))] = sha(raw)
        return str(path.relative_to(root))

    cp = save("chunks.jsonl", b"".join(encode(c) + b"\n" for c in chunks))
    op = save("unit-outcomes.json", encode(outcomes))
    save("COVERAGE.json", encode(summary))
    save("CASE_RESULTS.json", encode({"cases": cases}))
    save("STRUCTURE_EVIDENCE.json", encode({"authority": "EXPOSED_MACHINE_SOURCE_EVIDENCE_NOT_HUMAN_ACCEPTANCE", "fields": structure}))
    save("FROZEN_BOUNDARIES.json", encode(frozen))
    manifest = {"schema": "retrieval-chunk-catalog-1.0", "authority": "DERIVED_NOT_ADMISSION",
        "reader_contract": "qualified-parent-bound-reader-1.0", "documents": docs,
        "components": components, "files": files, "upstream_files": corpus.binding_manifest()["files"],
        "chunks_path": cp, "units_path": op, "configurations": configs,
        "default_configuration_id": old.manifest["default_configuration_id"], "summary": summary,
        "predecessor": {"path": PRIOR, "sha256": sha((root / PRIOR).read_bytes())}}
    for p, h in components.items():
        if sha((root / p).read_bytes()) != h:
            raise ValueError("qualified_component_changed_during_build")
    old.check()
    write_once(output / "manifest.json", encode(manifest))
    return manifest, {"seconds": time.perf_counter() - started,
                      "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path(DATA))
    p.add_argument("--selector", type=Path)
    args = p.parse_args()
    root = Path.cwd()
    original = socket.socket.connect

    def offline(*_args, **_kwargs):
        raise RuntimeError("qualified_M3_offline_only")

    socket.socket.connect = offline
    try:
        manifest, runtime = build(root, root / args.output)
        if args.selector:
            write_once(root / args.selector, encode({"schema": "chunk-catalog-selection-1.0",
                "manifest_path": str(args.output / "manifest.json"), "manifest_sha256": sha(encode(manifest)),
                "reader": "rag_hub.qualified_chunk_catalog.QualifiedChunkCatalog"}))
        print(json.dumps({"summary": manifest["summary"], "runtime": runtime,
                          "manifest_sha256": sha(encode(manifest)), "selector_default": SELECTOR}))
    finally:
        socket.socket.connect = original


if __name__ == "__main__":
    main()
