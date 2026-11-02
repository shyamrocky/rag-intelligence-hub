"""Verified consumer integration; no new QA admissions or third-party fixtures."""

import copy
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from rag_hub.unified_bindings import FREEZE, BoundFiles, accepted_bindings
from rag_hub.unified_consumption import VerifiedCorpus, load_verified_corpus
from rag_hub.unified_models import AdaptedUnit, Membership, encode, sha

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def corpus():
    if not (ROOT / FREEZE).exists():
        pytest.skip("accepted private corpus not provided")
    return load_verified_corpus(ROOT)


@pytest.mark.parametrize("fmt,documents,sections,admitted,excluded,held,units", [
    ("html", 11, 457, 427, 30, 0, 155),
    ("markdown", 1, 158, 154, 4, 0, 86),
    ("pdf", 4, 2425, 1991, 76, 358, 309),
])
def test_actual_accounting(corpus, fmt, documents, sections, admitted, excluded, held, units):
    summary = corpus.catalog.get_corpus_summary()
    assert summary["formats"][fmt] == {
        "sections": sections, "ADMITTED": admitted, "EXCLUDED": excluded,
        "HOLD": held, "units": units}
    assert sum(d["format"] == fmt for d in corpus.catalog.list_documents()) == documents


def test_exact_combined_unique_accounting(corpus):
    s = corpus.catalog.get_corpus_summary()
    assert {k: s[k] for k in ("documents", "sections", "admitted", "excluded", "HOLD", "units")} == {
        "documents": 16, "sections": 3040, "admitted": 2572,
        "excluded": 110, "HOLD": 358, "units": 550}
    catalog = json.loads(corpus.catalog.export())
    assert len(catalog["sections"]) == 3040
    assert len(catalog["units"]) == 550
    assert catalog["authority"] == "INSPECTION_ONLY"


def test_every_edge_is_bidirectional_and_admitted(corpus):
    catalog = json.loads(corpus.catalog.export())
    reverse = {}
    for uid, unit in catalog["units"].items():
        edges = corpus.catalog.get_unit_sections(uid)
        assert edges == unit["memberships"]
        assert len({(e["section_id"], e["role"], e["native_role"]) for e in edges}) == len(edges)
        for edge in edges:
            sid = edge["section_id"]
            assert catalog["sections"][sid]["admission_status"] == "ADMITTED"
            reverse.setdefault(sid, set()).add((uid, edge["role"], edge["native_role"]))
    for sid, section in catalog["sections"].items():
        expected = {(e["unit_id"], e["role"], e["native_role"]) for e in section["memberships"]}
        assert expected == reverse.get(sid, set())
        assert bool(expected) == (section["admission_status"] == "ADMITTED")
        assert section["unit_ids"] == sorted({e[0] for e in expected})
    assert any(len(s["unit_ids"]) > 1 for s in catalog["sections"].values())


@pytest.mark.parametrize("status", ["HOLD", "EXCLUDED", "ADMITTED"])
def test_section_ids_never_authorize_evidence(corpus, status):
    section = corpus.catalog.list_sections(filters={"admission_status": status}, limit=1)["items"][0]
    assert "text" not in section and "consumer" not in section
    assert not section["raw_section_is_independent_consumption_unit"]
    with pytest.raises(ValueError, match="wrong_publication_unit"):
        corpus.evidence.get_verified_unit(section["section_id"])


@pytest.mark.parametrize("uid", ["forged", "", "pdf:historical:foreign", "html:unknown", None])
def test_unknown_forged_wrong_publication_ids(corpus, uid):
    with pytest.raises(ValueError, match="wrong_publication_unit"):
        corpus.evidence.get_verified_unit(uid)


def test_catalog_has_no_raw_evidence_escape_hatch(corpus):
    data = json.loads(corpus.catalog.export())
    for row in data["sections"].values():
        assert not {"text", "raw_text", "source_content", "llm_context", "consumer"} & row.keys()
    for row in data["units"].values():
        assert "consumer" not in row and "llm_context" not in row
    with pytest.raises(TypeError):
        corpus.evidence.validate(corpus.catalog.export())
    with pytest.raises(TypeError):
        corpus.evidence.validate(None)
    with pytest.raises(TypeError):
        corpus.evidence.validate({"authority": "INSPECTION_ONLY"})


