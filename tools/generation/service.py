"""One dry run or explicitly opted-in invocation, reusing actual live prompt validation."""

import json
from dataclasses import dataclass, field
from decimal import Decimal

from tools.generation.diagnostics import ResponseValidationError, shape_error
from tools.generation.openai_adapter import ProviderError, wire_request
from tools.generation.profiles import ProfileError, check_fit, resolve
from tools.generation.telemetry import empty_usage, estimate_max_cost, load_pricing, price_usage
from tools.pre_generation_gate.assembly import PromptAssemblyGate
from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.response_v2 import validate_response_shape


@dataclass(frozen=True)
class GenerationResult:
    audit: dict
    response: dict | None = field(default=None, repr=False)


def parse_response(response, authorized_ids):
    if not isinstance(response, dict):
        raise ResponseValidationError('PROVIDER_RESPONSE_OBJECT_REQUIRED')
    if response.get("status") != "completed":
        raise ResponseValidationError("PROVIDER_RESPONSE_NOT_COMPLETED", path=['status'])
    pieces = []
    output = response.get('output', [])
    if not isinstance(output, list):
        raise ResponseValidationError('PROVIDER_OUTPUT_ARRAY_REQUIRED', path=['output'])
    for i, item in enumerate(output):
        if not isinstance(item, dict):
            raise ResponseValidationError('PROVIDER_MESSAGE_OBJECT_REQUIRED', path=['output', i])
        if item.get("type") == "reasoning":
            continue
        if item.get("type") != "message":
            raise ResponseValidationError("UNEXPECTED_PROVIDER_OUTPUT_TYPE", path=['output'])
        contents = item.get('content', [])
        if not isinstance(contents, list):
            raise ResponseValidationError('PROVIDER_CONTENT_ARRAY_REQUIRED', path=['output', i, 'content'])
        for j, content in enumerate(contents):
            if not isinstance(content, dict):
                raise ResponseValidationError('PROVIDER_CONTENT_OBJECT_REQUIRED', path=['output', i, 'content', j])
            if content.get("type") != "output_text":
                raise ResponseValidationError("REFUSAL_OR_UNSUPPORTED_RESPONSE_CONTENT", path=['output', 'content'])
            if not isinstance(content.get('text'), str):
                raise ResponseValidationError('PROVIDER_TEXT_REQUIRED', path=['output', i, 'content', j, 'text'])
            pieces.append(content["text"])

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ResponseValidationError("DUPLICATE_RESPONSE_JSON_KEY", path=['output', 'text'])
            value[key] = item
        return value

    try:
        value = json.loads("".join(pieces), object_pairs_hook=unique_pairs)
    except (json.JSONDecodeError, RecursionError):
        raise ResponseValidationError('MALFORMED_RESPONSE_JSON', path=['output', 'text']) from None
    try:
        return validate_response_shape(value, authorized_unit_ids=authorized_ids).model_dump()
    except (ValueError, TypeError, KeyError) as error:
        raise shape_error(error, value, authorized_ids) from None


