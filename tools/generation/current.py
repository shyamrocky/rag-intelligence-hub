"""Current v2.2 experimental orchestration; historical prompt/settings stay replayable.

Reuses M8, canonical prompt lineage, official adapter, model/profile controls,
response parser and cost telemetry. Nothing executes on import.
"""

import json
from decimal import Decimal
from pathlib import Path

from tools.answer_quality.abstention import check_explanation
from tools.generation.diagnostics import ResponseValidationError
from tools.generation.openai_adapter import OpenAIAdapter, ProviderError, wire_request
from tools.generation.profiles import GenerationSettings, ProfileError, check_fit
from tools.generation.profiles import resolve as historical_resolve
from tools.generation.qualifications import MISSING, VALID, QualificationValidator
from tools.generation.service import GenerationResult, parse_response
from tools.generation.telemetry import empty_usage, estimate_max_cost, load_pricing, price_usage
from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.current import DEFAULT_TEMPLATE_VERSION, PromptAssemblyGate


def load_settings(path=None, *, model=None):
    values = json.loads(Path(path or Path(__file__).with_name("settings-v2.2.json")).read_bytes())
    if model is not None:
        values["model"] = model
    return GenerationSettings.model_validate(values)


def resolve(settings, registry=None, *, as_of=None):
    settings = GenerationSettings.model_validate(settings.model_dump(by_alias=True))
    if settings.prompt_version != DEFAULT_TEMPLATE_VERSION or settings.response_schema != "grounded-response-2.0":
        raise ProfileError("CURRENT_PAIRED_PROMPT_SCHEMA_REQUIRED")
    # The model capability registry is unchanged. Only its historical prompt-name
    # guard is bridged; request/audit always retain the actual current identity.
    historical = settings.model_copy(update={"prompt_version": "grounded-generation-prompt-v2"})
    return historical_resolve(historical, registry, as_of=as_of)