def test_all_units_validate_with_no_per_lookup_native_loading(corpus, monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("unit lookup reran native loading/QA/parsing")

    for name in ("html_handoff", "markdown_handoff", "pdf_text_handoff"):
        monkeypatch.setattr(f"rag_hub.{name}.load_units", forbidden)
    monkeypatch.setattr("rag_hub.shared.qa.assess", forbidden)
    units = corpus.evidence.load_verified_units()
    assert len(units) == 550
    for u in units:
        assert corpus.evidence.validate(u)
        assert json.loads(corpus.evidence.serialize(u)) == u
        assert u["citation_locators"] and u["publication_identity"]
        assert "audit_only" not in u["consumer"]


def test_c10_context_and_qa_observation_remain_separate(corpus):
    u = next(u for u in corpus.evidence.load_verified_units(filters={"document_id": "C10"})
             if u["consumer"].get("related_evidence"))
    context = u["consumer"]["llm_context"]
    assert context["source_content"][0]["table"]
    assert any(x.get("relationship_type") == "documented_RRF_context_not_numerical_equivalence"
               for x in context["required_context"])
    assert all(o["kind"] == "QA_OBSERVATION" for o in context["qa_observations"])
    assert any(o["issue_id"] == "HTML-SRC-SCORE-STAGE" for o in context["qa_observations"])
    assert context["qualification"]["mandatory"]


def test_four_restricted_markdown_projections(corpus):
    units = corpus.evidence.load_verified_units(filters={"format": "markdown"})
    restricted = [u for u in units if u["scope_limited_projection"]]
    assert len(restricted) == 4
    for u in restricted:
        content = u["consumer"]["llm_context"]["source_content"]
        assert len(content) == 1 and "restricted_projection" in content[0]
        p = content[0]["restricted_projection"]
        assert all(w in p["consumable_text"] for w in p["warnings"])
        assert p["raw_Sections_are_provenance_only"]
        assert "source_evidence" not in u["consumer"]


@pytest.mark.parametrize("fmt", ["html", "markdown", "pdf"])
@pytest.mark.parametrize("attack", ["warning", "context", "text", "classification", "hash"])
def test_mutated_rehashed_units_rejected(corpus, fmt, attack):
    units = corpus.evidence.load_verified_units(filters={"format": fmt})
    u = next(u for u in units if u["consumer"]["llm_context"]["qa_observations"]
             and u["consumer"]["llm_context"]["required_context"])
    original = copy.deepcopy(u)
    c = u["consumer"]["llm_context"]
    if attack == "warning":
        c["qa_observations"] = []
        c["qualification"] = {}
    elif attack == "context":
        c["required_context"] = []
    elif attack == "text":
        c["source_content"] = [{"kind": "SOURCE_CONTENT", "text": "forged"}]
    elif attack == "classification":
        u["reference_classification"] = "STANDARD_REFERENCE"
        u["native_reference_classification"] = "forged"
    else:
        u["publication_identity"] = {"manifest_sha256": "0" * 64}
    u["native_handle"] = sha(encode(u))  # Rehashing must confer no authority.
    with pytest.raises(ValueError, match="altered_or_warning_context"):
        corpus.evidence.validate(u)
    assert corpus.evidence.validate(original)


def test_context_only_is_not_a_standalone_unit(corpus):
    row = corpus.catalog.list_sections(filters={"context_only": True}, limit=1)["items"][0]
    assert row["unit_ids"] and row["context_only"]
    for edge in row["memberships"]:
        assert edge["role"] in {"required_context", "supporting_heading"}
    with pytest.raises(ValueError):
        corpus.evidence.get_verified_unit(row["section_id"])


@pytest.mark.parametrize("filters", [
    {"admission_status": "HOLD"}, {"admission_status": "EXCLUDED"},
    {"reference_classification": "STANDARD_REFERENCE"},
    {"reference_classification": "ILLUSTRATIVE_REFERENCE"},
    {"context_only": True}, {"has_units": False}, {"format": "pdf"},
])
def test_catalog_filters_and_pagination(corpus, filters):
    result = corpus.catalog.list_sections(filters=filters, limit=3)
    assert result["total"] > 0
    assert len(result["items"]) == min(3, result["total"])
    assert result == corpus.catalog.list_sections(filters=filters, limit=3)
    if result["next_offset"]:
        later = corpus.catalog.list_sections(filters=filters, offset=3, limit=3)
        assert not {x["section_id"] for x in result["items"]} & {
            x["section_id"] for x in later["items"]}


@pytest.mark.parametrize("offset,limit", [(-1, 1), (0, 0), (0, 1001), (0.5, 1), (False, 2)])
def test_bad_pagination(corpus, offset, limit):
    with pytest.raises(ValueError, match="pagination"):
        corpus.catalog.list_sections(offset=offset, limit=limit)


def test_filters_do_not_strip_qualifications(corpus):
    for classification in ["STANDARD_REFERENCE", "ILLUSTRATIVE_REFERENCE"]:
        units = corpus.evidence.load_verified_units(filters={"reference_classification": classification})
        assert units and all(u["reference_classification"] == classification for u in units)
        assert all(corpus.evidence.validate(u) for u in units)
    assert corpus.evidence.load_verified_units(filters={"admission_status": "HOLD"}) == []
    with pytest.raises(ValueError, match="unknown_unified_filter"):
        corpus.catalog.list_units(filters={"invented": True})


def test_pdf_expiration_crossing_requires_warning_but_remains_readable(corpus, monkeypatch):
    import rag_hub.pdf_publication as publication

    old = next(u for u in corpus._units.values()
               if u.format == "pdf" and "publication_expiration" in json.loads(u.consumer_json))
    end = datetime.fromisoformat(json.loads(old.consumer_json)["publication_expiration"]["expires_at"])
    monkeypatch.setattr(publication, "utc_now", lambda: end - timedelta(seconds=1))
    before = corpus.evidence.get_verified_unit(old.unit_id)
    assert before["consumer"]["publication_expiration"]["status"] == "VALID"
    monkeypatch.setattr(publication, "utc_now", lambda: end + timedelta(seconds=1))
    after = corpus.evidence.get_verified_unit(old.unit_id)
    expiration = after["consumer"]["publication_expiration"]
    assert expiration["status"] == "EXPIRED" and expiration["retrieval_allowed"]
    assert expiration["display_to_user_when_used"]
    assert any(o["issue_id"] == "PDF_PUBLICATION_EXPIRED"
               for o in after["consumer"]["llm_context"]["qa_observations"])
    assert corpus.evidence.validate(after)
    with pytest.raises(ValueError):
        corpus.evidence.validate(before)


@pytest.mark.parametrize("mutation", ["bytes", "mtime_reset", "delete", "symlink"])
def test_binding_changes_invalidate_snapshot(tmp_path, mutation):
    p = tmp_path / "source"
    p.write_bytes(b"original")
    bound = BoundFiles(tmp_path)
    bound.bind("source", sha(p.read_bytes()))
    s = p.stat()
    if mutation in {"bytes", "mtime_reset"}:
        p.write_bytes(b"altered!")
        if mutation == "mtime_reset":
            os.utime(p, ns=(s.st_atime_ns, s.st_mtime_ns))
    elif mutation == "delete":
        p.unlink()
    else:
        other = tmp_path / "other"
        other.write_bytes(b"original")
        p.unlink()
        p.symlink_to(other)
    with pytest.raises(ValueError, match="invalidated"):
        bound.check()
    p.unlink(missing_ok=True)
    p.write_bytes(b"original")
    with pytest.raises(ValueError, match="invalidated"):
        bound.check()


def test_unbound_wrong_hash_and_outside_root(tmp_path):
    p = tmp_path / "owned"
    p.write_bytes(b"test")
    bound = BoundFiles(tmp_path)
    with pytest.raises(ValueError, match="binding_changed"):
        bound.bind("owned", "0" * 64)
    with pytest.raises(ValueError, match="unbound_catalog"):
        bound.json("owned")
    with pytest.raises(ValueError, match="outside_root"):
        bound.path("../../")


def test_wrong_or_historical_selection_fails_before_native_load():
    if not (ROOT / FREEZE).exists():
        pytest.skip("accepted private corpus absent")
    with pytest.raises(ValueError, match="historical_selection"):
        accepted_bindings(ROOT, {"markdown": {}})


def owned_snapshot(tmp_path, *, status="ADMITTED", member="owned", duplicate=False):
    bound = BoundFiles(tmp_path)
    unit = AdaptedUnit(
        "native", "DOC", "html", "STANDARD_REFERENCE", "STANDARD_REFERENCE",
        (Membership(member, "content", "owned"),), b"{}",
        encode({"llm_context": {"source_content": [], "required_context": [],
                                "qa_observations": [], "qualification": {}}}), b"{}", b"[]", False)
    rows = {"owned": {"document_id": "DOC", "format": "html", "admission_status": status}}
    sources = [{"source": {"doc_id": "DOC"}, "snapshot": {}}]
    counts = {"documents": 1, "sections": 1, "units": 1, "admitted": 1, "excluded": 0, "HOLD": 0}
    return VerifiedCorpus(bound, rows, [unit, unit] if duplicate else [unit], sources, counts, {})


@pytest.mark.parametrize("status", ["HOLD", "EXCLUDED"])
def test_catalog_label_cannot_authorize_hold_or_excluded(tmp_path, status):
    with pytest.raises(ValueError, match="unauthorized_or_foreign"):
        owned_snapshot(tmp_path, status=status)


def test_invalid_graph_and_duplicate_identity(tmp_path):
    with pytest.raises(ValueError, match="missing_section"):
        owned_snapshot(tmp_path, member="missing")
    with pytest.raises(ValueError, match="duplicate_unified"):
        owned_snapshot(tmp_path, duplicate=True)


def test_cross_format_namespaces_preserve_equal_native_ids():
    unit = AdaptedUnit("same", "D", "html", "STANDARD", None, (), b"{}", b"{}", b"{}", b"[]", False)
    assert unit.unit_id != replace(unit, format="pdf").unit_id
    assert unit.unit_id != replace(unit, publication_json=b'{"version":2}').unit_id


@pytest.mark.parametrize("target", ["snapshot", "manifest", "publication", "index", "canonical", "component"])
def test_corrupt_bound_input_rejected_before_native_loading(monkeypatch, target):
    if not (ROOT / FREEZE).exists():
        pytest.skip("accepted private corpus absent")
    freeze = json.loads((ROOT / FREEZE).read_bytes())
    selection = json.loads((ROOT / "config/pdf-residual-admission-publication-v1.json").read_bytes())
    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    from rag_hub.unified_bindings import INDEX

    names = {
        "snapshot": freeze["frozen_source_identities"][0]["snapshot"]["path"],
        "manifest": selection["manifest_path"],
        "publication": manifest["publications"][0]["path"],
        "index": INDEX,
        "canonical": "data/normalized/pdf/four-pdf-poc-v1/C01/sections.json",
        "component": "src/rag_hub/pdf_text_handoff.py",
    }
    altered = ROOT / names[target]
    original = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda p: original(p) + b"corrupt" if p == altered else original(p))
    with pytest.raises(ValueError, match="binding_changed"):
        accepted_bindings(ROOT)


