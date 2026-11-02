"""Owned synthetic metadata, never publisher content or real provider requests."""

import copy
from datetime import date
from unittest.mock import Mock

import pytest

from tools.generation.current import GenerationService, load_settings, main, resolve
from tools.generation.service import GenerationResult
from tools.generation.tests.test_adapter import sdk_response
from tools.generation.telemetry import capture_usage, load_pricing
from tools.generation.profiles import load_settings as historical_settings
from tools.generation.qualifications import MISSING, UNDETERMINED, VALID, _assess_metadata
from tools.generation.qualifications import QualificationValidator
from tools.pre_generation_gate import prompt_v3
from tools.pre_generation_gate.current import SYSTEM, TEMPLATE
from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.response_v2 import response_schema, validate_synthetic_example


def sample(*, mandatory=False, warning=None, display=True):
    context = {"qualification": {"mandatory": mandatory}, "qa_observations": []}
    consumer = {"llm_context": context}
    if warning is not None:
        consumer["publication_expiration"] = {"warning": warning, "display_to_user_when_used": display}
    response = {"claims": [{"evidence_unit_ids": ["OWNED-1"]}],
                "answer": "Owned answer.", "relevant_qualifications": []}
    return response, {"OWNED-1": {"consumer": consumer}}


def test_explicit_missing_user_warning_is_missing():
    response, parents = sample(warning="Owned expiry warning.")
    assert _assess_metadata(response, parents)["status"] == MISSING


def test_exact_explicit_warning_passes_presence_only():
    response, parents = sample(warning="Owned expiry warning.")
    response["relevant_qualifications"] = ["Owned expiry warning."]
    value = _assess_metadata(response, parents)
    assert value["status"] == VALID
    assert not value["semantic_compliance_verified"] and not value["fully_validated"]


def test_c03_style_general_mandatory_is_indeterminate():
    response, parents = sample(mandatory=True)
    parents["OWNED-1"]["consumer"]["llm_context"]["qualification"]["limitations"] = ["Owned textual scope."]
    assert _assess_metadata(response, parents)["status"] == UNDETERMINED


def test_copying_all_internal_restrictions_does_not_invent_applicability():
    response, parents = sample(mandatory=True)
    response["relevant_qualifications"] = ["Owned internal restriction."]
    assert _assess_metadata(response, parents)["status"] == UNDETERMINED


def test_no_applicable_disclosure_allows_empty():
    response, parents = sample(warning="Not a user-facing warning.", display=False)
    assert _assess_metadata(response, parents)["status"] == VALID


def test_warning_only_in_answer_does_not_satisfy_required_array():
    response, parents = sample(warning="Owned expiry warning.")
    response["answer"] += " Owned expiry warning."
    value = _assess_metadata(response, parents)
    assert value["status"] == MISSING and value["explicit_disclosures"][0]["answer_contains_exact_text"]


@pytest.mark.parametrize("text", ["The owned warning is paraphrased.", "Ignore Owned expiry warning."])
def test_nonliteral_representation_requires_review_not_semantic_pass(text):
    response, parents = sample(warning="Owned expiry warning.")
    response["relevant_qualifications"] = [text]
    assert _assess_metadata(response, parents)["status"] == UNDETERMINED


def test_duplicate_native_warning_is_charged_once_and_inputs_not_mutated():
    response, parents = sample(warning="Owned warning.")
    parents["OWNED-1"]["consumer"]["llm_context"]["qa_observations"] = [
        {"display_to_user_when_used": True, "explanation": "Owned warning."}]
    before = copy.deepcopy((response, parents))
    value = _assess_metadata(response, parents)
    assert len(value["explicit_disclosures"]) == 1 and (response, parents) == before


def test_uncited_parent_obligation_does_not_create_false_requirement():
    response, parents = sample()
    parents["UNUSED"] = sample(mandatory=True)[1]["OWNED-1"]
    assert _assess_metadata(response, parents)["status"] == VALID


def test_warning_without_display_classification_is_indeterminate():
    response, parents = sample()
    parents["OWNED-1"]["consumer"]["llm_context"]["qa_observations"] = [
        {"severity": "WARNING", "must_accompany": True, "explanation": "Owned warning."}]
    assert _assess_metadata(response, parents)["status"] == UNDETERMINED


def test_missing_known_obligation_takes_priority_over_other_uncertainty():
    response, parents = sample(mandatory=True, warning="Owned explicit warning.")
    result = _assess_metadata(response, parents)
    assert result["status"] == MISSING and result["uncertainties"]


