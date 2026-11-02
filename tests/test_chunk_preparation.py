"""M0/M1 source/context separation and live authorization-bound preparation."""

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from rag_hub.chunk_inputs import ChunkInput, json_schema
from rag_hub.chunk_preparation import ChunkPreparation, source_sections, write_once
from rag_hub.chunk_profile import distribution, profile, tokens
from rag_hub.unified_bindings import FREEZE
from rag_hub.unified_consumption import load_verified_corpus

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def preparation():
    if not (ROOT / FREEZE).exists():
        pytest.skip("accepted private corpus absent")
    return ChunkPreparation(load_verified_corpus(ROOT))


@pytest.fixture(scope="module")
def records(preparation):
    return preparation.prepare_document("C01")


def test_versioned_closed_schema():
    schema = json_schema()
    assert schema["additionalProperties"] is False
    assert {"indexable_source_content", "required_context", "qa_observations", "qualification",
            "memberships", "section_bindings", "citation_locators", "publication_identity"} <= (
                schema["properties"].keys())


def test_all_c01_units_and_unique_sections(records, preparation):
    assert len(records) == 61
    ids = {s["section_id"] for r in records for s in r.section_bindings}
    expected = preparation.corpus.catalog.list_sections(
        "C01", filters={"admission_status": "ADMITTED"}, limit=1000)
    assert len(ids) == expected["total"] == 277
    assert ids == {r["section_id"] for r in expected["items"]}
    assert len({r.record_id for r in records}) == 61


def test_deterministic_records_and_complete_separation(records, preparation):
    for r in records:
        original = preparation.corpus.evidence.get_verified_unit(r.unit_id)
        ctx = original["consumer"]["llm_context"]
        assert [s.native_source for s in r.indexable_source_content] == ctx["source_content"]
        assert r.required_context == ctx["required_context"]
        assert r.qa_observations == ctx["qa_observations"]
        assert r.qualification == ctx["qualification"]
        assert r.publication_identity == original["publication_identity"]
        assert r.memberships == original["memberships"]
        assert r == preparation.prepare(r.unit_id)
        assert r.authority == "DERIVED_PREPARATION_NOT_AUTHORIZATION"


@pytest.mark.parametrize("field", [
    "indexable_source_content", "required_context", "qa_observations", "qualification",
    "memberships", "section_bindings", "publication_identity", "citation_locators",
    "consumer_metadata", "evidence_sha256", "reference_classification",
])
def test_mutation_or_stripping_is_rejected(records, preparation, field):
    r = next(r for r in records if r.required_context and r.qa_observations)
    changed = r.model_dump(mode="json")
    value = changed[field]
    if isinstance(value, list):
        changed[field] = []
    elif isinstance(value, dict):
        changed[field] = {}
    else:
        changed[field] = "0" * 64
    with pytest.raises(ValueError):
        preparation.validate(changed)


def test_qa_or_context_cannot_become_indexable(records, preparation):
    r = next(r for r in records if r.required_context and r.qa_observations)
    for text in ["QA commentary must never be indexed", r.required_context[0].get("text", "heading")]:
        changed = r.model_dump(mode="json")
        changed["indexable_source_content"][0]["text"] = text
        with pytest.raises(ValueError, match="altered_stale"):
            preparation.validate(changed)


def test_context_membership_cannot_authorize_source():
    memberships = [{"section_id": "s", "role": "supporting_heading"}]
    with pytest.raises(ValueError, match="context_or_unbound"):
        source_sections({"section_id": "s"}, [], memberships)
    with pytest.raises(ValueError, match="unresolved"):
        source_sections({"citations": [{"block_id": "foreign"}]}, [], memberships)


def test_exact_numeric_symbols_and_source_bytes(records, preparation):
    types = {s.content_type for r in records for s in r.indexable_source_content}
    assert {"table", "mathematical_reference", "caption"} <= types
    for r in records:
        for s in r.indexable_source_content:
            assert s.text == s.native_source["text"]
            assert s.source_spans == s.native_source["citations"]
        assert json.loads(preparation.serialize(r)) == r.model_dump(mode="json")


def test_prepared_json_alone_is_not_verified_evidence(records, preparation):
    r = records[0]
    with pytest.raises((TypeError, ValueError)):
        preparation.corpus.evidence.validate(r.model_dump(mode="json"))
    changed = copy.deepcopy(r)
    changed.indexable_source_content[0].native_source["text"] = "tampered nested dict"
    with pytest.raises(ValueError):
        preparation.validate(changed)


