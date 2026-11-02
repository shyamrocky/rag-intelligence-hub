"""Real M8 gateway with official SDK/mock HTTP; NEVER a real inference result."""

import copy
import json
from datetime import date

import httpx
import pytest

from tools.generation.openai_adapter import OpenAIAdapter
from tools.generation.profiles import HERE, load_settings
from tools.generation.service import GenerationService
from tools.generation.tests.test_adapter import sdk_fixture, sdk_response
from tools.pre_generation_gate.assembly import PromptAssemblyGate
from tools.pre_generation_gate.tests.test_live import package, question, sample, service

__all__ = ["package", "question", "sample", "service"]
DAY = date(2026, 10, 27)


@pytest.fixture(scope="session")
def prepared(service, question, package, sample):
    gate = PromptAssemblyGate(service)
    return gate, gate.prepare(question, package, sample)


def engine(prepared, *, tokens=1000, raw=None, model="gpt-6-luna", status=200):
    calls = []

    def handler(req):
        calls.append(req.url.path)
        if "/models/" in req.url.path:
            return httpx.Response(
                200, json={"id": model, "created": 0, "object": "model", "owned_by": "owned"}
            )
        if req.url.path.endswith("/input_tokens"):
            return httpx.Response(
                200, json={"object": "response.input_tokens", "input_tokens": tokens}
            )
        return httpx.Response(status, json=raw if raw is not None else sdk_response())

    return GenerationService(
        prepared[0],
        OpenAIAdapter(client=sdk_fixture(handler)),
        load_settings(model=model),
        as_of=DAY,
    ), calls


def test_default_dry_run_never_makes_any_provider_request(prepared, question, package, sample):
    svc, calls = engine(prepared)
    value = svc.dry_run(prepared[1], question, package, sample)
    assert value.audit["blocking_reasons"] == ["PROVIDER_PREFLIGHT_NOT_AUTHORIZED"]
    assert not calls and not value.audit["generation_executed"]
    assert value.audit["usage"]["output_tokens"] is None


