"""Experimental stage reporting; no production policy/readiness implementation."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from rag_hub.schemas import SourceManifest
from rag_hub.validation_models import EvidenceModel

STAGES = (
    "acquisition",
    "parsing",
    "normalization",
    "quality_assurance",
    "ingestion_readiness_gate",
)


class Issue(EvidenceModel):
    issue_id: str
    code: str
    severity: Literal["warning", "error"]
    dimension: Literal["source_accounting", "source_fidelity", "structure", "execution"]
    detail: str
    evidence: dict
    artifact_refs: tuple[str, ...]


class Check(EvidenceModel):
    name: str
    dimension: Literal["source_accounting", "source_fidelity", "structure", "execution"]
    outcome: Literal["pass", "fail", "pending"]
    required: bool = True
    evidence: tuple[str, ...] = ()


class StageResult(EvidenceModel):
    source_id: str
    stage: Literal[
        "acquisition", "parsing", "normalization", "quality_assurance", "ingestion_readiness_gate"
    ]
    attempt_id: str
    publisher: str
    publisher_version: str
    status: Literal["success", "failure", "partial", "blocked", "not_executed"]
    source: SourceManifest | None = None
    components: tuple[str, ...]
    artifacts: dict[str, str]
    checks: tuple[Check, ...]
    issues: tuple[Issue, ...]
    provenance: tuple[str, ...]
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    note: str

    @model_validator(mode="after")
    def safe_outcome(self):
        if self.source and self.source.doc_id != self.source_id:
            raise ValueError("source identity disagreement")
        if self.status == "not_executed":
            if self.started_at or self.ended_at or self.checks:
                raise ValueError("not-executed stage cannot claim execution evidence")
        elif not self.started_at or not self.ended_at or self.ended_at < self.started_at:
            raise ValueError("executed stage requires ordered actual timestamps")
        if self.status == "success" and (
            not self.source
            or not self.components
            or not self.artifacts
            or not self.checks
            or not any(c.required for c in self.checks)
            or any(c.required and (c.outcome != "pass" or not c.evidence) for c in self.checks)
            or self.issues
        ):
            raise ValueError("success requires complete passing evidence without unresolved issues")
        if not self.source and self.status != "not_executed" and not self.issues:
            raise ValueError("missing source identity must be visible as an issue")
        return self


class Execution(EvidenceModel):
    contract_version: Literal["stage-result-experimental-1.0"] = "stage-result-experimental-1.0"
    workstream: Literal["pdf-remediation"] = "pdf-remediation"
    checkpoint: Literal["phase1a"] = "phase1a"
    attempt_id: str
    started_at: AwareDatetime
    ended_at: AwareDatetime
    run_id: str | None
    program_status: Literal["completed", "failed"]
    fingerprints: dict[str, str]
    stages: tuple[StageResult, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def unique_authorities(self):
        if self.ended_at < self.started_at:
            raise ValueError("invalid execution interval")
        pairs = [(s.source_id, s.stage) for s in self.stages]
        if len(pairs) != len(set(pairs)) or any(
            s.attempt_id != self.attempt_id for s in self.stages
        ):
            raise ValueError("duplicate stage authority or wrong execution attempt")
        for source in {s.source_id for s in self.stages}:
            rows = [s for s in self.stages if s.source_id == source]
            if tuple(s.stage for s in rows) != STAGES:
                raise ValueError("missing or unordered source stage records")
            for i, row in enumerate(rows):
                if row.status == "success" and any(p.status != "success" for p in rows[:i]):
                    raise ValueError("successful stage requires successful upstream evidence")
            # This bounded checkpoint cannot execute the gate or other stages.
            if any(s.status != "not_executed" for s in rows if s.stage != "quality_assurance"):
                raise ValueError("Phase1A executes only an isolated QA checkpoint")
        return self
