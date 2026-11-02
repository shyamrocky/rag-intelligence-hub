"""PDF native readback, fail-closed scope boundaries and UI regression checks."""

import json
import socket
from pathlib import Path

import pytest
from streamlit.string_util import clean_text
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import views
from apps.knowledge_preparation.data import PDFWalkthrough, verify_index
from apps.knowledge_preparation.process import STAGES
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_models import sha

ROOT = Path(__file__).resolve().parents[3]


def preparation_app():
    app = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    app._page_hash = calc_hash("knowledge-preparation")
    return app


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("NO_NETWORK_IN_WALKTHROUGH")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def library():
    return PDFWalkthrough(ROOT)


@pytest.fixture(scope="module")
def walkthrough(library):
    return library.for_document("C01")


def test_real_c01_inventory_and_derivative_reconciliation(walkthrough):
    w = walkthrough
    assert w.document["document_id"] == "C01"
    assert w.document["format"] == "pdf"
    assert w.document["counts"] == {"sections": 406, "ADMITTED": 277, "HOLD": 110, "EXCLUDED": 19}
    assert len(w.units) == 61
    assert len(w.chunks) == 88
    assert set(w.embeddings) == set(w.chunks)
    for index in w.indexes.values():
        assert set(index["records"]) == set(w.chunks)
        assert index["status"] == "HASH_VERIFIED_SAVED_EXPORT"
    assert all(u["document_id"] == "C01" for u in w.units)


def test_native_evidence_preserves_context_and_qualifications(walkthrough):
    uid = walkthrough.units[0]["unit_id"]
    value = walkthrough.unit(uid)
    assert value["consumer"]["llm_context"]["qualification"]
    assert "required_context" in value["consumer"]["llm_context"]
    assert value["citation_locators"]
    assert walkthrough.data.validate_unit(value) is not False
    cid = next(cid for cid, row in walkthrough.chunks.items() if row["unit_id"] == uid)
    view = walkthrough.chunk(cid)
    assert view["verified_parent"]["unit_id"] == uid
    assert sha(view["source_slice"].encode()) == view["chunk"]["source"]["text_sha256"]


@pytest.mark.parametrize("kind", ["unit", "chunk"])
def test_other_documents_or_arbitrary_ids_cannot_be_opened(walkthrough, kind):
    with pytest.raises(ValueError, match="outside_selected_document"):
        getattr(walkthrough, kind)("C02-untrusted")


def index_fixture(tmp_path, monkeypatch, *, ids=("cid",), input_hash="input", unit="unit"):
    from apps.knowledge_preparation import data
    metadata = {"document_id": "C01", "unit_id": unit, "input_text_sha256": input_hash,
                "qualification_sha256": "qual", "embedding_id": "emb", "vector_sha256": "vec",
                "row_index": 0, "chunk_sha256": "chunk"}
    payload = {"bindings": {}, "rows": [{"id": cid, "metadata": metadata} for cid in ids]}
    raw = json.dumps(payload).encode()
    (tmp_path / "payload.json").write_bytes(raw)
    manifest = {"schema": "m5-chroma-1.1", "records": 1, "payload_path": "payload.json",
                "upstream_bindings": {}, "spec": {"payload_sha256": sha(raw), "components": {}}}
    raw = json.dumps(manifest).encode()
    (tmp_path / "manifest.json").write_bytes(raw)
    raw = json.dumps({"manifest_path": "manifest.json", "manifest_sha256": sha(raw)}).encode()
    (tmp_path / "selector.json").write_bytes(raw)
    monkeypatch.setitem(data.INDEXES, "Vector index", ("selector.json", sha(raw)))
    record = metadata | {"unit_id": "unit", "input_text_sha256": "input"}
    return BoundFiles(tmp_path), {"cid": {"unit_id": "unit", "document_id": "C01"}}, {"cid": record}


def test_index_export_valid_fixture(tmp_path, monkeypatch):
    args = index_fixture(tmp_path, monkeypatch)
    assert verify_index(args[0], "Vector index", *args[1:])["records"]["cid"]["unit_id"] == "unit"


@pytest.mark.parametrize("change", ["duplicate", "missing", "wrong_unit", "wrong_input", "tampered"])
def test_index_export_rejects_corruption(tmp_path, monkeypatch, change):
    args = index_fixture(tmp_path, monkeypatch,
                         ids=("cid", "cid") if change == "duplicate" else () if change == "missing" else ("cid",),
                         input_hash="wrong" if change == "wrong_input" else "input",
                         unit="wrong" if change == "wrong_unit" else "unit")
    if change == "tampered":
        (tmp_path / "payload.json").write_text("{}")
    with pytest.raises(ValueError):
        verify_index(args[0], "Vector index", *args[1:])