def test_missing_key_is_explicit_and_no_source_transfer(
    prepared, question, package, sample, monkeypatch
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    svc = GenerationService(prepared[0], OpenAIAdapter(), load_settings(), as_of=DAY)
    value = svc.dry_run(prepared[1], question, package, sample)
    assert value.audit["blocking_reasons"] == ["OPENAI_API_KEY_MISSING"]
    assert value.audit["cost_estimate"]["status"] == "COST_UNAVAILABLE"


def test_metadata_permission_does_not_imply_corpus_transfer(prepared, question, package, sample):
    svc, calls = engine(prepared)
    value = svc.dry_run(prepared[1], question, package, sample, allow_provider_preflight=True)
    assert value.audit["blocking_reasons"] == ["SOURCE_TRANSFER_FOR_TOKEN_COUNT_NOT_AUTHORIZED"]
    assert len(calls) == 1 and "/models/" in calls[0]


def test_owned_mock_counter_can_qualify_full_wire_context_without_generation(
    prepared, question, package, sample
):
    svc, calls = engine(prepared)
    value = svc.dry_run(
        prepared[1],
        question,
        package,
        sample,
        allow_provider_preflight=True,
        allow_source_transfer=True,
    )
    assert value.audit["status"] == "READY"
    assert value.audit["generator_input_tokens"] == 1000
    assert value.audit["usage"]["output_tokens"] is None
    assert value.audit["cost_estimate"]["status"] == "ESTIMATED_MAX_API_COST"
    assert len(calls) == 2 and not value.audit["generation_executed"]
    # READY here is from an explicitly OWNED MOCK counter, not project qualification.


def test_context_overflow_never_invokes_generation(prepared, question, package, sample):
    svc, calls = engine(prepared, tokens=1050000)
    value = svc.dry_run(
        prepared[1],
        question,
        package,
        sample,
        allow_provider_preflight=True,
        allow_source_transfer=True,
    )
    assert value.audit["status"] == "BLOCKED_CONTEXT" and len(calls) == 2


def test_live_requires_both_explicit_opt_ins(prepared, question, package, sample):
    svc, calls = engine(prepared)
    value = svc.generate(prepared[1], question, package, sample)
    assert value.audit["status"] == "BLOCKED_CONFIGURATION" and not calls


def test_owned_mock_single_call_captures_usage_cost_and_variance(
    prepared, question, package, sample
):
    svc, calls = engine(prepared)
    value = svc.generate(
        prepared[1],
        question,
        package,
        sample,
        allow_paid_inference=True,
        allow_source_transfer=True,
    )
    assert value.audit["status"] == "GENERATED_STRUCTURE_VALID"
    assert value.audit["usage"]["cost_status"] == "ESTIMATED_API_COST"
    assert value.audit["usage"]["reasoning_tokens"] == 30
    assert value.audit["predicted_vs_observed"]["input_tokens_delta"] == 0
    assert value.audit["predicted_vs_observed"]["unused_output_reservation"] == 3996
    assert len(calls) == 3 and calls[-1].endswith("/responses")
    assert "Owned fixture no answer." not in json.dumps(value.audit)
    assert "Owned fixture no answer." not in repr(value)


def test_invalid_model_json_still_retains_cost_telemetry(prepared, question, package, sample):
    raw = sdk_response()
    raw["output"][0]["content"][0]["text"] = "not json"
    svc, calls = engine(prepared, raw=raw)
    value = svc.generate(
        prepared[1],
        question,
        package,
        sample,
        allow_paid_inference=True,
        allow_source_transfer=True,
    )
    assert value.audit["status"] == "INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE"
    assert value.audit["usage"]["cost_status"] == "ESTIMATED_API_COST" and len(calls) == 3


def test_model_switch_recounts_and_reprices(prepared, question, package, sample):
    values = []
    for model in ["gpt-6-luna", "gpt-6.1-terra"]:
        svc, calls = engine(prepared, model=model)
        values.append(
            svc.dry_run(
                prepared[1],
                question,
                package,
                sample,
                allow_provider_preflight=True,
                allow_source_transfer=True,
            ).audit
        )
        assert len(calls) == 2
    assert values[0]["request_sha256"] != values[1]["request_sha256"]
    assert (
        values[0]["cost_estimate"]["estimated_max_cost_usd"]
        != values[1]["cost_estimate"]["estimated_max_cost_usd"]
    )


def test_tampered_or_stale_evidence_blocks_before_any_provider_call(
    prepared, question, package, sample
):
    altered = copy.deepcopy(package)
    altered["llm_evidence"] += "tampered"
    svc, calls = engine(prepared)
    value = svc.dry_run(
        prepared[1],
        question,
        altered,
        sample,
        allow_provider_preflight=True,
        allow_source_transfer=True,
    )
    assert value.audit["status"] == "BLOCKED_INTEGRITY" and not calls


def test_provider_failure_marks_usage_and_cost_unknown(prepared, question, package, sample):
    svc, calls = engine(
        prepared, raw={"error": {"message": "PRIVATE_SOURCE_FIXTURE", "type": "owned"}}, status=500
    )
    value = svc.generate(
        prepared[1],
        question,
        package,
        sample,
        allow_paid_inference=True,
        allow_source_transfer=True,
    )
    assert value.audit["status"] == "PROVIDER_ERROR" and len(calls) == 3
    assert value.audit["usage"]["total_estimated_cost_usd"] is None
    assert value.audit["usage"]["latency_ms"] is not None
    assert "PRIVATE_SOURCE_FIXTURE" not in json.dumps(value.audit)


def test_changed_model_profile_after_count_blocks_invocation(
    prepared, question, package, sample, monkeypatch
):
    svc, calls = engine(prepared)
    svc.profiles = json.loads((HERE / "model-profiles-v1.json").read_bytes())
    original_count = svc.adapter.count

    def changed_count(request):
        receipt = original_count(request)
        svc.profiles["profiles"]["gpt-6-luna"]["context_window"] -= 1
        return receipt

    monkeypatch.setattr(svc.adapter, "count", changed_count)
    value = svc.generate(
        prepared[1],
        question,
        package,
        sample,
        allow_paid_inference=True,
        allow_source_transfer=True,
    )
    assert value.audit["status"] == "BLOCKED_INTEGRITY"
    assert not value.audit["generation_executed"] and len(calls) == 2