class GenerationService:
    def __init__(self, gate, adapter, settings, *, profiles=None, pricing=None, as_of=None):
        if type(gate) is not PromptAssemblyGate:
            raise ValueError("REAL_CURRENT_PROMPT_GATE_REQUIRED")
        self.gate, self.adapter, self.settings = gate, adapter, settings
        self.profiles, self.pricing, self.as_of = profiles, pricing or load_pricing(), as_of

    def dry_run(
        self,
        prepared,
        question,
        package,
        result,
        *,
        allow_provider_preflight=False,
        allow_source_transfer=False,
    ):
        audit = {
            "schema": "generation-result-1.0",
            "mode": "DRY_RUN",
            "model": self.settings.model,
            "status": "BLOCKED_CONFIGURATION",
            "blocking_reasons": [],
            "prompt_template": self.settings.prompt_version,
            "response_schema": self.settings.response_schema,
            "model_access": "UNVERIFIED",
            "generator_input_tokens": None,
            "usage": empty_usage(self.settings.model),
            "generation_executed": False,
            "semantic_sufficiency_evaluated": False,
        }

        def blocked(status, reason):
            audit.update(status=status, blocking_reasons=[reason])
            return GenerationResult(audit)

        try:
            profile = resolve(self.settings, self.profiles, as_of=self.as_of)
        except ProfileError as error:
            return blocked("BLOCKED_CONFIGURATION", str(error))
        except (ValueError, TypeError, KeyError):
            return blocked("BLOCKED_CONFIGURATION", "MODEL_PROFILE_OR_PARAMETERS_INVALID")
        try:
            current = self.gate.validate_preparation(prepared, question, package, result)
        except (ValueError, TypeError, KeyError, OSError):
            return blocked("BLOCKED_INTEGRITY", "STALE_OR_TAMPERED_PROMPT_OR_M8_INPUT")
        if current.payload is None:
            return blocked(current.audit["status"], current.audit["blocking_reasons"][0])
        if (
            current.audit["source_integrity"] != "LIVE_M8_VALIDATED"
            or current.audit["template_version"] != self.settings.prompt_version
            or current.audit["response_schema_version"] != self.settings.response_schema
        ):
            return blocked("BLOCKED_INTEGRITY", "PROMPT_SOURCE_OR_VERSION_BINDING_INVALID")
        # The preserved model-independent gate remains blocked pending qualification.
        # This separate envelope qualifies the exact provider wire request. It does
        # not rewrite or pretend that its earlier assembly audit became READY.
        if current.audit["blocking_reasons"] != ["NO_OWNER_AUTHORIZED_GENERATOR_CONFIGURATION"]:
            return blocked("BLOCKED_CONFIGURATION", "UNSUPPORTED_PROMPT_CONFIGURATION_STATE")
        request = wire_request(current.payload["request"], self.settings, profile)
        audit.update(
            prompt_assembly_status=current.audit["status"],
            neutral_request_sha256=current.audit["request_sha256"],
            request_sha256=digest(request),
            M8_package_sha256=digest(package),
            model_profile=profile,
            settings=self.settings.model_dump(),
            source_integrity="LIVE_M8_VALIDATED",
        )
        audit["cost_estimate"] = estimate_max_cost(
            self.settings.model,
            None,
            self.settings.max_output_tokens,
            self.pricing,
            tier=self.settings.service_tier,
            region=self.settings.region,
            as_of=self.as_of,
        )
        if reason := self.adapter.configuration_error():
            return blocked("BLOCKED_CONFIGURATION", reason)
        if not allow_provider_preflight:
            return blocked("BLOCKED_CONFIGURATION", "PROVIDER_PREFLIGHT_NOT_AUTHORIZED")
        try:
            audit["model_access"] = self.adapter.verify_model(self.settings.model)["status"]
            if not allow_source_transfer:
                return blocked(
                    "BLOCKED_CONFIGURATION", "SOURCE_TRANSFER_FOR_TOKEN_COUNT_NOT_AUTHORIZED"
                )
            count = self.adapter.count(request)
            if count["request_sha256"] != digest(request):
                return blocked("BLOCKED_INTEGRITY", "TOKEN_COUNT_REQUEST_BINDING_MISMATCH")
            audit.update(token_count_receipt=count, generator_input_tokens=count["input_tokens"])
            fit = check_fit(profile, self.settings, count["input_tokens"])
            audit["context_fit"] = fit
            audit["cost_estimate"] = estimate_max_cost(
                self.settings.model,
                count["input_tokens"],
                self.settings.max_output_tokens,
                self.pricing,
                tier=self.settings.service_tier,
                region=self.settings.region,
                as_of=self.as_of,
            )
            if not fit["fits"]:
                return blocked("BLOCKED_CONTEXT", "FULL_REQUEST_CONTEXT_OR_OUTPUT_RESERVE_EXCEEDED")
            self.gate.validate_preparation(prepared, question, package, result)
        except ProviderError as error:
            return blocked("BLOCKED_CONFIGURATION", str(error))
        except (ValueError, TypeError, KeyError, OSError):
            return blocked("BLOCKED_INTEGRITY", "SOURCE_OR_COUNT_BINDINGS_CHANGED")
        audit.update(status="READY", blocking_reasons=[])
        return GenerationResult(audit)

    def generate(
        self,
        prepared,
        question,
        package,
        result,
        *,
        allow_paid_inference=False,
        allow_source_transfer=False,
    ):
        if not allow_paid_inference or not allow_source_transfer:
            return GenerationResult(
                {
                    "schema": "generation-result-1.0",
                    "mode": "LIVE",
                    "status": "BLOCKED_CONFIGURATION",
                    "blocking_reasons": ["EXPLICIT_PAID_AND_SOURCE_TRANSFER_OPT_IN_REQUIRED"],
                    "generation_executed": False,
                    "usage": empty_usage(self.settings.model),
                }
            )
        dry = self.dry_run(
            prepared,
            question,
            package,
            result,
            allow_provider_preflight=True,
            allow_source_transfer=True,
        )
        if dry.audit["status"] != "READY":
            return dry
        audit = dict(dry.audit)
        audit["mode"] = "LIVE"
        # Revalidate immediately before the single paid request; no receipt cache,
        # hidden retries, alternate-model fallback or stale dry-run authorization.
        try:
            current = self.gate.validate_preparation(prepared, question, package, result)
            profile = resolve(self.settings, self.profiles, as_of=self.as_of)
            if digest(profile) != digest(audit["model_profile"]):
                raise ValueError("MODEL_PROFILE_CHANGED_AFTER_COUNT")
            request = wire_request(current.payload["request"], self.settings, profile)
            if digest(request) != audit["request_sha256"]:
                raise ValueError("REQUEST_CHANGED_AFTER_COUNT")
        except (ValueError, TypeError, KeyError, OSError):
            audit.update(
                status="BLOCKED_INTEGRITY",
                blocking_reasons=["SOURCE_OR_REQUEST_CHANGED_BEFORE_INVOCATION"],
            )
            return GenerationResult(audit)
        try:
            raw, usage = self.adapter.invoke(request)
        except ProviderError as error:
            audit.update(
                status="PROVIDER_ERROR",
                blocking_reasons=[str(error)],
                generation_executed=True,
                usage=empty_usage(
                    self.settings.model,
                    latency_ms=error.latency_ms,
                    response_status="PROVIDER_ERROR",
                ),
            )
            audit["usage"]["cost_reasons"] = ["REQUEST_MAY_HAVE_BEEN_BILLED_BUT_USAGE_UNAVAILABLE"]
            return GenerationResult(audit)
        usage = price_usage(usage, self.pricing, region=self.settings.region, as_of=self.as_of)
        audit.update(
            usage=usage,
            generation_executed=True,
            response_status=raw.get("status"),
            response_id=raw.get("id"),
            response_sha256=digest(raw),
        )
        estimate = audit["cost_estimate"]
        audit["predicted_vs_observed"] = {
            "input_tokens_delta": usage["input_tokens"] - audit["generator_input_tokens"]
            if usage["input_tokens"] is not None
            else None,
            "unused_output_reservation": self.settings.max_output_tokens - usage["output_tokens"]
            if usage["output_tokens"] is not None
            else None,
            "observed_cost_minus_estimated_max_usd": str(
                Decimal(usage["total_estimated_cost_usd"])
                - Decimal(estimate["estimated_max_cost_usd"])
            )
            if usage["total_estimated_cost_usd"] is not None
            and estimate["estimated_max_cost_usd"] is not None
            else None,
        }
        try:
            if raw.get("model") != self.settings.model:
                raise ValueError("RESPONSE_MODEL_MISMATCH")
            answer = parse_response(raw, {p["evidence"]["unit_id"] for p in package["parents"]})
            audit.update(
                status="GENERATED_STRUCTURE_VALID",
                blocking_reasons=[],
                answer_status=answer["status"],
                claim_count=len(answer["claims"]),
                citation_count=sum(len(c["supporting_quotes"]) for c in answer["claims"]),
                missing_requirement_count=len(answer["missing_information"]),
                reported_conflict_count=len(answer["conflicts_detected"]),
            )
            return GenerationResult(audit, answer)
        except (ValueError, TypeError, KeyError):
            audit.update(
                status="INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE",
                blocking_reasons=["RESPONSE_STRUCTURE_OR_IDENTITY_INVALID"],
            )
            return GenerationResult(audit)
