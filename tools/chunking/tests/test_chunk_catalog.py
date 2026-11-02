"""M3 contracts against the actual gateway and immutable catalog; no fake approvals."""

import copy
import json
import tempfile
from pathlib import Path

import pytest

from rag_hub.chunk_catalog import ChunkCatalog
from rag_hub.retrieval_chunks import RetrievalChunk, chunk_id
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def corpus():
    return load_verified_corpus(ROOT)


@pytest.fixture(scope="module")
def catalog(corpus):
    return ChunkCatalog(ROOT, corpus, selector="config/retrieval-chunks-c01-v2.json")


def test_c01_counts_and_accepted_m2_preserved(catalog):
    assert catalog.manifest["summary"]["chunks"] == 88
    assert len(catalog.outcomes()) == 61
    old = [json.loads(line) for line in (ROOT / "data/chunking/m2-c01-v3/config-384/unit-results.jsonl"
                                       ).read_text().splitlines()]
    expected = {(c["unit_id"], c["source_pointer"], c["display_start"], c["display_end"]): c
                for u in old for c in u["chunks"]}
    for row in catalog.list_chunks(limit=1000)["items"]:
        s = row["source"]
        c = expected[(row["unit_id"], s["pointer"], s["start"], s["end"])]
        assert row["lineage"] == c["lineage"]
        assert s["text_sha256"] == c["source_text_sha256"]
        assert row["token_count"] == c["token_count"]
    assert len(expected) == 88


def test_all_c01_chunks_live_source_and_coverage(catalog):
    chunks = catalog.list_chunks(limit=1000)["items"]
    characters = 0
    for c in chunks:
        view = catalog.open_chunk(c["chunk_id"])
        assert sha(view["source_slice"].encode()) == c["source"]["text_sha256"]
        assert view["verified_parent"]["consumer"]["llm_context"]["qualification"]["mandatory"]
        characters += len(view["source_slice"])
    assert characters == 65872  # Per-unit fields; shared source is not unique-PDF coverage.
    for outcome in catalog.outcomes():
        for source in outcome["source_coverage"]:
            rows = [c for c in chunks if c["unit_id"] == outcome["unit_id"]
                    and c["source"]["pointer"] == source["source_pointer"]]
            pos = 0
            for r in sorted(rows, key=lambda r: r["source"]["start"]):
                assert r["source"]["start"] == pos
                pos = r["source"]["end"]
            assert pos == source["source_characters"]


def test_bidirectional_many_to_many_and_context_roles(catalog):
    sids = set()
    shared = False
    for o in catalog.outcomes():
        assert catalog.get_unit_chunks(o["unit_id"]) == o["chunk_ids"]
        # One traversal per parent avoids repeatedly checking the same 100+
        # bibliography memberships for every child; all child spans are tested above.
        for c in o["chunk_ids"][:1]:
            expected = catalog.corpus.catalog.get_unit_sections(o["unit_id"])
            edges = catalog.get_chunk_sections(c)
            assert [(e["section_id"], e["role"], e["native_role"]) for e in edges] == [
                (e["section_id"], e["role"], e["native_role"]) for e in expected]
            for e in edges:
                sid = e["section_id"]
                sids.add(sid)
                reverse = catalog.get_section_chunks(sid)
                assert any(r["unit_id"] == o["unit_id"] and c in r["chunk_ids"] for r in reverse)
                assert e["context_only_in_unit"] == (e["role"] in {
                    "required_context", "supporting_heading"})
                shared |= len({r["unit_id"] for r in reverse}) > 1
    assert len(sids) == 277 and shared


@pytest.mark.parametrize("field,value", [
    ("configuration_id", "wrong-configuration"), ("unit_id", "forged-publication:unit"),
    ("document_id", "C02"), ("token_count", 383),
])
def test_ids_bind_changes(catalog, field, value):
    row = catalog.list_chunks(limit=1)["items"][0]
    old = row["chunk_id"]
    row[field] = value
    assert chunk_id(row) != old
    with pytest.raises(ValueError, match="unknown_chunk"):
        catalog.open_chunk(chunk_id(row))


@pytest.mark.parametrize("mutation", ["text", "warning", "context", "publication", "spans", "heading"])
def test_forged_or_stripped_view_rejected(catalog, mutation):
    c = catalog.list_chunks(limit=1)["items"][0]
    view = catalog.open_chunk(c["chunk_id"])
    if mutation == "text":
        view["source_slice"] += "forged"
    elif mutation == "warning":
        view["verified_parent"]["consumer"]["llm_context"]["qualification"] = {}
    elif mutation == "context":
        view["verified_parent"]["consumer"]["llm_context"]["required_context"] = ["forged"]
    elif mutation == "publication":
        view["verified_parent"]["publication_identity"] = {}
    elif mutation == "spans":
        view["chunk"]["lineage"]["source_spans"] = []
    else:
        view["heading_context"] = ["invented"]
    with pytest.raises(ValueError, match="altered_stale"):
        catalog.validate_view(view)