def test_hold_excluded_and_forged_ids_never_prepare(preparation):
    for status in ["HOLD", "EXCLUDED"]:
        sid = preparation.corpus.catalog.list_sections(
            "C01", filters={"admission_status": status}, limit=1)["items"][0]["section_id"]
        with pytest.raises(ValueError):
            preparation.prepare(sid)
    with pytest.raises(ValueError):
        preparation.prepare("pdf:forged:unit")


def test_all_three_native_formats_and_restricted_projection(preparation):
    counts, protected = {}, []
    for fmt in ["html", "markdown", "pdf"]:
        rows = preparation.corpus.catalog.list_units(filters={"format": fmt})
        counts[fmt] = len(rows)
        for row in rows:
            r = preparation.prepare(row["unit_id"])
            value = preparation.corpus.evidence.get_verified_unit(row["unit_id"])
            ctx = value["consumer"]["llm_context"]
            assert len(r.indexable_source_content) + len(r.protected_consumable_projections) == len(
                ctx["source_content"])
            assert r.required_context == ctx["required_context"]
            assert r.consumer_metadata == {k: v for k, v in value["consumer"].items()
                                           if k != "llm_context"}
            if r.protected_consumable_projections:
                protected.append(r)
                assert not r.indexable_source_content
                projection = r.protected_consumable_projections[0]["native_source"][
                    "restricted_projection"]
                assert all(w in projection["consumable_text"] for w in projection["warnings"])
                assert r.preparation_limits
    assert counts == {"html": 155, "markdown": 86, "pdf": 309}
    assert len(protected) == 4


def test_unique_section_profile_does_not_sum_repeated_context(records):
    result = profile(records)
    s = result["unique_section_statistics"]
    assert s["sections"] == 277
    assert s["shared_by_multiple_units"] > 0
    assert s["membership_edges"] > s["sections"]
    assert s["context_span_occurrences"] > s["unique_context_spans"]
    assert s["context_span_codepoints_with_repetition"] > s["unique_context_span_codepoints"]
    assert s["unique_body_context_union_codepoints"] <= (
        s["unique_body_span_codepoints"] + s["unique_context_span_codepoints"])
    assert all(s["source_text_witness_tokens"] is None for s in result["sections"]
               if s["context_only"])
    assert not result["token_method"]["model_tokens"]
    assert profile(records) == result


def test_token_count_is_explicit_not_bge():
    assert tokens("alpha beta, 12.5 Ω") == 7
    assert distribution([1, 2, 3, 4])["p50"] == 2
    assert distribution([]) == {"n": 0}


def test_versioned_output_cannot_overwrite(tmp_path):
    p = tmp_path / "new" / "records.jsonl"
    write_once(p, b"original")
    write_once(p, b"original")
    with pytest.raises(ValueError, match="already_exists"):
        write_once(p, b"changed")
    assert p.read_bytes() == b"original"


def test_no_unknown_contract_fields(records):
    changed = records[0].model_dump(mode="json")
    changed["raw_section_fallback"] = "forbidden"
    with pytest.raises(ValueError):
        ChunkInput.model_validate(changed)


def test_expiration_refresh_preserves_content_with_warning(preparation, monkeypatch):
    import rag_hub.pdf_publication as publication

    uid = next(u["unit_id"] for u in preparation.corpus.catalog.list_units(document_id="C01")
               if "pdf-preserved:" in u["unit_id"])
    view = preparation.corpus.evidence.get_verified_unit(uid)
    end = datetime.fromisoformat(view["consumer"]["publication_expiration"]["expires_at"])
    monkeypatch.setattr(publication, "utc_now", lambda: end - timedelta(seconds=1))
    before = preparation.prepare(uid)
    monkeypatch.setattr(publication, "utc_now", lambda: end + timedelta(seconds=1))
    after = preparation.prepare(uid)
    assert before.indexable_source_content == after.indexable_source_content
    assert before.publication_identity == after.publication_identity
    assert after.consumer_metadata["publication_expiration"]["retrieval_allowed"]
    assert any(x.get("issue_id") == "PDF_PUBLICATION_EXPIRED" for x in after.qa_observations)
    assert preparation.validate(after)
    with pytest.raises(ValueError, match="altered_stale"):
        preparation.validate(before)
