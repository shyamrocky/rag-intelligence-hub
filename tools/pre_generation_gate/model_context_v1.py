"""External model configuration and strict context arithmetic; no selected generator."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelConfiguration(BaseModel):
    """Declared configuration is not proof of provider limits or owner authorization."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    tokenizer_id: str = Field(min_length=1)
    tokenizer_revision: str = Field(min_length=1)
    context_window: int = Field(gt=0)
    maximum_input_tokens: int = Field(gt=0)
    maximum_output_tokens: int = Field(gt=0)
    reserved_output_tokens: int = Field(gt=0)
    safety_margin_tokens: int = Field(ge=0)
    message_format: str = Field(min_length=1)
    structured_output_format: str = Field(min_length=1)

    @model_validator(mode="after")
    def nonblank_identifiers(self):
        names = (self.provider, self.model_id, self.revision, self.tokenizer_id,
                 self.tokenizer_revision, self.message_format, self.structured_output_format)
        if any(not s.strip() for s in names):
            raise ValueError("blank_model_identifier")
        return self


def check_context_limits(configuration, exact_input_tokens):
    """Pure numeric policy, NOT qualification of a model or the supplied token count.

    Only a separately verified exact generator request counter could make this
    arithmetic a real compatibility verdict. Test fixtures are labeled as such.
    Independent component counts must not replace the full framed-request total.
    """
    cfg = ModelConfiguration.model_validate(configuration)
    if type(exact_input_tokens) is not int or exact_input_tokens < 0:
        raise ValueError("input_tokens_must_be_nonnegative_integer")
    reasons = []
    if exact_input_tokens > cfg.maximum_input_tokens:
        reasons.append("PROVIDER_INPUT_LIMIT_EXCEEDED")
    if cfg.reserved_output_tokens > cfg.maximum_output_tokens:
        reasons.append("PROVIDER_OUTPUT_LIMIT_EXCEEDED")
    remaining = cfg.context_window - exact_input_tokens - cfg.reserved_output_tokens
    margin = remaining - cfg.safety_margin_tokens
    if margin < 0:
        reasons.append("CONTEXT_WINDOW_OUTPUT_RESERVE_OR_MARGIN_EXCEEDED")
    return {"numeric_fit": not reasons, "blocking_reasons": reasons,
            "input_tokens": exact_input_tokens, "reserved_output_tokens": cfg.reserved_output_tokens,
            "required_margin_tokens": cfg.safety_margin_tokens,
            "remaining_after_output_reserve": remaining, "available_context_margin": margin,
            "model_and_count_qualification": "NOT_ESTABLISHED_BY_ARITHMETIC"}


def generator_accounting(configuration):
    """Explicit capability result. No exact generator/counter is currently qualified.

    Never use BGE counts, byte lengths, caller `verified` flags or estimates for
    READY. Adding a model/request counter is a separately reviewed extension.
    """
    if configuration is None:
        return None, "NO_OWNER_AUTHORIZED_GENERATOR_CONFIGURATION"
    cfg = ModelConfiguration.model_validate(configuration)
    return cfg.model_dump(), "MODEL_TOKENIZER_FRAMING_AND_SCHEMA_ACCOUNTING_UNQUALIFIED"
