"""Restricted seven-case recovery: source preservation and fail-closed consumers."""

import copy
import json
from pathlib import Path

import pytest
from test_markdown_qualification import census, staged  # noqa: F401

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.markdown_handoff import load_units
from rag_hub.markdown_illustrative import (
    DEFECTS,
    PREVIOUS,
    SCORE,
    restricted_payload,
    source_issue_register,
    validate_illustrative_handoff,
    validate_restricted_payload,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("number", [91, 103, 119, 181, 182, 183, 184])
def test_seven_cases_have_restricted_source_backed_scope(census, number):  # noqa: F811 -- imported pytest fixture
    row = next(c for c in census["sections"] if c["block_id"] == f"C04:b{number:05d}")
    assert row["assessment"] == "candidate"
    assert row["raw_Section_not_qualified_for_direct_retrieval"]
    assert row["qualification_scope"] == (
        "ILLUSTRATIVE_SOURCE_DEFECT" if number in DEFECTS else "ILLUSTRATIVE_METRIC_UNVERIFIED"
    )
    units = [u for u in census["units"] if u["unit_id"] in row["qualified_unit_ids"]]
    assert len(units) == 1
    u = units[0]
    assert u["whole_unit_required"] and u["supporting_heading_ids"]
    assert u["restricted_projection"]["warnings"]
    assert not u["documentation_scope"]["tested_or_executable_guidance"]
    if number in DEFECTS:
        assert u["provider_tab"]
        assert u["restricted_projection"]["source_defect"] == DEFECTS[number]


def test_107_candidates_55_units_and_40_decisions_preserved(census):  # noqa: F811 -- imported pytest fixture
    previous = json.loads((ROOT / PREVIOUS).read_bytes())
    assert census["counts"] == {"historical": 40, "candidate": 114, "excluded": 4}
    assert len(census["units"]) == 59
    assert census["units"][:55] == previous["units"]
    rows = {c["section_id"]: c for c in census["sections"]}
    for old in previous["sections"]:
        now = rows[old["section_id"]]
        assert now["historical_decision"] == old["historical_decision"]
        assert now["normalized_sha256"] == old["normalized_sha256"]
        assert now["source_span"] == old["source_span"]
        if old["assessment"] in ("candidate", "historical", "excluded"):
            assert now["assessment"] == old["assessment"]


@pytest.mark.parametrize("index", range(4))
def test_projection_characters_have_exact_source_spans_and_warning_text(census, index):  # noqa: F811 -- imported pytest fixture
    unit = census["units"][-4:][index]
    raw = (ROOT / census["source"]["raw_path"]).read_bytes()
    for segment in unit["restricted_projection"]["segments"]:
        a, b = segment["bytes_0based_end_exclusive"]
        assert raw[a:b].decode() == segment["text"]
        assert digest(raw[a:b]) == segment["text_sha256"]
    payload = restricted_payload(unit)
    validate_restricted_payload(ROOT, payload, expected_unit_id=unit["unit_id"])
    assert all(w in payload["consumable_text"] for w in payload["warnings"])
    assert payload["not_executable_guidance"] is True
    assert payload["raw_Sections_are_provenance_only"] is True


def test_source_errors_stay_verbatim_and_score_claims_are_not_consumable(census):  # noqa: F811 -- imported pytest fixture
    units = census["units"][-4:]
    originals = [
        next(
            s["text"]
            for s in u["restricted_projection"]["segments"]
            if s["role"] == "verbatim_defective_publisher_code"
        )
        for u in units[:3]
    ]
    assert "from langchain-voyageai import VoyageAIEmbeddings" in originals[0]
    assert "from langchain_voyageai" not in originals[0]
    if_line, statement = originals[1].splitlines()[3:5]
    assert len(if_line) - len(if_line.lstrip()) == len(statement) - len(statement.lstrip())
    assert "credentials = boto3.Session" in originals[2]
    assert "import boto3" not in originals[2]
    metric = units[-1]
    group = metric["required_section_ids"] + metric["supporting_heading_ids"]
    assert all(any(f":b{n:05d}:" in sid for sid in group) for n in SCORE)
    consumable = restricted_payload(metric)["consumable_text"]
    assert "Score meaning varies by provider." in consumable
    assert "similarity_search_with_score" in consumable
    assert "Score: 0.23699893057346344" in consumable
    assert "is a distance metric" not in consumable
    assert "varies inversely with similarity" not in consumable
    assert "$51.2 billion" not in consumable
    assert len(metric["restricted_projection"]["omitted_from_consumable_projection"]) == 3


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("tamper", ["warnings", "text", "classification", "executable", "segment"])
def test_restricted_payload_tampering_fails_closed(census, index, tamper):  # noqa: F811 -- imported pytest fixture
    unit = census["units"][-4:][index]
    payload = copy.deepcopy(restricted_payload(unit))
    if tamper == "warnings":
        del payload["warnings"]
    elif tamper == "text":
        payload["consumable_text"] = (
            "A verified working implementation; score is a distance metric."
        )
    elif tamper == "classification":
        payload["classification"] = "STANDARD_EXECUTABLE"
    elif tamper == "executable":
        payload["not_executable_guidance"] = False
    else:
        payload["segments"] = payload["segments"][:-1]
    with pytest.raises(ValueError, match="altered_or_incomplete"):
        validate_restricted_payload(ROOT, payload, expected_unit_id=unit["unit_id"])


def test_dashboard_separates_actual_admissions_proposals_and_source_errors(census):  # noqa: F811 -- imported pytest fixture
    ids = [c["section_id"] for c in census["sections"] if c["assessment"] == "historical"]
    register = source_issue_register(
        ROOT, census, authoritative_check={"admitted_section_ids": ids, "test_only": True}
    )
    assert len(register["sections"]) == 158
    assert len(register["issues"]) == 42
    assert register["current_admitted"] == 40
    assert register["proposed_after_integration"] == 154
    assert sum(c["confirmed_original_source_defect"] for c in register["sections"]) == 3
    for c in register["sections"]:
        assert c["qa_evidence_sha256"] == digest(encode(census))
        assert c["current_authoritative_QA"]["ledger_sha256"]
        if any(f":b{n:05d}:" in c["section_id"] for n in set(DEFECTS) | SCORE):
            assert c["retrieval_eligible"] is False
            assert c["proposed_eligibility_after_integration"] is True
            assert c["required_warning_or_limitation"]
            assert c["raw_Section_proposed_for_retrieval"] is False
        if c["confirmed_original_source_defect"]:
            assert c["source_defect_resolution"] == "unresolved_original_source_error"
            assert c["issue_origin"] == "source"
            assert c["parsing_status"] == "exact_source_correspondence_verified"


def test_seven_only_assessment_reuses_frozen_audits(monkeypatch):
    import rag_hub.markdown_qualification as policy
    import rag_hub.markdown_residual as previous_policy

    def forbidden(*args, **kwargs):
        raise AssertionError("must not restart an earlier audit or assessment")

    monkeypatch.setattr(policy, "audit", forbidden)
    monkeypatch.setattr(previous_policy, "assess_residual", forbidden)
    assert policy.assess(ROOT)["illustrative_sections_reassessed"] == 7


@pytest.fixture(scope="module")
def integrated_projection(staged):  # noqa: F811 -- imported pytest fixture
    from test_markdown_qualification import _arguments

    from rag_hub.shared.qa import assess as shared_assess

    root, selection, _ = staged
    qa = shared_assess(*_arguments(root), markdown_qualification=selection)
    publication = {
        "schema": "markdown-unit-QA-publication-1.0",
        "status": "AUTHORITATIVE_SHARED_QA",
        "qa": qa,
    }
    p = root / "SYNTHETIC-illustrative-publication.json"
    p.write_bytes(encode(publication))
    descriptor = dict(selection, publication_path=p.name, publication_sha256=digest(p.read_bytes()))
    return root, descriptor, load_units(root, admission=descriptor), publication


@pytest.mark.parametrize(
    "tamper",
    [
        "warnings",
        "heading",
        "member",
        "source_evidence",
        "raw_section",
        "contract",
        "provenance_text",
        "decision_scope",
        "provider",
        "source_identity",
    ],
)
def test_handoff_requires_warnings_and_complete_context(integrated_projection, tamper):
    root, _, units, _ = integrated_projection
    restricted = [u for u in units if u.get("restricted_projection")]
    assert len(restricted) == 4
    for view in restricted:
        validate_illustrative_handoff(root, view)
        assert all("section" not in m for m in view["members"])
        # A legacy consumer cannot silently use the raw canonical text.
        with pytest.raises(KeyError):
            view["members"][0]["section"]
        broken = copy.deepcopy(view)
        if tamper == "warnings":
            del broken["restricted_projection"]["warnings"]
        elif tamper == "heading":
            broken["heading_context"] = broken["heading_context"][:-1]
        elif tamper == "member":
            broken["members"] = broken["members"][:-1]
        elif tamper == "source_evidence":
            broken["source_evidence"] = []
        elif tamper == "provenance_text":
            canonical = broken["source_evidence"][0]["section"]
            broken["source_evidence"][0]["section"] = canonical.model_copy(
                update={"text": "source defect concealed"}
            )
        elif tamper == "decision_scope":
            m = next(
                m
                for m in broken["members"]
                if m["decision"].get("basis") == "markdown_verified_content_unit"
            )
            m["decision"]["scope"]["units"] = []
        elif tamper == "provider":
            broken["provider_tab"] = "INVENTED_PROVIDER"
        elif tamper == "source_identity":
            broken["source"]["title"] = "INVENTED_SOURCE"
        elif tamper == "raw_section":
            broken["members"][0]["section"] = view["source_evidence"][0]["section"]
        else:
            del broken["consumption_contract"]
        with pytest.raises(
            ValueError,
            match="illustrative_handoff_contract|illustrative_source_provenance|illustrative_decision_scope|illustrative_source_identity",
        ):
            validate_illustrative_handoff(root, broken)


def test_rehashed_owner_publication_cannot_strip_restrictions(integrated_projection):
    root, descriptor, _, publication = integrated_projection
    forged = copy.deepcopy(publication)
    decision = next(d for d in forged["qa"]["quality_decisions"] if ":b00091:" in d["section_id"])
    decision["scope"]["units"][0]["restricted_projection"]["warnings"] = []
    p = root / "SYNTHETIC-forged-no-warnings.json"
    p.write_bytes(encode(forged))
    with pytest.raises(ValueError, match="not_authoritative_engine_output"):
        load_units(
            root,
            admission=dict(
                descriptor, publication_path=p.name, publication_sha256=digest(p.read_bytes())
            ),
        )
