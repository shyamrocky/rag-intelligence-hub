"""Owned synthetic kernel controls; never owner reference annotations or QA approvals."""

import json
from pathlib import Path

import pytest

from rag_hub.chunk_inputs import ChunkInput, SourceContent
from rag_hub.corpus_chunking import CorpusChunker
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.unified_models import sha

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def kernel():
    return CorpusChunker(None, PinnedBgeTokenizer(ROOT))


def owned_record(kind, text):
    # Reuse contract shape only; synthetic values are deliberately not gateway-authorized.
    base = json.loads((ROOT / "data/preparation/m3-full-v1/prepared-inputs.jsonl").read_text().splitlines()[0])
    base.update(document_id="SYNTHETIC", format="html", required_context=[],
                protected_consumable_projections=[])
    base["indexable_source_content"] = [SourceContent(
        source_pointer="/synthetic/source", content_type=kind, text=text,
        section_ids=["owned:section"], source_spans=[{"owned_locator": True}], native_source={}
    ).model_dump(mode="json")]
    return ChunkInput.model_validate(base)


@pytest.mark.parametrize("kind", ["table", "code_block", "code", "code_example", "formula",
                                  "mathematical_reference", "caption", "figure",
                                  "ordered_list", "unordered_list"])
def test_specialized_elements_are_atomic_or_explicitly_blocked(kernel, kind):
    text = "all-MiniLM-L6-v2 = -12.5; Ω_1\n"
    short = kernel._partition_verified(owned_record(kind, text), total_tokens=384)
    assert short["chunks"][0]["source_text"] == text
    assert not short["unresolved"]
    long = kernel._partition_verified(owned_record(kind, text * 200), total_tokens=384)
    assert not long["chunks"]
    assert long["unresolved"][0]["reason"] == "OVERSIZED_ATOMIC_ELEMENT_REQUIRES_REVIEW"
    assert long["source_results"][0]["unresolved_characters"] == len(text) * 200


@pytest.mark.parametrize("kind", ["paragraph", "prose", "section_text", "residual_prose_projection"])
def test_lossless_prose_splitting(kernel, kind):
    text = "A complete sentence preserves BART-large and 400M.\n\n" * 90
    result = kernel._partition_verified(owned_record(kind, text), total_tokens=384)
    assert not result["unresolved"]
    assert "".join(c["source_text"] for c in result["chunks"]) == text
    assert all(c["token_count"] <= 384 for c in result["chunks"])


@pytest.mark.parametrize("kind", ["unknown", "heading", "new-unqualified-widget"])
def test_unknown_or_context_only_structures_not_forced_into_chunks(kernel, kind):
    result = kernel._partition_verified(owned_record(kind, "Bound source text"), total_tokens=384)
    assert not result["chunks"]
    assert result["unresolved"][0]["reason"] == "UNSUPPORTED_NATIVE_STRUCTURE_NOT_FORCED_INTO_PROSE"


def test_oversized_identifier_is_never_truncated(kernel):
    text = "all-MiniLM-L6-v2"
    result = kernel._partition_verified(owned_record("prose", text), total_tokens=8)
    outcomes = result["chunks"] + result["unresolved"]
    assert sum(x["display_end"] - x["display_start"] for x in outcomes) == len(text)
    assert result["unresolved"] and not result["chunks"]
    assert result["unresolved"][0]["source_text_sha256"] == sha(text.encode())


def test_very_long_unknown_word_preserves_characters(kernel):
    # WordPiece may encode an overlong word as UNK, not as thousands of tokens.
    text = "identifier" * 2000
    result = kernel._partition_verified(owned_record("prose", text), total_tokens=384)
    assert result["chunks"][0]["source_text"] == text
    assert result["chunks"][0]["unknown_token_offsets"]
    assert not result["unresolved"]


def test_protected_warning_projection_has_no_independent_chunks(kernel):
    record = owned_record("prose", "unused").model_copy(update={
        "indexable_source_content": [], "protected_consumable_projections": [
            {"source_pointer": "/protected", "native_source": {"warning": "must remain"}}]})
    result = kernel._partition_verified(record, total_tokens=384)
    assert not result["chunks"] and not result["unresolved"]
    assert result["non_indexable"][0]["source_pointer"] == "/protected"
