"""Official SDK adapter. No automatic retries, fallback, source logging or calls."""

import copy
import logging
import os
import time

from tools.generation.telemetry import capture_usage
from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.response_v2 import response_schema

SCHEMA_TRANSFORMATION = "openai-json-schema-annotations-only-1.0"


class ProviderError(Exception):
    """Safe application code, never provider exception text or HTTP request bodies."""

    def __init__(self, code, *, latency_ms=None, capture=None, usage=None, diagnostics=None):
        super().__init__(code)
        self.latency_ms = latency_ms
        self.capture = capture
        self.usage = usage
        self.diagnostics = diagnostics or [{'code': code, 'path': []}]


def safe_error(error):
    status = getattr(error, "status_code", None)
    if status in {401, 403}:
        return "PROVIDER_AUTHENTICATION_OR_PERMISSION_ERROR"
    if status == 404:
        return "PROVIDER_MODEL_OR_ENDPOINT_UNAVAILABLE"
    if status == 429:
        return "PROVIDER_RATE_LIMIT"
    if "Timeout" in type(error).__name__:
        return "PROVIDER_TIMEOUT"
    if status is not None and status >= 500:
        return "PROVIDER_TRANSIENT_ERROR_NO_RETRY"
    if status == 400:
        return "PROVIDER_REQUEST_OR_SCHEMA_REJECTED"
    return "PROVIDER_OR_SDK_ERROR_NO_RETRY"


def object_dict(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)


def wire_request(neutral, settings, profile):
    """Translate only request framing; keep all three message contents byte-identical."""
    if neutral["response_format"]["schema_version"] != "grounded-response-2.0" or digest(
        neutral["response_format"]["schema"]
    ) != digest(response_schema()):
        raise ValueError("UNSUPPORTED_OR_ALTERED_RESPONSE_SCHEMA")
    messages = copy.deepcopy(neutral["messages"])
    if [m["role"] for m in messages] != ["system", "user", "user"]:
        raise ValueError("UNSUPPORTED_MESSAGE_TRUST_BOUNDARIES")
    if profile["model"] != settings.model:
        raise ValueError("MODEL_PROFILE_BINDING_MISMATCH")
    schema = copy.deepcopy(neutral["response_format"]["schema"])
    # These two identifiers are annotations, not validation constraints. All
    # properties, required fields, bounds, references and Python validators stay.
    schema.pop("$schema", None)
    schema.pop("$id", None)
    request = {
        "model": settings.model,
        "input": messages,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "grounded_response_2_0",
                "strict": True,
                "schema": schema,
            }
        },
        "reasoning": {"effort": settings.reasoning_effort},
        "max_output_tokens": settings.max_output_tokens,
        "store": False,
        "truncation": "disabled",
        "service_tier": settings.service_tier,
        "prompt_cache_options": {"mode": "implicit", "ttl": settings.cache_ttl},
    }
    if settings.temperature is not None:
        if not profile["temperature_supported"]:
            raise ValueError("UNQUALIFIED_TEMPERATURE_PARAMETER")
        request["temperature"] = settings.temperature
    return request