@pytest.mark.parametrize("attack", ["warnings", "rendered_warning", "segments", "headings"])
def test_restricted_markdown_inner_projection_mutation_fails(corpus, attack):
    u = next(u for u in corpus.evidence.load_verified_units(filters={"format": "markdown"})
             if u["scope_limited_projection"])
    context = u["consumer"]["llm_context"]
    projection = context["source_content"][0]["restricted_projection"]
    if attack == "warnings":
        projection["warnings"] = []
    elif attack == "rendered_warning":
        projection["consumable_text"] = "warning removed"
    elif attack == "segments":
        projection["segments"].pop()
    else:
        context["required_context"] = []
    with pytest.raises(ValueError, match="altered_or_warning_context"):
        corpus.evidence.validate(u)


def test_returned_views_cannot_mutate_loaded_snapshot(corpus):
    section = corpus.catalog.list_sections(limit=1)["items"][0]
    original = copy.deepcopy(section)
    section["memberships"].clear()
    assert corpus.catalog.get_section(section["section_id"]) == original
    unit = corpus.evidence.load_verified_units()[0]
    original = copy.deepcopy(unit)
    unit["consumer"]["llm_context"].clear()
    assert corpus.evidence.get_verified_unit(unit["unit_id"]) == original


def test_issue_reason_filters_and_qa_drilldown(corpus):
    section = corpus.catalog.list_sections(filters={"admission_status": "HOLD"}, limit=1)["items"][0]
    reason = section["reason"]
    result = corpus.catalog.list_sections(filters={"reason": reason})
    assert result["total"] and all(r["reason"] == reason for r in result["items"])
    issue = section["issues"][0]["issue_type"]
    assert corpus.catalog.list_sections(filters={"issue_type": issue})["total"] > 0
    admitted = corpus.catalog.list_sections(filters={"admission_status": "ADMITTED"}, limit=1)["items"][0]
    details = corpus.catalog.get_section_qa_details(admitted["section_id"])
    assert details["unit_qualifications"]
    assert all(q["qualification"]["mandatory"] for q in details["unit_qualifications"])
