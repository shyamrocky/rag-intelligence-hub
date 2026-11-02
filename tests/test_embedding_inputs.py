"""Synthetic projection controls; these fixtures are not admitted corpus evidence."""

import copy

import pytest

from rag_hub.embedding_inputs import embedding_id, embedding_input
from rag_hub.unified_models import encode, sha


@pytest.fixture
def view():
    source = "Original publisher prose."
    parent = {"admission_status": "ADMITTED", "unit_id": "unit:synthetic",
        "memberships": [{"section_id": "body", "role": "content"},
                        {"section_id": "context", "role": "supporting_heading"}],
        "publication_identity": {"sha256": "synthetic"},
        "consumer": {"llm_context": {"qualification": {"mandatory": True,
            "complete_unit_only": True, "warning": "MANDATORY_WARNING_NOT_SOURCE"},
            "qa_observations": ["QA_OBSERVATION_NOT_SOURCE"],
            "required_context": ["CONTEXT_ONLY_NOT_INDEPENDENT_SOURCE"]}}}
    row = {"chunk_id": "chunk:synthetic", "unit_id": parent["unit_id"],
        "document_id": "SYNTHETIC", "format": "pdf", "token_count": 9,
        "configuration_id": "synthetic", "reference_classification": "ILLUSTRATIVE",
        "source": {"text_sha256": sha(source.encode())},
        "lineage": {"section_ids": ["body"]},
        "heading_context_sha256": sha(encode([{"text": "Source heading"}])),
        "mandatory_evidence_refs": {"scope": "complete_verified_unit_only"},
        "parent_binding": {"publication_sha256": sha(encode(parent["publication_identity"])),
                           "memberships_sha256": sha(encode(parent["memberships"]))}}
    return {"chunk": row, "verified_parent": parent, "source_slice": source,
            "heading_context": [{"text": "Source heading"}]}


def test_source_context_qa_separation(view):
    text, binding = embedding_input(view)
    assert text == "Source heading\n\nOriginal publisher prose."
    assert all(v not in text for v in ["MANDATORY_WARNING", "QA_OBSERVATION", "CONTEXT_ONLY"])
    assert binding["reference_classification"] == "ILLUSTRATIVE"
    assert binding["complete_parent_rehydration_required"]
    assert binding["qualification_sha256"]
    assert binding["input_text_sha256"] == sha(text.encode())


@pytest.mark.parametrize("status", ["HOLD", "EXCLUDED"])
def test_nonadmitted_parent_rejected(view, status):
    view["verified_parent"]["admission_status"] = status
    with pytest.raises(ValueError, match="parent_or_qualification"):
        embedding_input(view)


@pytest.mark.parametrize("field", ["mandatory", "complete_unit_only"])
def test_missing_qualification_rejected(view, field):
    view["verified_parent"]["consumer"]["llm_context"]["qualification"][field] = False
    with pytest.raises(ValueError, match="parent_or_qualification"):
        embedding_input(view)


def test_context_only_membership_never_promoted(view):
    view["chunk"]["lineage"]["section_ids"] = ["context"]
    with pytest.raises(ValueError, match="context_only_as_source"):
        embedding_input(view)


def test_tampered_source_rejected(view):
    view["source_slice"] += " injected"
    with pytest.raises(ValueError, match="source_slice_changed"):
        embedding_input(view)


def test_forged_publication_rejected(view):
    view["verified_parent"]["publication_identity"]["sha256"] = "forged"
    with pytest.raises(ValueError, match="parent_or_qualification"):
        embedding_input(view)


def test_parent_bound_search_projection(view):
    text, original = embedding_input(view)
    view["search_representation"] = {"text": text, "complete_parent_required": True,
                                    "role": "SEARCH_ONLY_NOT_INDEPENDENT_EVIDENCE"}
    assert embedding_input(view) == (text, original)
    altered = copy.deepcopy(view)
    altered["search_representation"]["text"] += " QA commentary"
    with pytest.raises(ValueError, match="search_scope_changed"):
        embedding_input(altered)


def test_model_comparison_does_not_change_upstream_ids(view):
    text, binding = embedding_input(view)
    a = embedding_id("model-configuration-A", binding["chunk_id"], sha(text.encode()))
    b = embedding_id("model-configuration-B", binding["chunk_id"], sha(text.encode()))
    assert a != b
    assert a == embedding_id("model-configuration-A", binding["chunk_id"], sha(text.encode()))
    assert view["chunk"]["chunk_id"] == "chunk:synthetic"