class GenerationService:
    def __init__(self, gate, adapter=None, settings=None, *, profiles=None, pricing=None, as_of=None):
        if type(gate) is not PromptAssemblyGate:
            raise ValueError("REAL_CURRENT_PROMPT_GATE_REQUIRED")
        self.gate, self.settings = gate, settings or load_settings()
        self.adapter = adapter or OpenAIAdapter(timeout_seconds=self.settings.timeout_seconds)
        self.profiles, self.pricing, self.as_of = profiles, pricing or load_pricing(), as_of
        self.qualifications = QualificationValidator(gate._service)

    def _request(self, prepared, question, package, result):
        profile = resolve(self.settings, self.profiles, as_of=self.as_of)
        current = self.gate.validate_preparation(prepared, question, package, result)
        if (current.payload is None or current.audit["source_integrity"] != "LIVE_M8_VALIDATED"
                or current.audit["template_version"] != DEFAULT_TEMPLATE_VERSION
                or current.audit["response_schema_version"] != self.settings.response_schema
                or current.audit["blocking_reasons"] != ["NO_OWNER_AUTHORIZED_GENERATOR_CONFIGURATION"]):
            raise ValueError("CURRENT_LIVE_PREPARATION_REQUIRED")
        return current, profile, wire_request(current.payload["request"], self.settings, profile)

    def dry_run(self, prepared, question, package, result, *, allow_provider_preflight=False,
                allow_source_transfer=False):
        audit = {"schema": "qualification-aware-generation-result-1.0", "mode": "DRY_RUN",
            "model": self.settings.model, "status": "BLOCKED_CONFIGURATION", "blocking_reasons": [],
            "prompt_template": self.settings.prompt_version, "response_schema": self.settings.response_schema,
            "model_access": "UNVERIFIED", "generator_input_tokens": None,
            "usage": empty_usage(self.settings.model), "generation_executed": False,
            "semantic_sufficiency_evaluated": False, "fully_validated": False}

        def blocked(status, reason):
            audit.update(status=status, blocking_reasons=[reason])
            return GenerationResult(audit)

        try:
            current, profile, request = self._request(prepared, question, package, result)
        except ProfileError as error:
            return blocked("BLOCKED_CONFIGURATION", str(error))
        except (ValueError, TypeError, KeyError, OSError):
            return blocked("BLOCKED_INTEGRITY", "STALE_OR_INCOMPATIBLE_CURRENT_PREPARATION")
        audit.update(request_sha256=digest(request), neutral_request_sha256=current.audit["request_sha256"],
            M8_package_sha256=digest(package), model_profile=profile, settings=self.settings.model_dump(),
            source_integrity="LIVE_M8_VALIDATED")
        if not allow_provider_preflight:
            return blocked("BLOCKED_CONFIGURATION", "PROVIDER_PREFLIGHT_NOT_AUTHORIZED")
        if not allow_source_transfer:
            return blocked("BLOCKED_CONFIGURATION", "SOURCE_TRANSFER_NOT_AUTHORIZED")
        if reason := self.adapter.configuration_error():
            return blocked("BLOCKED_CONFIGURATION", reason)
        try:
            audit["model_access"] = self.adapter.verify_model(self.settings.model)["status"]
            count = self.adapter.count(request)
            if count["request_sha256"] != digest(request):
                raise ValueError("TOKEN_COUNT_REQUEST_BINDING_MISMATCH")
            audit.update(token_count_receipt=count, generator_input_tokens=count["input_tokens"],
                         context_fit=check_fit(profile, self.settings, count["input_tokens"]))
            audit["cost_estimate"] = estimate_max_cost(self.settings.model, count["input_tokens"],
                self.settings.max_output_tokens, self.pricing, tier=self.settings.service_tier,
                region=self.settings.region, as_of=self.as_of)
            if not audit["context_fit"]["fits"]:
                return blocked("BLOCKED_CONTEXT", "FULL_REQUEST_CONTEXT_OR_RESERVE_EXCEEDED")
            if audit["cost_estimate"]["status"] != "ESTIMATED_MAX_API_COST":
                return blocked("BLOCKED_CONFIGURATION", "CURRENT_PRICING_UNAVAILABLE")
            self.gate.validate_preparation(prepared, question, package, result)
        except ProviderError as error:
            return blocked("BLOCKED_CONFIGURATION", str(error))
        except (ValueError, TypeError, KeyError, OSError):
            return blocked("BLOCKED_INTEGRITY", "SOURCE_OR_COUNT_BINDING_CHANGED")
        audit.update(status="READY", blocking_reasons=[])
        return GenerationResult(audit)

    def assess_response(self, response, package, result):
        return self.qualifications.validate(response, package, result)

    def generate(self, prepared, question, package, result, *, allow_paid_inference=False,
                 allow_source_transfer=False):
        if not allow_paid_inference or not allow_source_transfer:
            return GenerationResult({"status": "BLOCKED_CONFIGURATION",
                "blocking_reasons": ["EXPLICIT_PAID_AND_SOURCE_TRANSFER_OPT_IN_REQUIRED"],
                "generation_executed": False, "fully_validated": False,
                "usage": empty_usage(self.settings.model)})
        self.last_observation = None
        dry = self.dry_run(prepared, question, package, result,
                           allow_provider_preflight=True, allow_source_transfer=True)
        if dry.audit["status"] != "READY":
            return dry
        audit = dry.audit | {"mode": "LIVE"}
        try:
            _, profile, request = self._request(prepared, question, package, result)
            if (digest(request) != audit["request_sha256"]
                    or digest(profile) != digest(audit["model_profile"])):
                raise ValueError("REQUEST_CHANGED_BEFORE_INVOCATION")
        except (ValueError, TypeError, KeyError, OSError):
            return GenerationResult(audit | {"status": "BLOCKED_INTEGRITY",
                "blocking_reasons": ["SOURCE_OR_REQUEST_CHANGED_BEFORE_INVOCATION"]})
        try:
            raw, usage = self.adapter.invoke(request)  # exactly one; SDK retry policy unchanged
        except ProviderError as error:
            unknown = empty_usage(self.settings.model, latency_ms=error.latency_ms,
                                  response_status="PROVIDER_ERROR")
            unknown["cost_reasons"] = ["REQUEST_MAY_HAVE_BEEN_BILLED_BUT_USAGE_UNAVAILABLE"]
            measured = price_usage(error.usage, self.pricing, region=self.settings.region,
                                  as_of=self.as_of) if error.usage is not None else unknown
            return GenerationResult(audit | {"status": 'RAW_RESPONSE_CAPTURE_FAILED'
                if str(error) == 'RAW_RESPONSE_CAPTURE_FAILED' else "PROVIDER_ERROR", "generation_executed": True,
                "blocking_reasons": [str(error)], "usage": measured,
                'raw_response_capture': error.capture, 'response_diagnostics': error.diagnostics})
        capture = getattr(self.adapter, 'last_capture', None)
        if capture is not None:
            audit['raw_response_capture'] = capture
        audit.update(generation_executed=True, response_id=raw.get("id"), response_sha256=digest(raw),
                     response_status=raw.get("status"), usage=price_usage(usage, self.pricing,
                        region=self.settings.region, as_of=self.as_of))
        from tools.generation.observation import observe
        # Untrusted output survives strict parsing; never used as an accepted response.
        self.last_observation = observe(raw)
        measured = audit["usage"]
        audit["predicted_vs_observed"] = {
            "input_tokens_delta": measured["input_tokens"] - audit["generator_input_tokens"]
            if measured["input_tokens"] is not None else None,
            "unused_output_reservation": self.settings.max_output_tokens - measured["output_tokens"]
            if measured["output_tokens"] is not None else None,
            "observed_cost_minus_estimated_max_usd": str(Decimal(measured["total_estimated_cost_usd"])
                - Decimal(audit["cost_estimate"]["estimated_max_cost_usd"]))
            if measured["total_estimated_cost_usd"] is not None else None}
        try:
            if raw.get("model") != self.settings.model:
                raise ResponseValidationError("RESPONSE_MODEL_MISMATCH", path=['model'])
            response = parse_response(raw, {p["evidence"]["unit_id"] for p in package["parents"]})
        except (ValueError, TypeError, KeyError) as error:
            return GenerationResult(audit | {"status": "INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE",
                "blocking_reasons": ["RESPONSE_STRUCTURE_OR_IDENTITY_INVALID"],
                'response_diagnostics': getattr(error, 'diagnostics',
                    [{'code': 'PROVIDER_RESPONSE_ENVELOPE_INVALID', 'path': []}])})
        try:
            assessment = self.assess_response(response, package, result)
        except (ValueError, TypeError, KeyError, OSError):
            return GenerationResult(audit | {"status": "BLOCKED_INTEGRITY",
                "blocking_reasons": ["POST_RESPONSE_M8_VALIDATION_FAILED"]})
        state = assessment["status"]
        status = ("GENERATED_QUALIFICATIONS_VALID" if state == VALID else
                  "GENERATED_QUALIFICATIONS_MISSING" if state == MISSING else
                  "GENERATED_QUALIFICATION_REVIEW_REQUIRED")
        audit.update(status=status, qualification_validation=assessment, answer_status=response["status"],
                     abstention_explanation=check_explanation(response),
                     blocking_reasons=[] if state == VALID else [state])
        return GenerationResult(audit, response)


