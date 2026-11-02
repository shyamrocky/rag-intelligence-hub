"""Explicit external assessments, never model self-declarations or label heuristics.

Human identity/competence is an application review responsibility, not established
by a JSON field. A caller must independently trust the artifact hash and reviewer.
A model judge remains provisional. This module cannot invoke a model or issue consent.
"""
import hashlib
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from tools.quality_dashboard.artifacts import ArtifactError, digest, read_json, safe_path, sha


class Shape(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Passage(Shape):
    unit_id: str
    pointer: str
    field_sha256: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class ClaimAssessment(Shape):
    claim_index: int = Field(ge=0)
    claim_sha256: str
    outcome: Literal['SUPPORTED', 'PARTIALLY_SUPPORTED', 'CONTRADICTED', 'UNSUPPORTED', 'INDETERMINATE']
    rationale: str = Field(min_length=1)
    passages: list[Passage]
    quotation_coverage_gap: str | None = None


class RequirementAssessment(Shape):
    requirement_id: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    outcome: Literal['COMPLETE', 'PARTIAL', 'INCOMPLETE', 'INDETERMINATE']
    rationale: str = Field(min_length=1)
    claim_indices: list[int]
    passages: list[Passage]


class DisclosureAssessment(Shape):
    outcome: Literal['SATISFIED', 'MISSING', 'INDETERMINATE']
    rationale: str = Field(min_length=1)
    passages: list[Passage]


class Assessment(Shape):
    schema_version: Literal['answer-quality-assessment-2.0']
    method: Literal['HUMAN_REVIEW', 'LLM_JUDGE', 'OFFLINE_FIXTURE', 'ASSISTANT_ANALYSIS']
    reviewer: str = Field(min_length=1)
    assessed_at: str = Field(min_length=1)
    question_sha256: str
    response_sha256: str
    package_sha256: str
    request_sha256: str
    independent_of_generator: bool
    answer_claim_inventory_complete: bool
    question_requirements_reviewed: bool
    uncertainty: list[str]
    response_status_appropriate: bool | None
    claims: list[ClaimAssessment]
    requirements: list[RequirementAssessment]
    qualifications: DisclosureAssessment
    conflicts: DisclosureAssessment


class SemanticAssessor(Protocol):
    def assess(self, *, question, response, package, request_sha256) -> Assessment:
        """Read-only evidence-aware assessor; model calls need separate authorization."""
        ...


class HumanReview:
    """Import an independently trusted offline assessment. Not an approval issuer."""
    def __init__(self, root, path, expected_sha256, *, approved_reviewers):
        file = safe_path(root, path)
        if sha(file) != expected_sha256:
            raise ArtifactError('REVIEW_ARTIFACT_HASH_MISMATCH')
        self.provenance = {'path': path, 'sha256': expected_sha256,
                           'authority': 'EXTERNALLY_CONFIGURED_REVIEWER_AND_HASH_NOT_MODEL_DECLARATION'}
        self.value = Assessment.model_validate(read_json(file))
        if (self.value.method != 'HUMAN_REVIEW' or self.value.reviewer not in approved_reviewers
                or not self.value.independent_of_generator):
            raise ArtifactError('UNQUALIFIED_HUMAN_REVIEW')

    def assess(self, **context):
        return self.value.model_copy(deep=True)


def bound_assessment(value, *, question, response, package, request_sha256, fields):
    value = Assessment.model_validate(value)
    if (value.question_sha256 != hashlib.sha256(question.encode()).hexdigest()
            or value.response_sha256 != digest(response) or value.package_sha256 != digest(package)
            or value.request_sha256 != request_sha256):
        raise ArtifactError('SEMANTIC_ASSESSMENT_BINDING_MISMATCH')
    if sorted(c.claim_index for c in value.claims) != list(range(len(response['claims']))):
        raise ArtifactError('INCOMPLETE_OR_DUPLICATE_CLAIM_REVIEW')
    if not value.requirements or len({r.requirement_id for r in value.requirements}) != len(value.requirements):
        raise ArtifactError('INCOMPLETE_OR_DUPLICATE_REQUIREMENT_REVIEW')
    for c in value.claims:
        claim = response['claims'][c.claim_index]
        if c.claim_sha256 != digest(claim):
            raise ArtifactError('CLAIM_BINDING_MISMATCH')
        if c.outcome in {'SUPPORTED', 'PARTIALLY_SUPPORTED', 'CONTRADICTED'} and not c.passages:
            raise ArtifactError('EVIDENCE_AWARE_ASSESSMENT_REQUIRED')
        if any(p.unit_id not in claim['evidence_unit_ids'] for p in c.passages):
            raise ArtifactError('ASSESSMENT_SUBSTITUTED_CLAIM_SOURCE')
    for r in value.requirements:
        if any(type(i) is not int or not 0 <= i < len(response['claims']) for i in r.claim_indices):
            raise ArtifactError('INVALID_REQUIREMENT_CLAIM_REFERENCE')
    for item in [*value.claims, *value.requirements, value.qualifications, value.conflicts]:
        for p in item.passages:
            text = fields.get((p.unit_id, p.pointer))
            if (text is None or hashlib.sha256(text.encode()).hexdigest() != p.field_sha256
                    or not 0 <= p.start < p.end <= len(text)):
                raise ArtifactError('SEMANTIC_PASSAGE_BINDING_MISMATCH')
    return value
