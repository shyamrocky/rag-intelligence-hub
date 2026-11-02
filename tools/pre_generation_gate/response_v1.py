"""Versioned response SHAPE contract. No generation or post-generation grounding check."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "grounded-response-1.0"


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Quote(Shape):
    evidence_unit_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class Claim(Shape):
    claim_text: str = Field(min_length=1)
    evidence_unit_ids: list[str] = Field(min_length=1)
    supporting_quotes: list[Quote] = Field(min_length=1)

    @model_validator(mode="after")
    def references_consistent(self):
        ids = self.evidence_unit_ids
        if (any(not x.strip() for x in ids) or len(ids) != len(set(ids))
                or {q.evidence_unit_id for q in self.supporting_quotes} != set(ids)
                or not self.claim_text.strip() or any(not q.quote.strip() for q in self.supporting_quotes)):
            raise ValueError("claim_quote_reference_shape_inconsistent")
        return self


class GroundedResponse(Shape):
    status: Literal["ANSWERED", "PARTIAL", "ABSTAINED"]
    answer: str
    claims: list[Claim]
    missing_information: list[str]
    relevant_qualifications: list[str]

    @model_validator(mode="after")
    def status_consistent(self):
        if any(not x.strip() for x in self.missing_information + self.relevant_qualifications):
            raise ValueError("blank_response_metadata")
        if self.status == "ABSTAINED":
            if self.answer or self.claims or not self.missing_information:
                raise ValueError("abstention_requires_empty_answer_claims_and_missing_reason")
        elif not self.answer.strip() or not self.claims:
            raise ValueError("answer_requires_text_and_claims")
        if self.status == "PARTIAL" and not self.missing_information:
            raise ValueError("partial_requires_missing_information")
        if self.status == "ANSWERED" and self.missing_information:
            raise ValueError("complete_status_conflicts_with_missing_information")
        return self


def response_schema():
    """Provider-neutral JSON Schema. Provider structured-output support is unverified."""
    value = GroundedResponse.model_json_schema()
    value["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    value["$id"] = "urn:rag-hub:" + SCHEMA_VERSION
    value["description"] = (
        "Shape contract only. Python validators additionally enforce status/claim/reference "
        "relationships. Source entailment, quotation fidelity and answer quality are future checks.")
    return value


def validate_response_shape(value):
    """Owned fixture/schema validation only; does not establish factual or quote support."""
    return GroundedResponse.model_validate(value)