def main(argv=None):
    """Current experimental CLI; default is local dry run, with no .env loading."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--provider-preflight", action="store_true")
    parser.add_argument("--allow-source-transfer", action="store_true")
    parser.add_argument("--allow-paid-inference", action="store_true")
    args = parser.parse_args(argv)
    if args.live and args.dry_run:
        parser.error("choose dry-run or live")
    if args.live and not (args.allow_paid_inference and args.allow_source_transfer):
        parser.error("live requires separate owner authorization and both explicit opt-ins")
    try:
        from tools.evidence.service import EvidenceService
        from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA

        settings = load_settings(args.settings, model=args.model)
        resolve(settings)
        root = Path(__file__).resolve().parents[2]
        question = json.loads((root / "data/evals/ranking/phase2-v1/QUESTIONS_ONLY.json").read_bytes())["questions"]["M9-Q05"]
        result = json.loads((root / "data/evals/pre-generation-gate/experiment-v1/candidates/M9-Q05.json").read_bytes())
        seal = json.loads((root / "data/evals/prompt-assembly/experiment-v1/audits/M9-Q05.json").read_bytes())
        if (digest(result) != seal["M7_result_sha256"] or result["parameters"] !=
                {"top_k": 30, "candidate_depth": 50, "rrf_k": 60, "filters": {}}):
            raise ValueError("SEALED_CANDIDATE_BINDING_CHANGED")
        evidence = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
        package = evidence.assemble(result, token_budget=128000)
        if digest(package) != seal["M8_package_sha256"]:
            raise ValueError("SEALED_M8_BINDING_CHANGED")
        gate = PromptAssemblyGate(evidence)
        prepared = gate.prepare(question, package, result)
        service = GenerationService(gate, settings=settings)
        if args.live:
            value = service.generate(prepared, question, package, result,
                allow_paid_inference=args.allow_paid_inference, allow_source_transfer=args.allow_source_transfer)
        else:
            value = service.dry_run(prepared, question, package, result,
                allow_provider_preflight=args.provider_preflight, allow_source_transfer=args.allow_source_transfer)
        print(json.dumps(value.audit, indent=2, sort_keys=True))
        return 0 if value.audit["status"] in {"READY", "GENERATED_QUALIFICATIONS_VALID"} else 2
    except (ValueError, TypeError, KeyError, OSError, ImportError, RuntimeError, AttributeError) as error:
        print(json.dumps({"status": "BLOCKED_CONFIGURATION_OR_INTEGRITY",
            "blocking_reasons": ["CONFIGURATION_RUNTIME_OR_PRIVATE_BINDING_FAILED"],
            "error_type": type(error).__name__, "generation_executed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
