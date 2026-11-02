"""Synthetic structural and quotation controls; not real retrieval results."""
import copy
from pathlib import Path

import pytest

from tools.quality_dashboard.post_generation import assess_structure, quote_reader

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def owned():
    uid = "UNIT-owned-fixture"
    text = "Fictional Atlas supports two search methods."
    package = {"parents": [{"evidence": {"unit_id": uid, "verified_parent": {
        "citation_locators": [{"url": "https://example.test/source"}],
        "consumer": {"llm_context": {"source_content": [{"text": text}],
                                     "qualification": {"mandatory": False}}}}}}]}
    answer = {"status": "ANSWERED", "answer": text,
        "claims": [{"claim_text": text, "evidence_unit_ids": [uid],
                    "supporting_quotes": [{"evidence_unit_id": uid, "quote": text}]}],
        "missing_information": [], "relevant_qualifications": [],
        "requirement_coverage": [{"requirement": "Methods", "status": "SUPPORTED",
                                   "evidence_unit_ids": [uid]}], "conflicts_detected": []}
    return answer, package


def test_valid_schema_ids_and_quotes(owned):
    answer, package = owned
    before = copy.deepcopy(owned)
    result = assess_structure(answer, package, quote_reader(ROOT))
    assert all(c["outcome"] == "PASS" for c in result["checks"])
    assert result["semantic_entailment"] == "NOT_CERTIFIED"
    assert owned == before


@pytest.mark.parametrize("kind", ["missing_field", "example_id", "omitted_parent", "status_contradiction",
                                  "fake_quote_id", "missing_coverage", "missing_conflicts"])
def test_structural_negative(owned, kind):
    answer, package = owned
    if kind == "missing_field":
        del answer["claims"]
    elif kind in {"example_id", "omitted_parent", "fake_quote_id"}:
        answer["claims"][0]["supporting_quotes"][0]["evidence_unit_id"] = (
            "EXAMPLE-UNIT-001" if kind == "example_id" else "UNIT-not-in-package")
    elif kind == "status_contradiction":
        answer["status"] = "ABSTAINED"
    elif kind == "missing_coverage":
        del answer["requirement_coverage"]
    else:
        del answer["conflicts_detected"]
    with pytest.raises(ValueError):
        assess_structure(answer, package, quote_reader(ROOT))


def test_fabricated_quote_rejected(owned):
    answer, package = owned
    answer["claims"][0]["supporting_quotes"][0]["quote"] = "Invented source quotation."
    result = assess_structure(answer, package, quote_reader(ROOT))
    assert next(c for c in result["checks"] if "Verbatim" in c["check"])["outcome"] == "FAIL"


def test_qa_observation_not_publisher(owned):
    answer, package = owned
    parent = package["parents"][0]["evidence"]["verified_parent"]
    parent["consumer"]["llm_context"]["qa_observations"] = [{"text": "Only QA said this."}]
    answer["claims"][0]["supporting_quotes"][0]["quote"] = "Only QA said this."
    assert not assess_structure(answer, package, quote_reader(ROOT))["quote_checks"]["all_verbatim"]


def test_missing_citation_fails(owned):
    answer, package = owned
    package["parents"][0]["evidence"]["verified_parent"]["citation_locators"] = []
    result = assess_structure(answer, package, quote_reader(ROOT))
    assert result["checks"][-1]["outcome"] == "FAIL"


def test_genuine_unrelated_quote_not_semantic_pass(owned):
    answer, package = owned
    answer["claims"][0]["claim_text"] = "Atlas operates on Mars."
    result = assess_structure(answer, package, quote_reader(ROOT))
    assert result["quote_checks"]["all_verbatim"]
    assert result["semantic_entailment"] == "NOT_CERTIFIED"


def test_public_validator_rejects_fake_gateway():
    from tools.quality_dashboard.post_generation import PostGenerationValidator

    with pytest.raises(ValueError, match="REAL_EXPLICIT_M8"):
        PostGenerationValidator(object())
