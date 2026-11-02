"""Typed, versioned quality evidence separate from immutable ingestion records."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Hash = str


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ValidationPolicy(EvidenceModel):
    version: Literal["quality-1.0"] = "quality-1.0"
    input_run_id: str
    artifact_sha256: dict[str, str]
    expected_hold_count: int = Field(default=1665, ge=0)
    expected_original_approvals: int = Field(default=9, ge=0)
    seed: str = "rag-hub-quality-2026-10-19"
    sample_targets: dict[str, int] = {"low": 45, "medium:C01": 30, "medium:C06": 30, "high": 20}
    automatic_documents: tuple[str, ...] = ("C04",)
    automatic_formats: tuple[str, ...] = ("markdown_mdx",)
    min_eligible_reviews_per_cohort: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def safe_policy(self):
        if set(self.sample_targets) != {"low", "medium:C01", "medium:C06", "high"}:
            raise ValueError("unknown/missing sampling group")
        if any(v < 1 for v in self.sample_targets.values()):
            raise ValueError("sampling targets must be positive")
        if self.automatic_documents != ("C04",) or self.automatic_formats != ("markdown_mdx",):
            raise ValueError("this milestone permits automatic promotion only for C04 Markdown")
        return self


class ValidationResult(EvidenceModel):
    section_id: str
    doc_id: str
    raw_sha256: str
    normalized_sha256: str
    risk: Literal["low", "medium", "high"]
    cohort: str
    checks: dict[str, Literal["pass", "fail", "manual_required"]]
    reasons: tuple[str, ...]
    eligible_automatic: bool
    blocking_integrity: bool = False
    coverage_tags: tuple[str, ...]


class SamplePlan(EvidenceModel):
    validator_sha256: str
    policy_sha256: str
    seed: str
    role: Literal["acceptance", "calibration"] = "acceptance"
    excluded_ids: tuple[str, ...] = ()
    initial_ids: tuple[str, ...]
    selected_ids: tuple[str, ...]
    expansion: dict[str, tuple[str, ...]]
    coverage_required: tuple[str, ...]
    coverage_missing: tuple[str, ...]


class QualityReview(EvidenceModel):
    section_id: str
    normalized_sha256: str
    raw_sha256: str
    policy_sha256: str
    sample_sha256: str
    role: Literal["acceptance", "calibration"]
    reviewer: str = Field(min_length=1)
    method: Literal["source_comparison", "visual_source_comparison"]
    evidence_note: str = Field(min_length=1)
    verdict: Literal["pass", "confirmed_hold", "defect"]
    manual_approval: bool = False

    @model_validator(mode="after")
    def no_implicit_approval(self):
        if self.manual_approval and self.verdict != "pass":
            raise ValueError("manual approval requires passing review")
        return self


class QualityDecision(EvidenceModel):
    section_id: str
    doc_id: str
    risk: Literal["low", "medium", "high"]
    status: Literal["hold", "approved_for_index"]
    basis: Literal[
        "hold", "deterministic_source_match", "visual_manual_review", "original_manual_receipt"
    ]
    raw_sha256: str
    normalized_sha256: str
    policy_sha256: str
    validation_sha256: str
    receipt_sha256: str | None = None
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def approval_has_evidence(self):
        if self.status == "approved_for_index" and (
            self.basis == "hold" or not self.receipt_sha256
        ):
            raise ValueError("approved decision requires evidence")
        if self.basis == "deterministic_source_match" and self.risk != "low":
            raise ValueError("medium/high content cannot automatically promote")
        return self


class ScopedPdfDecision(QualityDecision):
    """Explicit parent-only approval; legacy consumers reject this new contract."""

    schema_version: Literal["pdf-scoped-decision-1.0"] = "pdf-scoped-decision-1.0"
    basis: Literal["scoped_pdf_owner_review"] = "scoped_pdf_owner_review"
    scope: dict
    reviewed_reason_dispositions: dict[str, str]

    @model_validator(mode="after")
    def restrict_scope(self):
        if (
            self.status != "approved_for_index"
            or self.risk != "medium"
            or self.reasons
            or self.scope.get("whole_parent_required") is not True
            or self.section_id not in self.scope.get("required_section_ids", ())
            or not self.scope.get("parent_id")
            or not self.scope.get("parent_sha256")
            or not self.scope.get("context_sha256")
            or not self.scope.get("policy_scope_sha256")
            or not self.scope.get("owner_policy_authorization_sha256")
            or not self.scope.get("qa_release_sha256")
            or not self.scope.get("candidate_id")
            or not self.scope.get("retrieval_context_projection")
            or self.doc_id not in {"C01", "C02", "C06", "C14"}
            or len(set(self.scope.get("required_section_ids", ())))
            != len(self.scope.get("required_section_ids", ()))
        ):
            raise ValueError("invalid_scoped_PDF_decision")
        return self