class OpenAIAdapter:
    def __init__(self, *, timeout_seconds=120, client=None, capture_sink=None):
        # Injected clients are for explicitly owned offline provider fixtures.
        self._client = client
        self.timeout_seconds = timeout_seconds
        self.capture_sink = capture_sink
        self.last_capture = None

    def configuration_error(self):
        if self._client is not None:
            return None
        if not os.environ.get("OPENAI_API_KEY"):
            return "OPENAI_API_KEY_MISSING"
        if os.environ.get("OPENAI_BASE_URL"):
            return "UNAPPROVED_OPENAI_BASE_URL_OVERRIDE"
        if os.environ.get("OPENAI_LOG"):
            return "UNSAFE_PROVIDER_SDK_LOGGING_CONFIGURATION"
        try:
            import openai  # noqa: F401
        except ImportError:
            return "OPENAI_SDK_UNAVAILABLE"
        return None

    def _sdk(self):
        if reason := self.configuration_error():
            raise ProviderError(reason)
        if self._client is None:
            from openai import OpenAI

            logging.getLogger("openai").setLevel(logging.WARNING)
            logging.getLogger("httpx").setLevel(logging.WARNING)
            self._client = OpenAI(
                api_key=os.environ["OPENAI_API_KEY"],
                base_url="https://api.openai.com/v1",
                max_retries=0,
                timeout=self.timeout_seconds,
            )
        return self._client

    def verify_model(self, model):
        client = self._sdk()
        from openai import APIError

        try:
            result = object_dict(client.models.retrieve(model))
            if result.get("id") != model:
                raise ProviderError("MODEL_ACCESS_IDENTITY_MISMATCH")
            return {"status": "ACCOUNT_MODEL_ACCESS_VERIFIED", "model": model}
        except ProviderError:
            raise
        except (APIError, ValueError, TypeError, KeyError, OSError, AttributeError) as error:
            raise ProviderError(safe_error(error)) from None

    def count(self, request):
        client = self._sdk()
        from openai import APIError

        # Exactly the content-bearing fields accepted by input_tokens.count;
        # generation-only limits/storage/tier/cache TTL do not add prompt tokens.
        args = {
            k: copy.deepcopy(request[k])
            for k in ["model", "input", "text", "reasoning", "truncation"]
        }
        try:
            # Preserve provider JSON primitive types: typed SDK models can coerce
            # malformed booleans into integers before application validation.
            result = client.responses.input_tokens.with_raw_response.count(
                **args
            ).http_response.json()
            tokens = result.get("input_tokens")
            if (
                type(tokens) is not int
                or tokens < 0
                or result.get("object") != "response.input_tokens"
            ):
                raise ProviderError("INVALID_AUTHORITATIVE_TOKEN_COUNT")
            return {
                "input_tokens": tokens,
                "method": "OPENAI_RESPONSES_INPUT_TOKENS",
                "request_sha256": digest(request),
                "count_payload_sha256": digest(args),
                "includes_messages_framing_and_response_schema": True,
            }
        except ProviderError:
            raise
        except (APIError, ValueError, TypeError, KeyError, OSError, AttributeError) as error:
            raise ProviderError(safe_error(error)) from None

    def invoke(self, request):
        if self.capture_sink is not None and self.capture_sink.receipt is not None:
            raise ProviderError('RAW_RESPONSE_CAPTURE_ALREADY_ATTEMPTED_NO_RETRY')
        client = self._sdk()
        from openai import APIError

        start = time.perf_counter()
        try:
            http = client.responses.with_raw_response.create(
                **copy.deepcopy(request)
            ).http_response
            elapsed = (time.perf_counter() - start) * 1000
            if self.capture_sink is not None:
                self.last_capture = self.capture_sink.capture(http.content, http_status=http.status_code)
            try:
                response = http.json()
                if not isinstance(response, dict):
                    raise TypeError('PROVIDER_RESPONSE_OBJECT_REQUIRED')
            except (ValueError, TypeError):
                code = ('RAW_RESPONSE_CAPTURE_FAILED' if self.last_capture and
                        self.last_capture['status'] == 'RAW_RESPONSE_CAPTURE_FAILED'
                        else 'PROVIDER_RESPONSE_JSON_INVALID')
                raise ProviderError(code, latency_ms=elapsed, capture=self.last_capture) from None
            usage = capture_usage(response, request["model"], elapsed)
            if self.last_capture and self.last_capture['status'] == 'RAW_RESPONSE_CAPTURE_FAILED':
                raise ProviderError('RAW_RESPONSE_CAPTURE_FAILED', latency_ms=elapsed,
                                    capture=self.last_capture, usage=usage)
            return response, usage
        except ProviderError:
            raise
        except (APIError, ValueError, TypeError, KeyError, OSError, AttributeError) as error:
            if self.capture_sink is not None and self.last_capture is None:
                http = getattr(error, 'response', None)
                status = getattr(http, 'status_code', None)
                withheld = status in {401, 403}
                self.last_capture = self.capture_sink.capture(
                    None if http is None or withheld else http.content,
                    http_status=status, unavailable_reason='AUTHENTICATION_ERROR_BODY_WITHHELD'
                    if withheld else 'NO_PROVIDER_RESPONSE_RECEIVED' if http is None else None)
            raise ProviderError(
                'RAW_RESPONSE_CAPTURE_FAILED' if self.last_capture and
                self.last_capture['status'] == 'RAW_RESPONSE_CAPTURE_FAILED' else safe_error(error),
                latency_ms=(time.perf_counter() - start) * 1000, capture=self.last_capture,
            ) from None