@pytest.mark.parametrize("status", ["HOLD", "EXCLUDED"])
def test_no_restricted_section_fallback(catalog, status):
    sid = catalog.corpus.catalog.list_sections("C01", filters={"admission_status": status},
                                             limit=1)["items"][0]["section_id"]
    assert catalog.get_section_chunks(sid) == []
    assert catalog.list_chunks(section_id=sid)["total"] == 0
    with pytest.raises(ValueError, match="unknown_chunk"):
        catalog.open_chunk(sid)


def test_carry_forward_m2_diagnostics(catalog):
    # 384 leaves the abstract intact. Whole native projections still carry parent citations.
    rows = catalog.list_chunks(limit=1000)["items"]
    assert any(r["lineage"]["precision"].startswith("AUTHORIZED") for r in rows)
    unk = [r for r in rows if r["unknown_token_offsets"]]
    assert sum(len(r["unknown_token_offsets"]) for r in unk) == 2
    view = catalog.open_chunk(unk[0]["chunk_id"])
    assert "⋆" in view["source_slice"]
    assert all(r["review_notes"] for r in unk)


def test_expired_publication_warning_is_live(catalog):
    # Unchanged eight historical parents now carry the current warning.
    expired = next(u for u in catalog.corpus.catalog.list_units("C01")
                   if "preserved" in u["native_unit_id"])
    view = catalog.open_chunk(catalog.get_unit_chunks(expired["unit_id"])[0])
    assert "EXPIRED" in json.dumps(view["verified_parent"]["consumer"])


@pytest.mark.parametrize("offset,limit", [(-1, 10), (False, 1), (0, 0), (0, 1001)])
def test_invalid_pagination(catalog, offset, limit):
    with pytest.raises(ValueError, match="pagination"):
        catalog.list_chunks(offset=offset, limit=limit)


def test_schema_forbids_detached_source_or_qualification_fields(catalog):
    row = catalog.list_chunks(limit=1)["items"][0]
    for field in ("source_text", "qualification", "qa_observations", "raw_text"):
        with pytest.raises(ValueError):
            RetrievalChunk.model_validate(row | {field: "not-authority"})


def test_public_metadata_is_copy_not_mutable_authorization(catalog):
    row = catalog.list_chunks(limit=1)["items"][0]
    original = copy.deepcopy(row)
    row["lineage"]["source_spans"].clear()
    assert encode(catalog.get_chunk(original["chunk_id"])) == encode(original)


@pytest.mark.parametrize("defect", ["duplicate", "orphan", "wrong_parent", "changed_source",
                                   "stale_hash", "span_outside", "lease_after_load"])
def test_corrupt_catalog_is_not_a_source_authority(catalog, defect):
    with tempfile.TemporaryDirectory(dir=ROOT / "workspace") as directory:
        folder = Path(directory)
        rows = catalog.list_chunks(limit=1000)["items"]
        manifest = copy.deepcopy(catalog.manifest)
        if defect == "duplicate":
            rows.append(copy.deepcopy(rows[0]))
        elif defect == "orphan":
            rows[0]["unit_id"] = "forged-unit"
        elif defect == "wrong_parent":
            rows[0]["parent_binding"]["native_handle"] = "0" * 64
        elif defect == "changed_source":
            rows[0]["source"]["text_sha256"] = "0" * 64
        elif defect == "span_outside":
            rows[0]["source"]["end"] = 10**9
        if defect in {"orphan", "wrong_parent", "changed_source", "span_outside"}:
            old = rows[0]["chunk_id"]
            rows[0]["chunk_id"] = chunk_id(rows[0])
            outcomes = catalog.outcomes()
            for o in outcomes:
                o["chunk_ids"] = [rows[0]["chunk_id"] if c == old else c for c in o["chunk_ids"]]
        else:
            outcomes = catalog.outcomes()
        for key, raw in [("chunks_path", b"".join(encode(r) + b"\n" for r in rows)),
                         ("units_path", encode(outcomes))]:
            file = folder / key
            file.write_bytes(raw)
            manifest[key] = str(file.relative_to(ROOT))
            manifest["files"][manifest[key]] = sha(raw)
        if defect == "stale_hash":
            manifest["files"][manifest["chunks_path"]] = "0" * 64
        mp = folder / "manifest.json"
        mp.write_bytes(encode(manifest))
        sp = folder / "selector.json"
        sp.write_bytes(encode({"manifest_path": str(mp.relative_to(ROOT)),
                              "manifest_sha256": sha(mp.read_bytes())}))
        with pytest.raises(ValueError):
            changed = ChunkCatalog(ROOT, catalog.corpus, selector=str(sp.relative_to(ROOT)))
            if defect == "lease_after_load":
                with (ROOT / manifest["chunks_path"]).open("ab") as stream:
                    stream.write(b"\n")
            changed.open_chunk(rows[0]["chunk_id"])