def test_binding_lease_detects_post_read_mutation(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text("original")
    bound = BoundFiles(tmp_path)
    bound.bind("artifact.json", sha(path.read_bytes()))
    path.write_text("changed")
    with pytest.raises(ValueError, match="snapshot_invalidated"):
        bound.check()


def test_six_pages_and_shared_evidence_selection(library, walkthrough, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    assert not app.exception
    assert [m.value for m in app.metric] == ["4", "312", "428", "428/428"]
    stages = next(e for e in app.sidebar.expander if e.label == "Preparation stages")
    assert stages.proto.expanded
    assert [p.label for p in stages.get("page_link")] == [
        "Sources", "Parsing & Evidence", "Chunks & Lineage", "Embeddings & Indexes", "Validation & Publications"]
    assert app.sidebar.get("page_link")[0].label == "New chat"
    assert app.sidebar.get("page_link")[1].label == "Knowledge Preparation"
    assert [link.label for link in app.sidebar.get("page_link")][-6:] == [
        "Knowledge Retrieval", "Offline Retrieval Evaluation", "Pre-Generation", "Generation",
        "Post-Generation Evaluation", "Human Review"]
    assert any(link.label == "Open Master Dashboard ↗" for link in app.sidebar.get("link_button"))
    assert not any(x.label == "Follow evidence unit" for x in app.selectbox)
    app._page_hash = calc_hash("parsing-evidence")
    app.run()
    selector = next(x for x in app.selectbox if x.label == "Choose evidence unit")
    uid = walkthrough.units[1]["unit_id"]
    selector.select(uid).run()
    for route in ["sources", "parsing-evidence", "chunks-lineage", "embeddings-indexes", "validation-publications"]:
        app._page_hash = calc_hash(route)
        app.run()
        assert not app.exception
        assert app.session_state["kp_unit"] == uid
        title = app.title[0].value
        backbone = next(e for e in app.main.expander if e.label == "Technical backbone")
        assert not backbone.proto.expanded
        assert {"Technology", "What it does", "Saved output", "Verification"} <= set(
            backbone.dataframe[0].value.columns)
        assert not backbone.selectbox
        assert not backbone.button
        if title == "Embeddings & Indexes":
            assert set(backbone.dataframe[0].value.Technology) == {
                "Sentence Transformers + BGE", "Persistent ChromaDB", "rank_bm25 · BM25Okapi"}
            assert any("does not fuse rankings or create a hybrid embedding" in x.value for x in backbone.info)
        if title == "Parsing & Evidence":
            assert set(backbone.dataframe[0].value.Stage) == {"Parse", "Normalize", "QA & Verified Evidence"}
            assert set(backbone.dataframe[1].value.Source) == {"C01", "C02", "C06", "C14"}
        assert any(m.value == f"Focus: {views.FOCUS[title]}" for m in app.markdown)
        assert any(c.value == f"Workspace / [Knowledge Preparation](/knowledge-preparation) / {title}" for c in app.caption)
        assert any(link.label == "← Knowledge Preparation overview" for link in app.get("page_link"))
        expected = {
            "parsing-evidence": ["Inspect parsed blocks", "Inspect canonical Sections", "Inspect evidence unit"],
            "chunks-lineage": ["Inspect individual records"],
            "embeddings-indexes": ["Inspect individual records"],
            "validation-publications": ["Inspect evidence validation"],
        }.get(route, [])
        for label in expected:
            panel = next(e for e in app.expander if e.label == label)
            assert not panel.proto.expanded
        if route == "parsing-evidence":
            panel = next(e for e in app.expander if e.label == "Inspect evidence unit")
            assert panel.selectbox[0].label == "Choose evidence unit"
            assert any(h.value == "Verified source content" for h in panel.subheader)
        if route == "chunks-lineage":
            panel = next(e for e in app.expander if e.label == "Inspect individual records")
            assert [x.label for x in panel.selectbox] == ["Follow evidence unit", "Related retrieval chunk"]
            assert any(h.value == "Complete parent and source obligations" for h in panel.subheader)
        if route == "validation-publications":
            panel = next(e for e in app.expander if e.label == "Inspect evidence validation")
            assert panel.selectbox[0].value == uid
            assert any("NATIVE_VALIDATED" in x.value for x in panel.success)
            assert not panel.warning
    assert not any("generate" in b.label.lower() or "rebuild" in b.label.lower() for b in app.button)


def test_overview_scope_and_stage_links(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    assert not app.exception
    labels = [x.label for x in app.get("page_link")]
    for label in ["Acquire", "Parse", "Normalize", "QA & Verified Evidence", "Prepare & Chunk",
                  "Embed & Index", "Validate & Publish"]:
        assert label in labels
    assert len([b for b in app.button if b.label == "Inspect source →"]) == 4
    assert next(h.value for h in app.subheader) == "Preparation pipeline"
    controls = {x.label: x for x in app.selectbox}
    assert controls["Format"].options == ["All formats", "PDF"]
    controls["Format"].select("PDF").run()
    assert [m.value for m in app.metric] == ["4", "312", "428", "428/428"]
    source = next(x for x in app.selectbox if x.label == "Source")
    source.select("C01").run()
    assert not app.exception
    assert [m.value for m in app.metric] == ["1", "61", "88", "88/88"]
    assert any(c.value.startswith("Showing: C01") for c in app.caption)
    breakdown = next(frame.value for frame in app.dataframe if "Disposition" in frame.value.columns)
    assert list(breakdown["Sections"]) == [406, 277, 110, 19]
    assert any("409 parsed blocks → 406 canonical Sections → 277 admitted Sections" in c.value
               for c in app.caption)
    next(x for x in app.selectbox if x.label == "Source").select("All matching sources").run()
    assert any(c.value.startswith("Showing: PDF · All sources") for c in app.caption)
    # Scope survives a visit to detail and back; no placeholder evidence control returns.
    app._page_hash = calc_hash("sources")
    app.run()
    app._page_hash = calc_hash("knowledge-preparation")
    app.run()
    assert not app.exception
    assert app.session_state["kp_scope_format"] == "PDF"
    assert not any(x.label == "Follow evidence unit" for x in app.selectbox)


def test_all_pdf_inventory_reconciles(library):
    assert [d["document_id"] for d in library.documents] == ["C01", "C02", "C06", "C14"]
    assert sum(d["counts"]["sections"] for d in library.documents) == 2425
    assert sum(d["counts"]["ADMITTED"] for d in library.documents) == 1991
    assert sum(d["counts"]["HOLD"] for d in library.documents) == 358
    assert sum(d["counts"]["EXCLUDED"] for d in library.documents) == 76
    assert len(library.units) == 312
    assert len(library.chunks) == len(library.embeddings) == 428
    assert all(d["format"] == "pdf" for d in library.documents)


def test_parsed_blocks_are_bound_metadata_not_sections_or_source_text(library):
    expected = {"C01": 409, "C02": 459, "C06": 1271, "C14": 471}
    for did, total in expected.items():
        scope = library.for_document(did)
        parsed = scope.parsed
        assert parsed["status"] == "HASH_VERIFIED_METADATA"
        assert parsed["total"] == sum(parsed["types"].values()) == total
        assert all(set(row) == {"Block ID", "Type", "Sequence", "Source location"}
                   for row in parsed["rows"])
        assert parsed["sha256"] == library.data.binding_fingerprints[parsed["path"]]
    assert library.for_document("C01").parsed["total"] != library.for_document("C01").document["counts"]["sections"]


def test_process_boundaries_keep_ingestion_before_m0():
    assert [s["title"] for s in STAGES] == ["Acquire", "Parse", "Normalize", "QA & Verified Evidence",
                                           "Prepare & Chunk", "Embed & Index", "Validate & Publish"]
    assert all("M0" not in s["milestone"] for s in STAGES[:3])
    assert "before M0" in STAGES[3]["milestone"]
    assert "Already verified" in STAGES[4]["input"]
    assert "M0 contract" in STAGES[4]["milestone"]


@pytest.mark.parametrize("route,title,metric", [("parse", "Parse", "409"),
                                               ("normalize", "Normalize", "406"),
                                               ("qa-evidence", "QA & Verified Evidence", "277")])
def test_direct_stage_routes_show_exact_process_step(library, monkeypatch, route, title, metric):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash(route)
    app.run()
    assert not app.exception
    assert next(t.value for t in app.title) == title
    backbone = next(e for e in app.main.expander if e.label == "Technical backbone")
    assert not backbone.proto.expanded
    assert set(backbone.dataframe[0].value.Stage) == {title}
    assert any(m.value == f"Focus: {views.FOCUS[title]}" for m in app.markdown)
    assert any(c.value == f"Workspace / [Knowledge Preparation](/knowledge-preparation) / {title}" for c in app.caption)
    assert app.metric[0].value == metric
    assert any(c.value == f"Current process stage · {title}" for c in app.caption)
    labels = [x.label for x in app.get("page_link")]
    assert any(label.startswith("← ") for label in labels)
    assert any(label.endswith(" →") for label in labels)
    controls = [x.label for x in app.selectbox]
    assert ("Choose evidence unit" in controls) == (title == "QA & Verified Evidence")
    assert "Follow evidence unit" not in controls
    label = {"Parse": "Inspect parsed blocks", "Normalize": "Inspect canonical Sections",
             "QA & Verified Evidence": "Inspect evidence unit"}[title]
    panel = next(e for e in app.expander if e.label == label)
    assert not panel.proto.expanded
    assert panel.dataframe
    assert not panel.metric
    if title == "Parse":
        assert any("not a PDF page number" in c.value for c in app.caption)
        assert any(c.value == "Records 1–25 of 409 · Page 1 of 17" for c in app.caption)
        assert any(label == "Next: Normalize →" for label in labels)
        assert app.button(key="kp_block_page_previous").disabled
        app.button(key="kp_block_page_next").click().run()
        assert not app.exception
        assert any(c.value == "Records 26–50 of 409 · Page 2 of 17" for c in app.caption)
        assert len(next(f.value for f in app.dataframe if "Block ID" in f.value.columns)) == 25


@pytest.mark.parametrize("did,units,chunks", [("C01", 61, 88), ("C02", 50, 106),
                                             ("C06", 128, 140), ("C14", 73, 94)])
def test_every_pdf_native_parent_and_exports(library, did, units, chunks):
    scope = library.for_document(did)
    assert len(scope.units) == units
    assert len(scope.chunks) == len(scope.embeddings) == chunks
    assert scope.profile["document"]["document_id"] == did
    for index in scope.indexes.values():
        assert set(index["records"]) == set(scope.chunks)
    parent = scope.unit(scope.units[0]["unit_id"])
    assert parent["document_id"] == did
    assert parent["consumer"]["llm_context"]["qualification"]
    view = scope.chunk(next(iter(scope.chunks)))
    assert view["verified_parent"]["document_id"] == did


def test_non_pdf_and_cross_document_selection_rejected(library):
    with pytest.raises(ValueError, match="outside_pdf_scope"):
        library.for_document("C04")
    c01, c02 = library.for_document("C01"), library.for_document("C02")
    with pytest.raises(ValueError, match="outside_selected_document"):
        c01.unit(c02.units[0]["unit_id"])
    with pytest.raises(ValueError, match="outside_selected_document"):
        c01.chunk(next(iter(c02.chunks)))


def test_document_switch_resets_children_and_inventory_navigation(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app.button(key="kp-inspect-C02").click().run()
    assert not app.exception
    assert app.session_state["kp_document"] == "C02"
    assert next(t.value for t in app.title) == "Sources"
    app._page_hash = calc_hash("parsing-evidence")
    app.run()
    c02 = library.for_document("C02")
    uid = c02.units[1]["unit_id"]
    next(x for x in app.selectbox if x.label == "Choose evidence unit").select(uid).run()
    next(x for x in app.selectbox if x.label == "Selected PDF source").select("C14").run()
    assert not app.exception
    assert app.session_state["kp_unit"] in library.for_document("C14").unit_ids
    assert app.session_state["kp_unit"] != uid
    assert app.session_state["kp_section_page"] == 1
    app._page_hash = calc_hash("chunks-lineage")
    app.run()
    assert not app.exception
    assert app.session_state["kp_chunk"] in library.for_document("C14").chunks


def test_loader_failure_displays_closed_state(monkeypatch):
    def broken():
        raise ValueError("synthetic_integrity_failure")
    monkeypatch.setattr(views, "load", broken)
    app = preparation_app().run()
    assert not app.exception
    assert any("failed validation" in e.value for e in app.error)
    assert not app.metric


def test_sources_reformat_preserves_metadata_and_publisher_link(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash("sources")
    app.run()
    assert not app.exception
    assert any("Focus: Original document, acquisition, permissions and provenance." in m.value
               for m in app.markdown)
    fields = {row["Field"]: row["Value"] for frame in app.dataframe if "Field" in frame.value.columns
              for row in frame.value.to_dict("records")}
    assert set(fields) == {"Document", "Publisher", "Version", "Format", "Language",
                           "File size (bytes)", "Rights", "Captured at"}
    assert fields["Document"] == "C01"
    source = library.for_document("C01").document["source"]
    assert source["acquisition_basis"] in [i.value for i in app.info]
    assert source["title"] in [h.value for h in app.subheader]
    assert any(e.label == "Technical provenance — frozen source" for e in app.expander)
    assert any(x.label == "Open publisher source ↗" and x.url == source["canonical_url"]
               for x in app.get("link_button"))
    assert any(x.label == "Next: Parse →" for x in app.get("page_link"))
    app._page_hash = calc_hash("parse")
    app.run()
    assert not app.exception
    assert app.session_state["kp_selected_document"] == "C01"


@pytest.mark.parametrize("route,key,last", [("parse", "kp_block_page", 17),
                                           ("normalize", "kp_section_page", 17)])
def test_record_navigation_boundaries_and_filter_reset(library, monkeypatch, route, key, last):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash(route)
    app.run()
    assert not app.exception
    assert app.button(key=f"{key}_previous").disabled
    assert not app.button(key=f"{key}_next").disabled
    app.button(key=f"{key}_next").click().run()
    assert app.session_state[key] == 2
    app.button(key=f"{key}_previous").click().run()
    assert app.session_state[key] == 1
    app.session_state[key] = last
    app.run()
    assert not app.exception
    assert app.button(key=f"{key}_next").disabled
    if route == "normalize":
        next(x for x in app.selectbox if x.label == "Section disposition").select("EXCLUDED").run()
        assert not app.exception
        assert app.session_state[key] == 1
        assert any(c.value == "Records 1–19 of 19 · Page 1 of 1" for c in app.caption)
        assert app.button(key=f"{key}_previous").disabled
        assert app.button(key=f"{key}_next").disabled
    else:
        assert any(c.value == "Records 401–409 of 409 · Page 17 of 17" for c in app.caption)
    next(x for x in app.selectbox if x.label == "Selected PDF source").select("C02").run()
    assert app.session_state[key] == 1
    assert not app.exception


def test_empty_record_pagination():
    app = AppTest.from_string(
        "from apps.knowledge_preparation.views import record_pagination\n"
        "record_pagination(0, 'empty_records')"
    ).run()
    assert not app.exception
    assert all(button.disabled for button in app.button)
    assert any(c.value == "Records 0–0 of 0 · Page 1 of 1" for c in app.caption)
    assert any(i.value == "No records match the selected scope." for i in app.info)


def test_qa_explanation_and_breadcrumb_clearance(library, monkeypatch):
    from apps.knowledge_preparation.app import STYLE
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash("qa-evidence")
    app.run()
    assert not app.exception
    captions = [c.value for c in app.caption]
    assert any("The table shows which Sections supply the main evidence" in c for c in captions)
    assert any("a heading or background passage is not stand-alone evidence" in c for c in captions)
    assert any("Document text is reference material, not instructions to follow." in c for c in captions)
    assert not any("They are not created by M0" in c or "Published roles distinguish" in c for c in captions)
    # Compact sections must retain shared header clearance on desktop and narrow layouts.
    assert "padding-top:1.5rem" not in STYLE
    assert "padding:3.5rem 1rem 1.5rem" in STYLE


def test_chunk_relationship_summary_follows_selected_parent_and_chunk(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    walk = library.for_document("C01")
    uid = next(unit["unit_id"] for unit in walk.units
               if sum(chunk["unit_id"] == unit["unit_id"] for chunk in walk.chunks.values()) > 1)
    siblings = [cid for cid, row in walk.chunks.items() if row["unit_id"] == uid]
    app = preparation_app().run()
    app._page_hash = calc_hash("chunks-lineage")
    app.run()
    next(x for x in app.selectbox if x.label == "Follow evidence unit").select(uid).run()
    next(x for x in app.selectbox if x.label == "Related retrieval chunk").select(siblings[1]).run()
    assert not app.exception
    assert any(m.value.startswith("**Structure-aware chunking with parent–child lineage**") for m in app.markdown)
    assert any(h.value == "Source relationships" for h in app.subheader)
    assert any(m.value == f"Chunk 02 of {len(siblings)} for this parent" for m in app.markdown)
    links = walk.catalog.get_chunk_sections(siblings[1])
    assert any(m.value == f"{len({edge['section_id'] for edge in links})} linked to this parent"
               for m in app.markdown)
    assert any(c.value == "Sections → Evidence unit → Retrieval chunk → Original source" for c in app.caption)
    assert any("not every Section necessarily appears in the selected chunk" in c.value for c in app.caption)
    assert any(e.label == "Technical details — chunk lineage" for e in app.expander)
    assert any(t.value == clean_text(walk.chunk(siblings[1])["source_slice"]) for t in app.text)


@pytest.mark.parametrize("did", ["C01", "C02", "C06", "C14"])
def test_saved_block_section_unit_chunk_relationships(library, did):
    walk = library.for_document(did)
    bid = walk.parsed["rows"][0]["Block ID"]
    result = walk.related_items(block_id=bid)
    assert result["mapping_status"] == "AVAILABLE"
    for row in result["rows"]:
        assert bid in row["block_ids"]
        section = walk.data.section(row["section_id"])
        assert section["document_id"] == did
        assert set(row["unit_ids"]) == set(section["unit_ids"])
        assert all(walk.chunks[cid]["unit_id"] in row["unit_ids"] for cid in row["chunk_ids"])
        reverse = walk.related_items(section_id=row["section_id"])
        assert reverse["rows"] == [row]
        assert "source_content" not in row and "text" not in row


@pytest.mark.parametrize("status", ["HOLD", "EXCLUDED"])
def test_unadmitted_sections_have_recorded_stop_reason(library, status):
    walk = library.for_document("C01")
    sid = walk.data.sections("C01", status=status)["items"][0]["Section ID"]
    row = walk.related_items(section_id=sid)["rows"][0]
    assert row["status"] == status
    assert row["unit_ids"] == row["chunk_ids"] == []
    assert f"No authorized evidence unit: {status}" in row["reason"]


def test_related_items_reject_foreign_ids_and_expose_missing_mapping(library, monkeypatch):
    walk = library.for_document("C01")
    foreign = library.for_document("C02")
    with pytest.raises(ValueError, match="outside_selected_document"):
        walk.related_items(block_id=foreign.parsed["rows"][0]["Block ID"])
    foreign_sid = foreign.data.sections("C02")["items"][0]["Section ID"]
    with pytest.raises(ValueError, match="outside_selected_document"):
        walk.related_items(section_id=foreign_sid)
    bid = walk.parsed["rows"][0]["Block ID"]
    path = "data/normalized/pdf/four-pdf-poc-v1/C01/sections.json"
    monkeypatch.setattr(walk.data, "binding_fingerprints",
                        {p: h for p, h in walk.data.binding_fingerprints.items() if p != path})
    result = walk.related_items(block_id=bid)
    assert result["mapping_status"] == "UNAVAILABLE" and not result["rows"]
    assert "Mapping unavailable" in result["message"]


def test_related_panels_and_selection_preserve_other_controls(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash("parsing-evidence")
    app.run()
    assert not app.exception
    assert len([s for s in app.subheader if s.value == "Related items"]) == 2
    assert any(s.label == "Choose evidence unit" for s in app.selectbox)
    blocks = next(s for s in app.selectbox if s.label == "Select block on this page")
    blocks.select_index(1).run()
    assert not app.exception
    assert app.session_state["kp_related_block"] == library.for_document("C01").parsed["rows"][1]["Block ID"]
    app.button(key="kp_block_page_next").click().run()
    assert not app.exception
    assert app.session_state["kp_related_block"] == library.for_document("C01").parsed["rows"][25]["Block ID"]
    next(s for s in app.selectbox if s.label == "Section disposition").select("HOLD").run()
    assert not app.exception
    assert any("No authorized evidence unit: HOLD" in reason for frame in app.dataframe
               if "Recorded reason / relationship" in frame.value.columns
               for reason in frame.value["Recorded reason / relationship"])
    assert len([e for e in app.expander if e.label == "Technical details — related item IDs"]) == 2


def test_chunk_policy_uses_full_corpus_and_survives_pdf_selection(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash("chunks-lineage")
    app.run()
    assert not app.exception
    assert any(m.value == "**Default limit:** 384 BGE tokens · **Approved exceptions:** up to 512 "
               "· **Overlap:** 0" for m in app.markdown)
    assert any("**4 chunks above the usual 384-token limit**" in m.value for m in app.markdown)
    table = next(frame.value for frame in app.dataframe if "Larger chunks" in frame.value.columns)
    assert table["Larger chunks"].sum() == 4
    assert set(table["Actual BGE tokens"]) == {"507, 485", "474", "385"}
    assert set(table["Approved limit"]) == {"512"}
    assert any(str(value).startswith("C16 ·") for value in table["Document"])
    assert any("All published formats · 992 saved chunks" in c.value for c in app.caption)
    assert any("independent of the PDF selected below" in c.value for c in app.caption)
    next(s for s in app.selectbox if s.label == "Selected PDF source").select("C06").run()
    assert not app.exception
    current = next(frame.value for frame in app.dataframe if "Larger chunks" in frame.value.columns)
    assert current.equals(table)


def test_document_handoff_totals_and_context_survive_both_pages(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash("chunks-lineage")
    app.run()
    walk = library.for_document("C01")
    uid = next(u["unit_id"] for u in walk.units
               if sum(c["unit_id"] == u["unit_id"] for c in walk.chunks.values()) > 1)
    cid = [cid for cid, c in walk.chunks.items() if c["unit_id"] == uid][1]
    next(s for s in app.selectbox if s.label == "Follow evidence unit").select(uid).run()
    next(s for s in app.selectbox if s.label == "Related retrieval chunk").select(cid).run()
    assert app.session_state["kp_chunk"] == cid, "Chunk selection must apply before navigation"
    assert app.session_state["kp_selected_chunk"] == cid, "Stable chunk selection must follow the widget"
    expected = "**61 evidence units** → **88 chunks** → **88 saved embeddings** → " \
               "**88 vector-index records** + **88 BM25 records**"
    for route, link in [("embeddings-indexes", "← Back to Chunks & Lineage"),
                        ("chunks-lineage", "View Embeddings & Indexes →")]:
        app._page_hash = calc_hash(route)
        app.run()
        assert not app.exception
        assert any(m.value == expected for m in app.markdown)
        assert any(c.value == "C01 · Selected document totals" for c in app.caption)
        assert any(l.label == link for l in app.get("page_link"))
        assert app.session_state["kp_selected_document"] == "C01"
        assert app.session_state["kp_unit"] == uid
        assert next(s for s in app.selectbox if s.label == "Follow evidence unit").value == uid
        ordinal = next(n for n, unit in enumerate(walk.units, 1) if unit["unit_id"] == uid)
        if route == "chunks-lineage":
            assert any(m.value == f"Evidence {ordinal:02d}" for m in app.markdown)
        else:
            inspection = next(e for e in app.expander if e.label == "Inspect individual records")
            assert not inspection.proto.expanded
            assert [s.label for s in inspection.selectbox] == ["Follow evidence unit", "Related retrieval chunk"]
            assert inspection.selectbox[0].value == uid
            assert inspection.selectbox[1].value == cid
            assert any(e.label == "Technical details — exact embedding and index bindings"
                       for e in inspection.expander)
            assert not inspection.metric
        assert app.session_state["kp_chunk"] == cid, (route, app.session_state["kp_selected_chunk"])
    next(s for s in app.selectbox if s.label == "Selected PDF source").select("C02").run()
    assert not app.exception
    assert any(m.value == "**50 evidence units** → **106 chunks** → **106 saved embeddings** → "
               "**106 vector-index records** + **106 BM25 records**" for m in app.markdown)
    app._page_hash = calc_hash("embeddings-indexes")
    app.run()
    assert not app.exception
    assert any(c.value == "C02 · Selected document totals" for c in app.caption)
    app._page_hash = calc_hash("sources")
    app.run()
    assert not any(h.value == "Document preparation summary" for h in app.subheader)


@pytest.mark.parametrize("did,hold,excluded", [("C01", 110, 19), ("C02", 38, 22),
                                              ("C06", 33, 34), ("C14", 177, 1)])
def test_withheld_metadata_reconciles_to_selected_source(library, did, hold, excluded):
    walk = library.for_document(did)
    rows = views.withheld_section_rows(walk)
    assert len(rows) == hold + excluded
    assert sum(r["Status"] == "HOLD" for r in rows) == hold
    assert sum(r["Status"] == "EXCLUDED" for r in rows) == excluded
    assert all(r["Section ID"].startswith(did + ":") for r in rows)
    assert all("text" not in key.lower() or key == "Context only" for r in rows for key in r)


def test_withheld_metadata_fails_closed_and_missing_reasons_are_explicit(monkeypatch, walkthrough):
    assert views.recorded_reason({"Issue / reason": "—"}) == "Reason not recorded."
    assert views.recorded_reason({}) == "Reason not recorded."
    assert views.recorded_reason({"Issue / reason": "recorded observation"}) == "recorded observation"
    monkeypatch.setattr(walkthrough.data, "sections", lambda *_a, **_kw: {"total": 0, "items": []})
    with pytest.raises(ValueError, match="withheld_section_count_mismatch"):
        views.withheld_section_rows(walkthrough)


def test_validation_section_outcomes_and_withholding_drilldown(library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: library)
    app = preparation_app().run()
    app._page_hash = calc_hash("validation-publications")
    app.run()
    assert not app.exception
    assert any(m.value == "**406 canonical Sections** → **277 admitted** · **110 HOLD** · **19 excluded**"
               for m in app.markdown)
    reasons = next(f.value for f in app.dataframe if "Recorded QA reason" in f.value.columns)
    assert reasons.groupby("Status")["Sections"].sum().to_dict() == {"EXCLUDED": 19, "HOLD": 110}
    assert reasons.loc[reasons.Status == "EXCLUDED", "Recorded QA reason"].tolist() == [
        "EXCLUDED_NON_KNOWLEDGE: source-backed page furniture"]
    panel = next(e for e in app.expander if e.label == "Inspect withheld Sections")
    assert not panel.proto.expanded
    assert panel.dataframe[0].value.shape[0] == 25
    assert "Section ID" not in panel.dataframe[0].value.columns
    assert app.button(key="kp_withheld_page_previous").disabled
    app.button(key="kp_withheld_page_next").click().run()
    assert any(c.value == "Records 26–50 of 129 · Page 2 of 6" for c in app.caption)
    next(s for s in app.selectbox if s.label == "Withheld Section status").select("EXCLUDED").run()
    assert app.session_state["kp_withheld_page"] == 1
    panel = next(e for e in app.expander if e.label == "Inspect withheld Sections")
    assert len(panel.dataframe[0].value) == 19
    assert set(panel.dataframe[0].value.Status) == {"EXCLUDED"}
    assert app.button(key="kp_withheld_page_next").disabled
    assert any(l.label == "Open QA & Verified Evidence →" for l in panel.get("page_link"))
    assert any(m.value == "Frozen source → QA-authorized evidence → Retrieval chunks → Saved embeddings & search indexes"
               for m in app.markdown)
    assert not any("M3 chunks" in m.value or "M4 embeddings" in m.value for m in app.markdown)
    next(s for s in app.selectbox if s.label == "Selected PDF source").select("C14").run()
    assert not app.exception
    assert app.session_state["kp_withheld_page"] == 1
    assert app.session_state["kp_withheld_status"] == "All"
    assert any(m.value == "**471 canonical Sections** → **293 admitted** · **177 HOLD** · **1 excluded**"
               for m in app.markdown)




@pytest.fixture(scope="module")
def preparation_library():
    return PDFWalkthrough(ROOT, formats=("pdf", "markdown"))


def test_markdown_published_inventory_and_scope(preparation_library):
    library = preparation_library
    assert [d["document_id"] for d in library.documents] == ["C01", "C02", "C04", "C06", "C14"]
    walk = library.for_document("C04")
    assert walk.document["counts"] == {"sections": 158, "ADMITTED": 154, "EXCLUDED": 4}
    assert walk.parsed["total"] == 215
    assert walk.profile["parser"]["adapter_version"] == "mdx-v1"
    assert len(walk.units) == 86
    assert len(walk.chunks) == len(walk.embeddings) == 209
    assert all(set(index["records"]) == set(walk.chunks) for index in walk.indexes.values())
    assert (len(library.units), len(library.chunks)) == (398, 637)
    assert any(r["Provider / tab"] != "—" for r in walk.parsed["rows"])
    assert all("lines " in r["Source location"] for r in walk.parsed["rows"])
    assert not any("text" in k.lower() or "content" in k.lower() for r in walk.parsed["rows"] for k in r)
    assert len(views.withheld_section_rows(walk)) == 4
    with pytest.raises(ValueError, match="outside_pdf_scope"):
        library.for_document("C03")  # HTML remains outside this UI integration.
    with pytest.raises(ValueError, match="outside_selected_document"):
        walk.unit(library.for_document("C01").units[0]["unit_id"])


def test_markdown_relationships_and_native_authority(preparation_library):
    walk = preparation_library.for_document("C04")
    first = walk.parsed["rows"][0]
    omitted = walk.related_items(block_id=first["Block ID"])
    assert omitted["mapping_status"] == "AVAILABLE"
    assert not omitted["rows"]
    assert "remove_documentation_discovery_instructions" in omitted["message"]
    code = next(r for r in walk.parsed["rows"] if r["Type"] == "code")
    mapped = walk.related_items(block_id=code["Block ID"])
    assert mapped["rows"]
    assert all(r["section_id"].startswith("C04:") for r in mapped["rows"])
    uid = walk.units[0]["unit_id"]
    assert sha(json.dumps(walk.unit(uid), sort_keys=True).encode()) == sha(
        json.dumps(walk.data.verified_unit(uid), sort_keys=True).encode())
    chunk = walk.chunk(next(iter(walk.chunks)))
    assert chunk["verified_parent"]["document_id"] == "C04"
    assert sha(json.dumps(chunk["verified_parent"], sort_keys=True).encode()) == sha(
        json.dumps(walk.unit(chunk["verified_parent"]["unit_id"]), sort_keys=True).encode())


@pytest.mark.parametrize("kind", ["parsed", "normalized", "source_metadata"])
def test_markdown_metadata_identity_tampering_fails_closed(preparation_library, monkeypatch, kind):
    library = preparation_library
    bind = library.bound.bind
    path = f"data/{'normalized' if kind == 'normalized' else 'parsed'}/markdown/C04.json"

    def altered(name, expected):
        value = bind(name, expected)
        if name == path:
            record = json.loads(value)
            if kind == "source_metadata":
                record["source"]["publisher"] = "tampered publisher"
            else:
                record["source"]["raw_sha256"] = "0" * 64
            return json.dumps(record).encode()
        return value

    monkeypatch.setattr(library.bound, "bind", altered)
    with pytest.raises(ValueError, match="mismatch"):
        if kind != "normalized":
            library._parsed_metadata("C04")
        else:
            walk = library.for_document("C04")
            walk.related_items(block_id=walk.parsed["rows"][0]["Block ID"])


def test_markdown_overview_and_all_preparation_pages(preparation_library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: preparation_library)
    app = preparation_app().run()
    assert not app.exception
    assert [m.value for m in app.metric] == ["5", "398", "637", "637/637"]
    fmt = next(s for s in app.selectbox if s.label == "Format")
    assert fmt.options == ["All formats", "MARKDOWN", "PDF"]
    fmt.select("MARKDOWN").run()
    assert app.session_state["kp_selected_document"] == "C04"
    assert [m.value for m in app.metric] == ["1", "86", "209", "209/209"]
    assert any(c.value == "215 parsed blocks → 158 canonical Sections → 154 admitted Sections" for c in app.caption)
    next(s for s in app.selectbox if s.label == "Source").select("C04").run()
    for route in ["sources", "parsing-evidence", "parse", "normalize", "qa-evidence",
                  "chunks-lineage", "embeddings-indexes", "validation-publications"]:
        app._page_hash = calc_hash(route)
        app.run()
        assert not app.exception, route
        assert not app.error, route
        assert app.session_state["kp_selected_document"] == "C04"
        assert next(s for s in app.selectbox if s.label == "Selected source").value == "C04"
        assert not any("created with a default value" in w.value for w in app.warning)
        if route == "sources":
            recorded = preparation_library.for_document("C04").source_metadata
            fields = {r["Field"]: r["Value"] for f in app.dataframe if "Field" in f.value.columns
                      for r in f.value.to_dict("records")}
            assert fields["Format"] == recorded["source_format"] == "markdown_mdx"
            assert fields["Rights"] == recorded["rights_status"]
            assert fields["File size (bytes)"] == str(recorded["byte_size"])
            assert any(i.value == recorded["acquisition_basis"] for i in app.info)
        if route == "parse":
            blocks = next(f.value for f in app.dataframe if "Block ID" in f.value.columns)
            assert {"Language", "Provider / tab", "Code group"} <= set(blocks.columns)
            assert any(c.value == "Records 1–25 of 215 · Page 1 of 9" for c in app.caption)
        if route == "qa-evidence":
            assert any("Markdown/MDX units retain" in i.value for i in app.info)
            assert any(h.value == "Verified source content" for h in app.subheader)
        if route in {"chunks-lineage", "embeddings-indexes"}:
            assert any(m.value == "**86 evidence units** → **209 chunks** → **209 saved embeddings** → "
                       "**209 vector-index records** + **209 BM25 records**" for m in app.markdown)
        if route == "validation-publications":
            assert any(m.value == "**158 canonical Sections** → **154 admitted** · **0 HOLD** · **4 excluded**"
                       for m in app.markdown)
    next(s for s in app.selectbox if s.label == "Selected source").select("C01").run()
    assert not app.error and not app.exception
    assert app.session_state["kp_selected_document"] == "C01"
    assert any(m.value == "**406 canonical Sections** → **277 admitted** · **110 HOLD** · **19 excluded**"
               for m in app.markdown)


@pytest.fixture(scope="module")
def full_preparation_library():
    return PDFWalkthrough(ROOT, formats=("pdf", "markdown", "html"))


@pytest.mark.parametrize("did,sections,units,chunks", [
    ("C03", 24, 7, 15), ("C05", 17, 2, 15), ("C07", 60, 18, 41),
    ("C08", 77, 21, 55), ("C09", 69, 24, 54), ("C10", 38, 15, 29),
    ("C11", 26, 10, 16), ("C12", 31, 11, 21), ("C13", 35, 10, 13),
    ("C15", 17, 8, 9), ("C16", 63, 29, 87),
])
def test_html_saved_inventory_and_native_authority(full_preparation_library, did, sections, units, chunks):
    library = full_preparation_library
    walk = library.for_document(did)
    assert walk.document["format"] == "html"
    assert walk.parsed["status"] == "HASH_VERIFIED_METADATA"
    assert walk.parsed["total"] == walk.document["counts"]["sections"] == sections
    assert walk.profile["parser"]["adapter_version"] == "fixed-html-1.0"
    assert walk.source_metadata["source_format"] == "html"
    assert walk.source_metadata["raw_sha256"] == walk.document["snapshot"]["sha256"]
    assert len(walk.units) == units
    assert len(walk.chunks) == len(walk.embeddings) == chunks
    assert all(set(i["records"]) == set(walk.chunks) for i in walk.indexes.values())
    assert all(r["DOM path"] != "Not recorded" for r in walk.parsed["rows"])
    assert not any(k in {"source_tree", "text", "content", "source_metadata"}
                   for r in walk.parsed["rows"] for k in r)
    first = walk.parsed["rows"][0]
    related = walk.related_items(block_id=first["Block ID"])
    assert related["mapping_status"] == "AVAILABLE"
    assert related["rows"]
    assert all(r["section_id"].startswith(did + ":") for r in related["rows"])
    value = walk.unit(walk.units[0]["unit_id"])
    assert sha(json.dumps(value, sort_keys=True).encode()) == sha(
        json.dumps(walk.data.verified_unit(value["unit_id"]), sort_keys=True).encode())
    chunk = walk.chunk(next(iter(walk.chunks)))
    assert chunk["verified_parent"]["document_id"] == did
    assert sha(json.dumps(chunk["verified_parent"], sort_keys=True).encode()) == sha(
        json.dumps(walk.unit(chunk["verified_parent"]["unit_id"]), sort_keys=True).encode())


@pytest.mark.parametrize("kind", ["parsed", "normalized", "source"])
def test_html_metadata_tampering_fails_closed(full_preparation_library, monkeypatch, kind):
    library = full_preparation_library
    bind = library.bound.bind
    path = ("data/parsed/html/C03.source.json" if kind == "source" else
            f"data/{kind}/html/C03.json")

    def altered(name, expected):
        value = bind(name, expected)
        if name == path:
            record = json.loads(value)
            if kind == "source":
                record["raw_sha256"] = "0" * 64
            else:
                key = "section" if kind == "normalized" else "block"
                record["records"][0][key]["raw_sha256"] = "0" * 64
            return json.dumps(record).encode()
        return value

    monkeypatch.setattr(library.bound, "bind", altered)
    with pytest.raises(ValueError, match="mismatch"):
        if kind == "normalized":
            walk = library.for_document("C03")
            walk.related_items(block_id=walk.parsed["rows"][0]["Block ID"])
        else:
            library._parsed_metadata("C03")


def test_html_missing_inspection_bindings_are_explicit(full_preparation_library, monkeypatch):
    library = full_preparation_library
    paths = {"data/parsed/html/C03.json", "data/normalized/html/C03.json"}
    monkeypatch.setattr(library.data, "binding_fingerprints",
                        {p: h for p, h in library.data.binding_fingerprints.items() if p not in paths})
    assert library._parsed_metadata("C03")["status"] == "UNAVAILABLE"
    walk = library.for_document("C03")
    result = walk.related_items(block_id=walk.parsed["rows"][0]["Block ID"])
    assert result["mapping_status"] == "UNAVAILABLE" and not result["rows"]
    assert "Mapping unavailable" in result["message"]
    with pytest.raises(ValueError, match="outside_selected_document"):
        walk.unit(library.for_document("C04").units[0]["unit_id"])


def test_html_source_is_inert_text_not_rendered_markup():
    app = AppTest.from_string(
        "from rag_hub.dashboard_ui import payload\n"
        "payload({'text': '<script>alert(1)</script><img src=\"https://invalid.example/image.png\">'})"
    ).run()
    assert not app.exception
    assert "<script>alert(1)</script>" in app.text[0].value
    assert not app.markdown
    assert not app.get("html") and not app.get("iframe") and not app.get("imgs")


def test_html_overview_routes_zero_exclusions_and_source_switching(full_preparation_library, monkeypatch):
    monkeypatch.setattr(views, "load", lambda: full_preparation_library)
    app = preparation_app().run()
    assert not app.exception and not app.error
    assert [m.value for m in app.metric] == ["16", "553", "992", "992/992"]
    assert any(c.value == "Read-only overview · 16 Verified sources connected: 4 PDF sources · 1 Markdown source · 11 HTML sources"
               for c in app.caption)
    fmt = next(s for s in app.selectbox if s.label == "Format")
    assert fmt.options == ["All formats", "HTML", "MARKDOWN", "PDF"]
    fmt.select("HTML").run()
    assert [m.value for m in app.metric] == ["11", "155", "355", "355/355"]
    next(s for s in app.selectbox if s.label == "Source").select("C03").run()
    for route in ["sources", "parsing-evidence", "parse", "normalize", "qa-evidence",
                  "chunks-lineage", "embeddings-indexes", "validation-publications"]:
        app._page_hash = calc_hash(route)
        app.run()
        assert not app.exception and not app.error, route
        assert next(s for s in app.selectbox if s.label == "Selected source").value == "C03"
        assert app.session_state["kp_selected_document"] == "C03"
        if route == "sources":
            fields = {r["Field"]: r["Value"] for f in app.dataframe if "Field" in f.value.columns
                      for r in f.value.to_dict("records")}
            assert fields["Format"] == "html"
            assert fields["Rights"] == full_preparation_library.for_document("C03").source_metadata["rights_status"]
        if route == "parse":
            blocks = next(f.value for f in app.dataframe if "Block ID" in f.value.columns)
            assert {"DOM path", "Classification", "Anchor"} <= set(blocks.columns)
        if route == "qa-evidence":
            assert any("HTML evidence uses the current published QA scope" in i.value for i in app.info)
            assert any(h.value == "Verified source content" for h in app.subheader)
        if route == "validation-publications":
            assert any(m.value == "**24 canonical Sections** → **21 admitted** · **0 HOLD** · **3 excluded**"
                       for m in app.markdown)
    # Exercise a zero-withheld document, not an inferred failure or missing measurement.
    next(s for s in app.selectbox if s.label == "Selected source").select("C05").run()
    assert not app.exception and not app.error
    assert any(c.value == "No HOLD or excluded Sections recorded for this source." for c in app.caption)
    assert app.button(key="kp_withheld_page_previous").disabled
    assert app.button(key="kp_withheld_page_next").disabled
    # The qualified HTML publication and earlier formats retain their own counts/context.
    for did, count in [("C16", "87"), ("C04", "209"), ("C01", "88")]:
        next(s for s in app.selectbox if s.label == "Selected source").select(did).run()
        app._page_hash = calc_hash("embeddings-indexes")
        app.run()
        assert not app.exception and not app.error
        assert app.session_state["kp_selected_document"] == did
        assert app.metric[0].value == count


