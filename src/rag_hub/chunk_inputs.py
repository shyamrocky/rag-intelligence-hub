"""M0 derived preparation contract. Records are never evidence authorizations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceContent(BaseModel):
    """An exact gateway source field, still bound to its whole verified unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source_pointer: str
    content_type: str
    text: str
    section_ids: list[str]
    source_spans: list[dict]
    native_source: dict
    consumption_scope: Literal["complete_verified_unit_only"] = "complete_verified_unit_only"


class ChunkInput(BaseModel):
    """Separate source, context, QA and lineage; no chunk or index is created."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["chunk-input-1.0"] = "chunk-input-1.0"
    authority: Literal["DERIVED_PREPARATION_NOT_AUTHORIZATION"] = (
        "DERIVED_PREPARATION_NOT_AUTHORIZATION"
    )
    record_id: str
    unit_id: str
    document_id: str
    format: Literal["pdf", "html", "markdown"]
    reference_classification: str
    indexable_source_content: list[SourceContent]
    required_context: list[dict]
    qa_observations: list[dict]
    qualification: dict
    protected_consumable_projections: list[dict]
    preparation_limits: list[str]
    memberships: list[dict]
    section_bindings: list[dict]
    citation_locators: list[dict]
    publication_identity: dict
    consumer_metadata: dict
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def json_schema():
    return ChunkInput.model_json_schema()
