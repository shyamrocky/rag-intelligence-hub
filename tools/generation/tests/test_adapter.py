"""Official SDK against httpx MockTransport. No real requests or paid inference."""

import copy
import inspect
import json
from datetime import date

import httpx
import openai
import pytest

from tools.generation.openai_adapter import OpenAIAdapter, ProviderError, wire_request
from tools.generation.profiles import check_fit, load_settings, resolve
from tools.generation.service import parse_response
from tools.generation.telemetry import load_pricing, price_usage
from tools.generation.tests.test_telemetry import response
from tools.pre_generation_gate.prompt_v3 import build_request
from tools.pre_generation_gate.response_v2 import response_schema, synthetic_example

DAY = date(2026, 10, 27)


def neutral():
    return build_request(
        "Owned fixture question?",
        {"llm_evidence": "Owned fixture evidence."},
        response_schema(),
        None,
    )


def request():
    cfg = load_settings()
    return wire_request(neutral(), cfg, resolve(cfg, as_of=DAY))


def sdk_response():
    # Fixture has no claim/evidence citations and is not a real model answer.
    answer = {
        "status": "ABSTAINED",
        "answer": "",
        "claims": [],
        "missing_information": ["Owned fixture no answer."],
        "relevant_qualifications": [],
        "requirement_coverage": [],
        "conflicts_detected": [],
    }
    return response() | {
        "id": "resp_owned_fixture",
        "created_at": 0,
        "object": "response",
        "output": [
            {
                "id": "msg_owned_fixture",
                "role": "assistant",
                "status": "completed",
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(answer),
                        "annotations": [],
                        "logprobs": [],
                    }
                ],
            }
        ],
    }


def sdk_fixture(handler):
    return openai.OpenAI(
        api_key="owned-test-fixture",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_official_sdk_request_count_and_usage_fields_are_wired():
    calls = []

    def handler(req):
        calls.append((req.url.path, json.loads(req.content) if req.content else {}))
        if "/models/" in req.url.path:
            return httpx.Response(
                200, json={"id": "gpt-6-luna", "created": 0, "object": "model", "owned_by": "owned"}
            )
        if req.url.path.endswith("/input_tokens"):
            return httpx.Response(
                200, json={"input_tokens": 100, "object": "response.input_tokens"}
            )
        return httpx.Response(200, json=sdk_response())

    adapter = OpenAIAdapter(client=sdk_fixture(handler))
    wire = request()
    assert adapter.verify_model("gpt-6-luna")["status"] == "ACCOUNT_MODEL_ACCESS_VERIFIED"
    count = adapter.count(wire)
    raw, usage = adapter.invoke(wire)
    assert count["input_tokens"] == 100 and usage["cache_write_tokens"] == 100
    assert usage["cache_write_30m_tokens"] == 100  # SDK extras survive model_dump.
    assert price_usage(usage, load_pricing(), as_of=DAY)["cost_status"] == "ESTIMATED_API_COST"
    assert len(calls) == 3
    assert calls[1][1]["input"] == wire["input"] and calls[1][1]["text"] == wire["text"]
    assert calls[2][1] == wire
    assert parse_response(raw, set())["status"] == "ABSTAINED"


def test_wire_framing_preserves_schema_constraints_and_all_message_bytes():
    before = copy.deepcopy(neutral())
    wire = request()
    assert wire["input"] == before["messages"]
    expected = copy.deepcopy(response_schema())
    expected.pop("$schema")
    expected.pop("$id")
    assert wire["text"]["format"]["schema"] == expected
    assert wire["store"] is False and wire["truncation"] == "disabled"
    assert wire["service_tier"] == "default" and "temperature" not in wire
    assert "requirement_coverage" in expected["required"]


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-terra"])
def test_switch_by_configuration_only(model):
    cfg = load_settings(model=model)
    profile = resolve(cfg, as_of=DAY)
    wire = wire_request(neutral(), cfg, profile)
    assert wire["model"] == model and wire["input"] == request()["input"]
    assert check_fit(profile, cfg, 100)["fits"]


@pytest.mark.parametrize(
    "kind", ["unknown_model", "temperature", "reasoning", "output", "tier", "region", "stale"]
)
def test_invalid_model_configuration(kind):
    cfg = load_settings()
    updates = {}
    if kind == "unknown_model":
        updates = {"model": "not-qualified"}
    elif kind == "temperature":
        updates = {"temperature": 0.5}
    elif kind == "reasoning":
        updates = {"reasoning_effort": "ultra"}
    elif kind == "output":
        updates = {"max_output_tokens": 128001}
    elif kind == "tier":
        updates = {"service_tier": "auto"}
    elif kind == "region":
        updates = {"region": "unconfigured-region"}
    with pytest.raises(ValueError):
        resolve(cfg.model_copy(update=updates), as_of=date(2026, 11, 4) if kind == "stale" else DAY)


def test_context_limit_includes_output_and_margin():
    cfg = load_settings()
    profile = resolve(cfg, as_of=DAY)
    limit = profile["context_window"] - cfg.max_output_tokens - cfg.safety_margin_tokens
    assert check_fit(profile, cfg, limit)["fits"]
    assert not check_fit(profile, cfg, limit + 1)["fits"]


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "AUTHENTICATION"),
        (403, "AUTHENTICATION"),
        (404, "UNAVAILABLE"),
        (429, "RATE_LIMIT"),
        (500, "TRANSIENT"),
        (400, "SCHEMA_REJECTED"),
    ],
)
def test_errors_redact_provider_text_and_do_not_retry(status, expected):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            status,
            json={"error": {"message": "PRIVATE_SOURCE_AND_CREDENTIAL_FIXTURE", "type": "owned"}},
        )

    adapter = OpenAIAdapter(client=sdk_fixture(handler))
    with pytest.raises(ProviderError) as info:
        adapter.invoke(request())
    assert expected in str(info.value)
    assert "PRIVATE_SOURCE" not in str(info.value) and len(calls) == 1
    assert info.value.latency_ms is not None


