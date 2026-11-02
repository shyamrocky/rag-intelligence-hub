"""Actual-gateway C01 acceptance plus clearly owned, non-admission kernel controls."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rag_hub.chunk_inputs import ChunkInput, SourceContent
from rag_hub.chunk_preparation import ChunkPreparation
from rag_hub.m2_tokenizer import SPEC, PinnedBgeTokenizer
from rag_hub.structure_chunking import StructureAwarePilot, bibliography_entries, display_segments
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def tokenizer():
    return PinnedBgeTokenizer(ROOT)


@pytest.fixture(scope="module")
def preparation():
    return ChunkPreparation(load_verified_corpus(ROOT))


@pytest.fixture(scope="module")
def records(preparation):
    return preparation.prepare_document("C01")


@pytest.fixture(scope="module")
def pilot(preparation, tokenizer):
    return StructureAwarePilot(preparation, tokenizer)


@pytest.fixture(scope="module")
def results(records, pilot):
    return {b: [pilot.chunk(r, total_tokens=b) for r in records] for b in [256, 384]}


@pytest.mark.parametrize("text,expected", [
    ("", [101, 102]),
    ("hello world", [101, 7592, 2088, 102]),
    ("RAG-Sequence", [101, 17768, 1011, 5537, 102]),
])
def test_known_wordpiece_ids_and_special_tokens(tokenizer, text, expected):
    assert tokenizer.encode(text).ids == expected
    assert tokenizer.max_length == 512
    assert tokenizer.special_tokens == 2


def test_no_silent_truncation(tokenizer):
    assert tokenizer.count("hello " * 600) == 602
    assert tokenizer.count("hello " * 600, special=False) == 600


def test_tokenizer_configuration_mutation_fails_closed(tokenizer):
    tokenizer.tokenizer.enable_truncation(8)
    try:
        with pytest.raises(ValueError, match="truncation"):
            tokenizer.count("hello " * 600)
    finally:
        tokenizer.tokenizer.no_truncation()


def test_altered_tokenizer_spec_rejected(tmp_path):
    p = tmp_path / SPEC
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    with pytest.raises(ValueError, match="binding_changed"):
        PinnedBgeTokenizer(tmp_path)


def test_json_and_vocab_configuration_paths_agree_on_all_c01_source(records, tokenizer):
    reference = tokenizer.reference_tokenizer()
    for record in records:
        for source in record.indexable_source_content:
            assert tokenizer.encode(source.text).ids == reference.encode(source.text).ids
    for text in ["semi-supervised ﬁne Ω ± 2.5%", "all-MiniLM-L6-v2", "é 中文", "[MASK] [UNK]"]:
        assert tokenizer.encode(text).ids == reference.encode(text).ids


@pytest.mark.parametrize("budget", [256, 384])
def test_every_source_character_accounted_exactly_once(records, results, budget):
    assert len(results[budget]) == len(records) == 61
    for record, result in zip(records, results[budget], strict=True):
        assert result["unit_id"] == record.unit_id
        for source in record.indexable_source_content:
            outcomes = [c for c in result["chunks"] + result["unresolved"]
                        if c["source_pointer"] == source.source_pointer]
            position = 0
            for item in sorted(outcomes, key=lambda c: c["display_start"]):
                assert item["display_start"] == position
                a, b = item["display_start"], item["display_end"]
                assert sha(source.text[a:b].encode()) == item["source_text_sha256"]
                if "source_text" in item:
                    assert item["source_text"] == source.text[a:b]
                position = b
            assert position == len(source.text)
        assert result["config"]["chunk_overlap"] == 0


@pytest.mark.parametrize("budget", [256, 384])
def test_actual_bge_limits_include_prefix_and_specials(results, tokenizer, budget):
    for result in results[budget]:
        for chunk in result["chunks"]:
            assert chunk["embedding_text"] == chunk["heading_prefix"] + chunk["source_text"]
            assert chunk["token_count"] == tokenizer.count(chunk["embedding_text"])
            assert chunk["token_count"] <= budget < tokenizer.max_length
            assert chunk["body_token_count"] == tokenizer.count(chunk["source_text"], special=False)


def test_qa_and_context_never_flattened_into_source(records, results):
    for record, result in zip(records, results[256], strict=True):
        source = record.indexable_source_content[0]
        for c in result["chunks"]:
            assert c["source_text"] == source.text[c["display_start"]:c["display_end"]]
            assert c["qa_observations"] == record.qa_observations
            assert c["qualification"] == record.qualification
            assert c["required_context"] == record.required_context
            assert c["memberships"] == record.memberships
            assert c["publication_identity"] == record.publication_identity
            assert all(h["kind"] == "SOURCE_CONTENT" for h in c["heading_context"])
            assert c["authority"] == "DERIVED_CANDIDATE_NOT_EVIDENCE"


@pytest.mark.parametrize("budget", [256, 384])
def test_all_short_specialized_elements_stay_whole(records, results, budget):
    counts = {"table": 0, "mathematical_reference": 0, "caption": 0}
    for record, result in zip(records, results[budget], strict=True):
        source = record.indexable_source_content[0]
        if source.content_type not in counts:
            continue
        counts[source.content_type] += 1
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["source_text"] == source.text
        assert not result["unresolved"]
    assert counts == {"table": 4, "mathematical_reference": 2, "caption": 10}


def test_bibliography_matches_frozen_source_entry_boundaries(records, results):
    expected = json.loads((ROOT / "workspace/rag-implementation/v1/m2/BIBLIOGRAPHY_EXPECTATIONS.json"
                           ).read_text())
    record = next(r for r in records if r.unit_id == expected["unit_id"])
    source = record.indexable_source_content[0]
    assert sha(source.text.encode()) == expected["source_text_sha256"]
    entries = bibliography_entries(source, display_segments(source))
    assert len(entries) == 68
    assert [(e["start"], e["end"]) for e in entries] == [
        (e["display_start"], e["display_end"]) for e in expected["reference_entries"]]
    starts = {e["start"] for e in entries}
    ends = {e["end"] for e in entries}
    for budget in [256, 384]:
        result = next(u for u in results[budget] if u["unit_id"] == record.unit_id)
        assert [n for c in result["chunks"] for n in c["reference_numbers"]] == list(range(1, 69))
        assert all(c["display_start"] in starts and c["display_end"] in ends
                   for c in result["chunks"])
        assert not result["unresolved"]


def test_precise_lineage_and_parent_projection_precision_are_honest(records, results):
    lookup = {r.unit_id: r for r in records}
    for result in results[256]:
        record = lookup[result["unit_id"]]
        source = record.indexable_source_content[0]
        for c in result["chunks"]:
            lineage = c["lineage"]
            assert set(lineage["section_ids"]) <= set(source.section_ids)
            if lineage["precision"] == "HASH_VERIFIED_DISPLAY_TO_ORIGINAL_SOURCE_SLICES":
                for span in lineage["source_spans"]:
                    a, b = span["display_start"], span["display_end"]
                    assert sha(source.text[a:b].encode()) == span["span_sha256"]
                    assert span["end"] - span["start"] == b - a
            else:
                assert lineage["source_spans"] == source.source_spans
                assert "partial raw offsets" in lineage["note"]


@pytest.mark.parametrize("attack", ["text", "warning", "context", "publication", "span", "tokens"])
def test_rehashed_tampering_does_not_authorize(pilot, results, attack):
    original = next(r for r in results[256] if r["chunks"] and r["chunks"][0]["required_context"]
                    and r["chunks"][0]["qa_observations"])
    changed = copy.deepcopy(original)
    c = changed["chunks"][0]
    if attack == "text":
        c["source_text"] = "forged"
    elif attack == "warning":
        c["qa_observations"] = []
        c["qualification"] = {}
    elif attack == "context":
        c["required_context"] = []
    elif attack == "publication":
        c["publication_identity"] = {}
    elif attack == "span":
        c["lineage"]["source_spans"] = []
    else:
        c["token_count"] = 1
    c["proposal_id"] = "m2-piece:" + sha(encode(c))
    with pytest.raises(ValueError, match="altered_or_stale"):
        pilot.validate(changed)


def test_no_raw_hold_or_foreign_unit_input(pilot, records):
    changed = records[0].model_dump(mode="json")
    changed["indexable_source_content"][0]["text"] = "neighboring HOLD text"
    with pytest.raises(ValueError, match="altered_stale"):
        pilot.chunk(changed, total_tokens=256)
    changed["unit_id"] = "pdf:forged:unit"
    with pytest.raises(ValueError):
        pilot.chunk(changed, total_tokens=256)


def owned_control(text, kind="prose", structure=None, *, heading=None):
    """Synthetic kernel control, explicitly not a published or admitted source."""
    span = {"block_id": "owned:B1", "start": 0, "end": len(text),
            "span_sha256": sha(text.encode())}
    return ChunkInput(
        record_id="owned-synthetic-control-not-authorization", unit_id="owned:unit",
        document_id="C01", format="pdf", reference_classification="ILLUSTRATIVE_REFERENCE",
        indexable_source_content=[SourceContent(
            source_pointer="/owned/text", content_type=kind, text=text,
            section_ids=["owned:S1"], source_spans=[span],
            native_source={"kind": "SOURCE_CONTENT", "text": text, "structure": structure,
                           "content_type": kind, "citations": [span]})],
        required_context=[{"kind": "SOURCE_CONTENT", "role": "source_heading",
                           "text": heading, "source_span": span}] if heading else [],
        qa_observations=[], qualification={"mandatory": True, "complete_unit_only": True},
        protected_consumable_projections=[], preparation_limits=[],
        memberships=[{"section_id": "owned:S1", "role": "projection", "native_role": "owned"}],
        section_bindings=[{"section_id": "owned:S1",
                           "provenance": {"original_block_ids": ["owned:B1"]}}],
        citation_locators=[span], publication_identity={"owned_test_only": True},
        consumer_metadata={}, evidence_sha256="0" * 64)


@pytest.mark.parametrize("kind", ["table", "code", "mathematical_reference", "caption"])
def test_oversized_atomic_controls_are_unresolved_not_truncated(pilot, kind):
    record = owned_control("original number -123.456 and identifier all-MiniLM-L6-v2\n" * 100, kind)
    result = pilot._chunk_verified(record, total_tokens=256)
    assert not result["chunks"]
    assert result["unresolved"][0]["reason"] == "OVERSIZED_ATOMIC_ELEMENT_REQUIRES_REVIEW"
    assert result["source_results"][0]["unresolved_characters"] == len(
        record.indexable_source_content[0].text)


def test_prefix_exhaustion_is_explicit(pilot):
    record = owned_control("tiny source", heading="heading " * 400)
    result = pilot._chunk_verified(record, total_tokens=256)
    assert result["unresolved"][0]["reason"] == "REQUIRED_HEADING_EXHAUSTS_TOKEN_BUDGET"


def test_original_whitespace_unicode_and_identifiers_survive(pilot):
    text = ("  all-MiniLM-L6-v2 semi-supervised -123.456 Ω ﬁne.\n\n" * 60) + "  \n"
    record = owned_control(text)
    result = pilot._chunk_verified(record, total_tokens=256)
    assert not result["unresolved"]
    assert "".join(c["source_text"] for c in result["chunks"]) == text
    assert all("all-MiniLM-L6-v2" in c["source_text"] for c in result["chunks"]
               if "MiniLM" in c["source_text"])


@pytest.mark.parametrize("budget", [0, 7, 513, True, 1.5])
def test_invalid_budget_is_rejected(pilot, budget):
    with pytest.raises(ValueError, match="scope_or_token_budget"):
        pilot._chunk_verified(owned_control("owned test"), total_tokens=budget)


def test_malformed_reference_markers_fail_safely(pilot):
    record = owned_control("[1] source one\n[3] source three\n", "bibliography")
    result = pilot._chunk_verified(record, total_tokens=256)
    assert not result["chunks"]
    assert result["unresolved"][0]["reason"] == "UNVERIFIED_REFERENCE_BOUNDARIES"


def test_tokenizer_unk_is_reported_without_text_replacement(pilot):
    record = owned_control("faithful source \U0001fae0 remains literal")
    result = pilot._chunk_verified(record, total_tokens=256)
    assert result["chunks"][0]["source_text"] == record.indexable_source_content[0].text
    assert result["chunks"][0]["unknown_token_offsets"]


def owned_bibliography(first="[1] short source", second="[2] another source"):
    text = first + "\n" + second
    record = owned_control(text, "bibliography")
    members = []
    for a, b in [(0, len(first)), (len(first) + 1, len(text))]:
        members.append({"source_member": {"block_id": "owned:B1", "start": a, "end": b,
                                          "span_sha256": sha(text[a:b].encode())}})
    record.indexable_source_content[0].native_source["structure"] = {"paragraphs": members}
    return record


def test_oversized_verified_reference_is_explicit_not_split_as_prose(pilot):
    record = owned_bibliography(second="[2] " + "original technical source " * 300)
    result = pilot._chunk_verified(record, total_tokens=256)
    assert result["chunks"][0]["reference_numbers"] == [1]
    assert result["unresolved"][0]["reason"] == "OVERSIZED_REFERENCE_ENTRY"
    assert result["unresolved"][0]["detail"]["reference_number"] == 2
    assert sum(s["chunked_characters"] + s["unresolved_characters"]
               for s in result["source_results"]) == len(record.indexable_source_content[0].text)


@pytest.mark.parametrize("second", ["[3] missing number", "[1] duplicate number"])
def test_nonsequential_markers_rejected_even_with_exact_source_segments(pilot, second):
    record = owned_bibliography(second=second)
    result = pilot._chunk_verified(record, total_tokens=256)
    assert not result["chunks"]
    assert result["unresolved"][0]["reason"] == "UNVERIFIED_REFERENCE_BOUNDARIES"


def test_real_result_replay_and_protected_values_are_exact(pilot, results, tokenizer):
    for budget in [256, 384]:
        abstract = next(r for r in results[budget] if "pdf-preserved:" in r["unit_id"])
        assert pilot.validate(abstract)
    text = "all-MiniLM-L6-v2 semi-supervised -123.456 " * 200
    record = owned_control(text)
    result = pilot._chunk_verified(record, total_tokens=256)
    assert "".join(c["source_text"] for c in result["chunks"]) == text
    assert sum(c["source_text"].count("all-MiniLM-L6-v2") for c in result["chunks"]) == 200
    assert sum(c["source_text"].count("-123.456") for c in result["chunks"]) == 200
    assert all(tokenizer.count(c["embedding_text"]) <= 256 for c in result["chunks"])


def test_real_current_expiration_is_readable_and_bound(records, results):
    record = next(r for r in records if "pdf-preserved:" in r.unit_id)
    expiration = record.consumer_metadata["publication_expiration"]
    assert expiration["retrieval_allowed"]
    if datetime.now(UTC) >= datetime.fromisoformat(expiration["expires_at"]):
        assert expiration["status"] == "EXPIRED"
        assert any(o.get("issue_id") == "PDF_PUBLICATION_EXPIRED"
                   for o in record.qa_observations)
    for budget in [256, 384]:
        result = next(u for u in results[budget] if u["unit_id"] == record.unit_id)
        assert not result["unresolved"]
        for c in result["chunks"]:
            assert c["consumer_metadata"]["publication_expiration"] == expiration
            assert c["qa_observations"] == record.qa_observations


def test_native_leading_heading_is_carried_into_oversized_prose(pilot):
    record = owned_bibliography(first="Abstract", second="Source technical prose. " * 180)
    old = record.indexable_source_content[0]
    record.indexable_source_content[0] = old.model_copy(update={"content_type": "section_text"})
    result = pilot._chunk_verified(record, total_tokens=256)
    assert not result["unresolved"]
    assert result["chunks"][0]["source_text"].startswith("Abstract\nSource technical prose.")
    assert all(c["source_text"].strip() != "Abstract" for c in result["chunks"])
    assert "".join(c["source_text"] for c in result["chunks"]) == old.text


def test_no_heading_only_candidates_created_in_real_c01(records, results):
    for budget in [256, 384]:
        for record, result in zip(records, results[budget], strict=True):
            if len(result["chunks"]) <= 1:
                continue
            assert all(c["source_text"].strip() not in {"Abstract", "3.4\nFact Veriﬁcation"}
                       for c in result["chunks"])


def test_leading_member_keeps_prose_when_next_member_fits_alone(pilot):
    record = owned_bibliography(first="A source heading", second="simple " * 253)
    old = record.indexable_source_content[0]
    record.indexable_source_content[0] = old.model_copy(update={"content_type": "section_text"})
    result = pilot._chunk_verified(record, total_tokens=256)
    assert not result["unresolved"]
    assert "".join(c["source_text"] for c in result["chunks"]) == old.text
    assert all(c["source_text"].strip() != "A source heading" for c in result["chunks"])
