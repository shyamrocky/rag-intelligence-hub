"""External model selection and documented capability profiles; no automatic fallback."""

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).parent


class ProfileError(ValueError):
    """Application-owned configuration code, safe for source-free diagnostics."""


class GenerationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: str = Field(default="generation-settings-1.0", alias="schema")
    provider: str = "openai"
    model: str = "gpt-6-luna"
    prompt_version: str = "grounded-generation-prompt-v2"
    response_schema: str = "grounded-response-2.0"
    reasoning_effort: str = "none"
    max_output_tokens: int = Field(default=4096, gt=0)
    safety_margin_tokens: int = Field(default=1024, ge=0)
    temperature: float | None = None
    timeout_seconds: int = Field(default=120, gt=0, le=600)
    service_tier: str = "default"
    region: str = "global"
    cache_ttl: str = "30m"


def load_settings(path=None, *, model=None):
    values = json.loads(Path(path or HERE / "settings-v1.json").read_bytes())
    if model is not None:
        values["model"] = model
    return GenerationSettings.model_validate(values)


def resolve(settings, registry=None, *, as_of=None):
    settings = GenerationSettings.model_validate(settings.model_dump(by_alias=True))
    registry = registry or json.loads((HERE / "model-profiles-v1.json").read_bytes())
    today = as_of or date.today()
    if (
        settings.provider != "openai"
        or settings.schema_version != "generation-settings-1.0"
        or settings.prompt_version != "grounded-generation-prompt-v2"
        or settings.response_schema != "grounded-response-2.0"
    ):
        raise ProfileError("UNSUPPORTED_PROVIDER_OR_PROMPT_CONTRACT")
    p = registry["profiles"].get(settings.model)
    if registry.get("schema") != "openai-model-profiles-1.0" or not registry.get("version"):
        raise ProfileError("INVALID_MODEL_PROFILE_REGISTRY")
    if not p or p["model"] != settings.model:
        raise ProfileError("UNSUPPORTED_MODEL_NO_FALLBACK")
    for key in ["context_window", "maximum_input_tokens", "maximum_output_tokens"]:
        if type(p[key]) is not int or p[key] <= 0:
            raise ProfileError("INVALID_MODEL_CAPACITY")
    if not date.fromisoformat(p["reviewed_on"]) <= today <= date.fromisoformat(p["review_by"]):
        raise ProfileError("MODEL_PROFILE_REVIEW_STALE")
    if (
        not p["structured_outputs_documented"]
        or p["count_method"] != "responses.input_tokens.count"
    ):
        raise ProfileError("MODEL_CAPABILITY_UNQUALIFIED")
    if settings.reasoning_effort not in p["reasoning_efforts"] or (
        settings.temperature is not None and not p["temperature_supported"]
    ):
        raise ProfileError("UNSUPPORTED_OR_UNVERIFIED_MODEL_PARAMETER")
    if settings.max_output_tokens > p["maximum_output_tokens"]:
        raise ProfileError("OUTPUT_RESERVATION_EXCEEDS_MODEL_LIMIT")
    if settings.service_tier not in {"default", "flex", "fast", "priority"}:
        raise ProfileError("UNSUPPORTED_SERVICE_TIER")
    # This adapter targets only the ordinary global API endpoint. Regional pricing
    # remains calculable in the telemetry engine, but is not a deployment selector.
    if settings.region != "global" or settings.cache_ttl not in {"30m", "12h"}:
        raise ProfileError("UNSUPPORTED_ENDPOINT_REGION_OR_CACHE_TTL")
    return dict(p)


def check_fit(profile, settings, input_tokens):
    if type(input_tokens) is not int or input_tokens < 0:
        raise ProfileError("UNVERIFIED_INPUT_TOKEN_COUNT")
    margin = (
        profile["context_window"]
        - input_tokens
        - settings.max_output_tokens
        - settings.safety_margin_tokens
    )
    return {
        "fits": input_tokens <= profile["maximum_input_tokens"] and margin >= 0,
        "input_tokens": input_tokens,
        "reserved_output_tokens": settings.max_output_tokens,
        "safety_margin_tokens": settings.safety_margin_tokens,
        "remaining_context_margin": margin,
        "context_window": profile["context_window"],
        "maximum_input_tokens": profile["maximum_input_tokens"],
    }
