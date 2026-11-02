"""Initial contracts, not a claim of full ingestion-spec implementation.

All records default to HOLD. Verification applies only to the recorded spans.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class Record(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceManifest(Record):
    schema_version: Literal["0.1"] = "0.1"
    doc_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    canonical_url: HttpUrl
    title: str
    publisher: str
    source_format: Literal["pdf", "markdown_mdx", "html"]
    source_version: str | None = None
    captured_at: AwareDatetime | None = None
    original_url: HttpUrl | None = None
    byte_size: int | None = Field(default=None, gt=0)
    language: str | None = None
    acquisition_basis: str | None = None
    snapshot_path: Path | None = None

    @field_validator("captured_at")
    @classmethod
    def utc_capture(cls, value):
        return value.astimezone(UTC) if value else None

    raw_path: Path
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights_status: Literal["review_pending", "local_use_approved", "redistribution_approved"]
    technical_status: Literal["acquired", "parsed", "normalized", "verified", "hold"] = "acquired"


class Locator(Record):
    url: HttpUrl
    page: int | None = Field(default=None, ge=1)
    anchor: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def valid_ranges(self):
        if self.line_end is not None and (
            self.line_start is None or self.line_end < self.line_start
        ):
            raise ValueError("invalid line range")
        if self.bbox and (
            self.page is None or self.bbox[2] < self.bbox[0] or self.bbox[3] < self.bbox[1]
        ):
            raise ValueError("invalid page bounding box")
        return self


class ParsedBlock(Record):
    block_id: str
    doc_id: str
    snapshot_id: str
    sequence: int = Field(ge=0)
    block_type: Literal[
        "heading", "prose", "code", "table", "equation", "figure_caption", "list", "metadata"
    ]
    content: str
    heading_path: tuple[str, ...] = ()
    locator: Locator
    language: str | None = None
    provider_tab: str | None = None
    issues: tuple[str, ...] = ()
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_status: Literal["unreviewed", "hold"] = "unreviewed"
    fence_info: str | None = None
    code_group: str | None = None
    parser_version: str

    @model_validator(mode="after")
    def content_integrity(self):
        if hashlib.sha256(self.content.encode()).hexdigest() != self.content_sha256:
            raise ValueError("block content hash mismatch")
        return self


class Section(Record):
    section_id: str
    doc_id: str
    snapshot_id: str
    heading_path: tuple[str, ...]
    block_ids: tuple[str, ...]
    text: str
    locators: tuple[Locator, ...] = Field(min_length=1)
    verification_status: Literal[
        "unreviewed", "verified_sample", "verified_full", "hold", "rejected"
    ] = "unreviewed"
    index_status: Literal["hold", "approved_for_index"] = "hold"
    normalized_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    raw_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_tab: str | None = None
    code_group: str | None = None
    code_label: str | None = None
    block_type: str | None = None
    review_receipt: str | None = None
    transformations: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()

    @model_validator(mode="after")
    def approval_requires_review(self):
        if (
            self.normalized_sha256
            and hashlib.sha256(self.text.encode()).hexdigest() != self.normalized_sha256
        ):
            raise ValueError("normalized text hash mismatch")
        if self.index_status == "approved_for_index" and (
            self.verification_status not in ("verified_sample", "verified_full")
            or not self.review_receipt
            or not self.normalized_sha256
            or not self.raw_sha256
        ):
            raise ValueError("approval requires hash-bound review receipt")
        return self


class ReviewReceipt(Record):
    section_id: str
    normalized_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str = Field(min_length=1)
    evidence_note: str = Field(min_length=1)


class HazardSidecar(Record):
    sidecar_id: str
    section_id: str
    doc_id: str
    snapshot_id: str
    kind: Literal["table", "equation", "mixed_pdf", "figure"]
    source_locator: Locator
    original_visual_locator: str
    verification_status: Literal["hold"] = "hold"
    verified_latex_or_null: str | None = None
    column_names: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    embedding_model: str | None = None
    retrieval_k: int | None = None
    dataset: str | None = None
    units: str | None = None
    context_block_ids: tuple[str, ...] = ()
    context_locators: tuple[Locator, ...] = ()
    issues: tuple[str, ...]


class SourceSpan(Record):
    section_id: str
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)


class Chunk(Record):
    chunk_id: str
    doc_id: str
    snapshot_id: str
    strategy: Literal["fixed", "structure_aware"]
    strategy_version: str
    text: str = Field(min_length=1)
    source_spans: tuple[SourceSpan, ...] = Field(min_length=1)
    index_status: Literal["hold", "approved_for_index"] = "hold"


class Evidence(Record):
    chunk: Chunk
    score: float
    locators: tuple[Locator, ...] = Field(min_length=1)


class Answer(Record):
    text: str
    abstained: bool
    cited_chunk_ids: tuple[str, ...] = ()


class EvaluationCase(Record):
    question_id: str
    question: str
    split: Literal["DEV", "HELD"]
    answerability: Literal["answerable", "insufficient"]
    gold_spans: tuple[SourceSpan, ...] = ()
    label_status: Literal["pending_review", "approved"] = "pending_review"


class EvaluationReport(Record):
    run_id: str
    measured_at: datetime
    metrics: dict[str, float | None]
    sample_size: int = Field(ge=0)
    limitations: tuple[str, ...]