@pytest.fixture(scope="module")
def full_catalog(corpus):
    return ChunkCatalog(ROOT, corpus)


def test_full_corpus_complete_accounting(full_catalog):
    rows = full_catalog.outcomes()
    assert len(rows) == 550
    assert {r["unit_id"] for r in rows} == {
        u["unit_id"] for u in full_catalog.corpus.catalog.list_units()}
    assert len({r["document_id"] for r in rows}) == 16
    assert {r["format"] for r in rows} == {"pdf", "markdown", "html"}
    assert all(r["chunk_ids"] or r["unresolved"] or r["non_indexable"] for r in rows)
    assert sum(r["protected_projection_count"] for r in rows) == 4
    assert all(r["non_indexable"] for r in rows if r["protected_projection_count"])
    assert len({m["section_id"] for u in full_catalog.corpus.catalog.list_units()
                for m in u["memberships"]}) == 2572


def test_full_corpus_every_source_interval_and_budget(full_catalog):
    from rag_hub.m2_tokenizer import PinnedBgeTokenizer
    from rag_hub.structure_chunking import display_segments, heading_projection, mapped_lineage

    tokenizer = PinnedBgeTokenizer(ROOT)
    for outcome in full_catalog.outcomes():
        record = full_catalog.preparation.prepare(outcome["unit_id"])
        rows = full_catalog.list_chunks(unit_id=record.unit_id, limit=1000)["items"]
        headings = heading_projection(record)
        prefix = "\n".join(h["text"] for h in headings)
        prefix = prefix + "\n\n" if prefix else ""
        assert len(outcome["source_coverage"]) == len(record.indexable_source_content)
        for source in record.indexable_source_content:
            selected = [r for r in rows if r["source"]["pointer"] == source.source_pointer]
            intervals = [(r["source"]["start"], r["source"]["end"]) for r in selected]
            intervals += [(r["display_start"], r["display_end"]) for r in outcome["unresolved"]
                          if r["source_pointer"] == source.source_pointer]
            pos = 0
            for a, b in sorted(intervals):
                assert a == pos and b > a
                pos = b
            assert pos == len(source.text)
            for r in selected:
                a, b = r["source"]["start"], r["source"]["end"]
                text = source.text[a:b]
                assert r["source"]["projection_sha256"] == sha(source.text.encode())
                assert r["source"]["text_sha256"] == sha(text.encode())
                assert tokenizer.count(prefix + text) == r["token_count"] <= 384
                assert r["lineage"] == mapped_lineage(record, source, display_segments(source), a, b)
                assert r["heading_context_sha256"] == sha(encode(headings))
        assert not {p["source_pointer"] for p in record.protected_consumable_projections} & {
            r["source"]["pointer"] for r in rows}


@pytest.mark.parametrize("did", [f"C{i:02}" for i in range(1, 17)])
def test_live_chunk_view_per_document(full_catalog, did):
    rows = full_catalog.list_chunks(did, limit=1000)["items"]
    assert rows
    for row in [rows[0], rows[-1]]:
        view = full_catalog.open_chunk(row["chunk_id"])
        assert full_catalog.validate_view(view)
        assert view["verified_parent"]["document_id"] == did
        assert full_catalog.get_unit_chunks(row["unit_id"])


def test_c01_pilot_lineage_and_ids_are_configuration_qualified(catalog, full_catalog):
    a = catalog.list_chunks("C01", limit=1000)["items"]
    b = full_catalog.list_chunks("C01", limit=1000)["items"]
    assert len(a) == len(b) == 88
    for first, second in zip(a, b, strict=True):
        assert first["source"] == second["source"]
        assert first["lineage"] == second["lineage"]
        assert first["unit_id"] == second["unit_id"]
        assert first["chunk_id"] != second["chunk_id"]  # Different bound engine/configuration.


def test_c10_and_protected_markdown_contracts_remain_attached(full_catalog):
    rows = full_catalog.list_chunks("C10", limit=1000)["items"]
    table = next(r for r in rows if r["source"]["content_type"] == "table")
    view = full_catalog.open_chunk(table["chunk_id"])
    llm = view["verified_parent"]["consumer"]["llm_context"]
    assert llm["required_context"] and llm["qa_observations"]
    assert llm["qualification"]["mandatory"]
    forged = copy.deepcopy(view)
    forged["verified_parent"]["consumer"]["llm_context"]["qa_observations"] = []
    with pytest.raises(ValueError):
        full_catalog.validate_view(forged)
    protected = [r for r in full_catalog.outcomes() if r["protected_projection_count"]]
    assert len(protected) == 4
    assert all(r["format"] == "markdown" and r["non_indexable"] for r in protected)
