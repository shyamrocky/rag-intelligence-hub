"""Response shape and reference scope only; no entailment or quote-fidelity assessor."""

from typing import Literal

from pydantic import Field, model_validator

from tools.pre_generation_gate.response_v1 import GroundedResponse as ResponseV1
from tools.pre_generation_gate.response_v1 import Shape

SCHEMA_VERSION = "grounded-response-2.0"
EXAMPLE_ID = "EXAMPLE-UNIT-001"


def checked_ids(ids):
    if any(not x.strip() for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("blank_or_duplicate_reference")
    return ids


class RequirementCoverage(Shape):
    requirement: str = Field(min_length=1)
    status: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNCERTAIN"]
    evidence_unit_ids: list[str]

    @model_validator(mode="after")
    def consistent(self):
        checked_ids(self.evidence_unit_ids)
        if not self.requirement.strip():
            raise ValueError("blank_requirement")
        if self.status in {"SUPPORTED", "PARTIAL"} and not self.evidence_unit_ids:
            raise ValueError("asserted_support_requires_references")
        if self.status == "UNSUPPORTED" and self.evidence_unit_ids:
            raise ValueError("unsupported_requirement_cannot_assert_support")
        return self


class Conflict(Shape):
    description: str = Field(min_length=1)
    # A conflict can occur within one complete parent; do not invent a second unit.
    evidence_unit_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self):
        checked_ids(self.evidence_unit_ids)
        if not self.description.strip():
            raise ValueError("blank_conflict")
        return self


class GroundedResponse(ResponseV1):
    requirement_coverage: list[RequirementCoverage]
    conflicts_detected: list[Conflict]

    @model_validator(mode="after")
    def declarations_consistent(self):
        if self.status == "ANSWERED" and any(
            r.status != "SUPPORTED" for r in self.requirement_coverage
        ):
            raise ValueError("complete_answer_conflicts_with_coverage_declarations")
        # Conflicts are potential model-reported concerns. Conservatively require
        # bounded partial/abstention rather than an unqualified complete answer.
        if self.status == "ANSWERED" and self.conflicts_detected:
            raise ValueError("complete_answer_with_unresolved_reported_conflicts")
        if self.status == "ABSTAINED" and any(
            r.status in {"SUPPORTED", "PARTIAL"} for r in self.requirement_coverage
        ):
            raise ValueError("abstention_conflicts_with_asserted_usable_support")
        return self


def response_schema():
    value = GroundedResponse.model_json_schema()
    value["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    value["$id"] = "urn:rag-hub:" + SCHEMA_VERSION
    value["description"] = (
        "Structural contract only; coverage/conflicts are model declarations. Python "
        "validators additionally enforce relationships and explicit authorized-ID scope. "
        "No semantic entailment, quotation fidelity or provider compatibility is certified.")
    return value


def _validate_scoped(value, allowed_ids, *, example):
    """Explicit ID scope is mandatory; never derive it from a model response."""
    if type(allowed_ids) not in (set, frozenset, list, tuple):
        raise ValueError("explicit_authorized_unit_ids_required")
    if any(type(x) is not str or not x.strip() for x in allowed_ids):
        raise ValueError("invalid_authorized_unit_ids")
    allowed = set(allowed_ids)
    if not example and any(x.startswith("EXAMPLE-") for x in allowed):
        raise ValueError("example_scope_forbidden_in_live_request")
    result = GroundedResponse.model_validate(value)
    referenced = set()
    for c in result.claims:
        referenced.update(c.evidence_unit_ids)
        referenced.update(q.evidence_unit_id for q in c.supporting_quotes)
    for item in result.requirement_coverage + result.conflicts_detected:
        referenced.update(item.evidence_unit_ids)
    if not referenced <= allowed:
        raise ValueError("unauthorized_evidence_reference")
    if not example and any(x.startswith("EXAMPLE-") for x in referenced):
        raise ValueError("example_reference_forbidden_in_live_response")
    return result


def validate_response_shape(value, *, authorized_unit_ids):
    """Owned fixture structural/reference validation; not post-generation evaluation.

    Caller must obtain IDs from its currently live-validated M8 package. An ID
    allowlist is not itself a reusable source-authorization receipt.
    """
    return _validate_scoped(value, authorized_unit_ids, example=False)


def synthetic_example():
    text = "Atlas Search supports keyword search and semantic search."
    return {"status": "ANSWERED", "answer": text,
        "claims": [{"claim_text": text, "evidence_unit_ids": [EXAMPLE_ID],
            "supporting_quotes": [{"evidence_unit_id": EXAMPLE_ID, "quote": text}]}],
        "missing_information": [], "relevant_qualifications": [],
        "requirement_coverage": [{"requirement": "Two supported search methods",
            "status": "SUPPORTED", "evidence_unit_ids": [EXAMPLE_ID]}],
        "conflicts_detected": []}


def validate_synthetic_example():
    """Dedicated instructional fixture; not an alternate live validation mode."""
    return _validate_scoped(synthetic_example(), {EXAMPLE_ID}, example=True)