def test_timeout_is_redacted():
    def handler(req):
        raise httpx.ReadTimeout("PRIVATE_SOURCE_FIXTURE", request=req)

    with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
        OpenAIAdapter(client=sdk_fixture(handler)).invoke(request())


def test_missing_key_and_sdk_logging_base_override_checks(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAIAdapter().configuration_error() == "OPENAI_API_KEY_MISSING"
    monkeypatch.setenv("OPENAI_API_KEY", "owned-test-fixture")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://invalid.example")
    assert "BASE_URL" in OpenAIAdapter().configuration_error()
    monkeypatch.delenv("OPENAI_BASE_URL")
    monkeypatch.setenv("OPENAI_LOG", "debug")
    assert "LOGGING" in OpenAIAdapter().configuration_error()


@pytest.mark.parametrize(
    "kind",
    [
        "not_completed",
        "non_json",
        "unauthorized",
        "example",
        "duplicate",
        "refusal",
        "missing_fields",
    ],
)
def test_malformed_or_unauthorized_structured_response(kind):
    raw = sdk_response()
    if kind == "not_completed":
        raw["status"] = "incomplete"
    elif kind == "refusal":
        raw["output"][0]["content"] = [{"type": "refusal", "refusal": "Owned fixture."}]
    else:
        text = raw["output"][0]["content"][0]
        if kind == "non_json":
            text["text"] = "not json"
        elif kind == "duplicate":
            text["text"] = '{"status":"ABSTAINED","status":"ANSWERED"}'
        elif kind == "missing_fields":
            text["text"] = "{}"
        else:
            value = synthetic_example()
            if kind == "unauthorized":
                value = json.loads(json.dumps(value).replace("EXAMPLE-UNIT-001", "forged:unit"))
            text["text"] = json.dumps(value)
    with pytest.raises(ValueError):
        parse_response(raw, {"owned:unit"})


def test_sdk_has_required_count_and_create_parameters():
    from openai.resources.responses.input_tokens import InputTokens
    from openai.resources.responses.responses import Responses

    assert {"model", "input", "text", "reasoning", "truncation"} <= set(
        inspect.signature(InputTokens.count).parameters
    )
    assert "prompt_cache_options" in inspect.signature(Responses.create).parameters


@pytest.mark.parametrize("value", [None, True, -1, 1.5])
def test_unqualified_counter_values_cannot_become_ready(value):
    def handler(req):
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": value})

    with pytest.raises(ProviderError):
        OpenAIAdapter(client=sdk_fixture(handler)).count(request())


def test_strict_output_reservation_cannot_be_boolean():
    with pytest.raises(ValueError):
        resolve(load_settings().model_copy(update={"max_output_tokens": True}), as_of=DAY)


def test_optional_controls_follow_explicit_owned_profile():
    # Owned capability override proves parameter plumbing, NOT Luna qualification.
    cfg = load_settings().model_copy(update={"temperature": 0.2})
    profile = resolve(load_settings(), as_of=DAY)
    profile["temperature_supported"] = True
    assert wire_request(neutral(), cfg, profile)["temperature"] == 0.2
