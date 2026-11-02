"""Reuse the immutable stage/check/issue models and original span validator."""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from rag_hub.schemas import SourceManifest

from .contracts import ExtendedSource

ROOT = Path(__file__).resolve().parents[3]


from . import guard as GUARD  # noqa: F401 -- public shared guard binding
from . import stage_contract as LEGACY

Check, Issue, STAGES = LEGACY.Check, LEGACY.Issue, LEGACY.STAGES


class StageResult(LEGACY.StageResult):
    source: ExtendedSource | SourceManifest | None = None


class Execution(LEGACY.Execution):
    contract_version: Literal["stage-result-experimental-2.0"] = "stage-result-experimental-2.0"
    workstream: Literal["ext01"] = "ext01"
    checkpoint: Literal["foundation-extensibility"] = "foundation-extensibility"
    stages: tuple[StageResult, ...]
    diagnostics: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_authorities(self):
        if self.ended_at < self.started_at:
            raise ValueError("invalid execution interval")
        pairs = [(r.source_id, r.stage) for r in self.stages]
        if len(set(pairs)) != len(pairs) or any(
            r.attempt_id != self.attempt_id for r in self.stages
        ):
            raise ValueError("duplicate authority or foreign attempt")
        for source in {r.source_id for r in self.stages}:
            rows = [r for r in self.stages if r.source_id == source]
            if tuple(r.stage for r in rows) != STAGES:
                raise ValueError("missing or unordered stage")
            for index, row in enumerate(rows):
                if row.status == "success" and any(p.status != "success" for p in rows[:index]):
                    raise ValueError("success cannot hide unresolved upstream evidence")
        return self