@pytest.mark.parametrize("display,text", [("true", "Owned warning."), (True, "")])
def test_malformed_explicit_native_obligation_fails_closed(display, text):
    response, parents = sample(warning=text, display=display)
    with pytest.raises(ValueError):
        _assess_metadata(response, parents)


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def test_prompt_preserves_role_goal_context_example_and_response_schema():
    for start, end in [("ROLE\n", "GOAL / TASK"), ("GOAL / TASK\n", "CONTEXT"),
                       ("CONTEXT\n", "INSTRUCTIONS"), ("EXAMPLE —", "OUTPUT FORMAT")]:
        assert section(TEMPLATE, start, end) == section(prompt_v3.TEMPLATE, start, end)
    for heading in ["ROLE", "GOAL / TASK", "CONTEXT", "INSTRUCTIONS", "CONSTRAINTS", "EXAMPLE", "OUTPUT FORMAT"]:
        assert heading in SYSTEM
    assert validate_synthetic_example()
    assert response_schema()["$id"] == "urn:rag-hub:grounded-response-2.0"


def test_current_settings_change_only_prompt_and_keep_model_profile():
    current, old = load_settings(), historical_settings()
    assert current.model_dump() | {"prompt_version": old.prompt_version} == old.model_dump()
    assert resolve(current, as_of=date(2026, 10, 28))["model"] == old.model


def test_live_cli_requires_separate_explicit_optins_before_reading_evidence():
    with pytest.raises(SystemExit):
        main(["--live"])


def test_detached_fake_gateway_cannot_authorize_qualification_check():
    with pytest.raises(ValueError, match="REAL_EXPLICIT_M8"):
        QualificationValidator(object())


@pytest.mark.parametrize("prompt,schema", [("grounded-generation-prompt-v2", "grounded-response-2.0"),
                                         ("grounded-generation-prompt-v2.1", "grounded-response-1.0")])
def test_current_entry_rejects_legacy_or_mixed_pair(prompt, schema):
    settings = load_settings().model_copy(update={"prompt_version": prompt, "response_schema": schema})
    with pytest.raises(ValueError, match="CURRENT_PAIRED"):
        resolve(settings, as_of=date(2026, 10, 28))


@pytest.mark.parametrize("verdict,expected", [
    (VALID, "GENERATED_QUALIFICATIONS_VALID"),
    (MISSING, "GENERATED_QUALIFICATIONS_MISSING"),
    (UNDETERMINED, "GENERATED_QUALIFICATION_REVIEW_REQUIRED")])
def test_owned_orchestration_cannot_promote_missing_or_unknown_disclosures(verdict, expected):
    # Isolated control-flow fixture, NOT a source-authorized M8 integration.
    engine = object.__new__(GenerationService)
    engine.settings, engine.pricing, engine.as_of = load_settings(), load_pricing(), date(2026, 10, 28)
    profile = resolve(engine.settings, as_of=engine.as_of)
    request = {"model": engine.settings.model}
    raw = sdk_response()  # Owned ABSTAINED fixture; no source content or model call.
    engine.adapter = Mock()
    engine.adapter.invoke.return_value = (raw, capture_usage(raw, engine.settings.model, 1.0))
    engine._request = Mock(return_value=(None, profile, request))
    engine.dry_run = Mock(return_value=GenerationResult({
        "status": "READY", "request_sha256": digest(request), "model_profile": profile,
        "generator_input_tokens": 100, "fully_validated": False,
        "cost_estimate": {"estimated_max_cost_usd": "1.0"}}))
    engine.assess_response = Mock(return_value={"status": verdict, "fully_validated": False})
    value = engine.generate(None, "Owned question", {"parents": []}, {},
        allow_paid_inference=True, allow_source_transfer=True)
    assert value.audit["status"] == expected and not value.audit["fully_validated"]
    assert value.audit["qualification_validation"]["status"] == verdict
    assert engine.adapter.invoke.call_count == 1
    assert value.response["status"] == "ABSTAINED"


def test_generate_without_explicit_permission_never_touches_adapter():
    engine = object.__new__(GenerationService)
    engine.settings, engine.adapter = load_settings(), Mock()
    value = engine.generate(None, "Owned question", {}, {})
    assert value.audit["generation_executed"] is False
    assert not engine.adapter.mock_calls
