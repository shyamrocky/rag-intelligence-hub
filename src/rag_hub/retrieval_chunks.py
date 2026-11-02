"""M3 derived chunk contracts. A catalog entry is never evidence authorization."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rag_hub.unified_models import encode, sha

SCHEMA = "retrieval-chunk-1.0"


class SourceSlice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pointer: str
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: str


class RetrievalChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["retrieval-chunk-1.0"] = SCHEMA
    authority: Literal["DERIVED_CATALOG_NOT_AUTHORIZATION"] = "DERIVED_CATALOG_NOT_AUTHORIZATION"
    chunk_id: str
    configuration_id: str
    unit_id: str
    document_id: str
    format: Literal["pdf", "html", "markdown"]
    source: SourceSlice
    parent_binding: dict
    mandatory_evidence_refs: dict
    lineage: dict
    reference_classification: str
    heading_context_sha256: str
    token_count: int = Field(gt=0)
    body_token_count: int = Field(ge=0)
    boundary_decision: str
    reference_numbers: list[int]
    unknown_token_offsets: list[dict]
    review_notes: list[str]


def chunk_id(payload):
    """Version, publication-qualified parent, config and exact source interval bind identity."""
    return f"rc:{SCHEMA}:" + sha(encode({k: v for k, v in payload.items() if k != "chunk_id"}))


def from_proposal(proposal, parent_metadata, configuration_id):
    p = proposal
    payload = {
        "schema_version": SCHEMA, "authority": "DERIVED_CATALOG_NOT_AUTHORIZATION",
        "configuration_id": configuration_id, "unit_id": p["unit_id"],
        "document_id": p["document_id"], "format": parent_metadata["format"],
        "source": {"pointer": p["source_pointer"],
                   "projection_sha256": p["source_projection_sha256"],
                   "start": p["display_start"], "end": p["display_end"],
                   "text_sha256": p["source_text_sha256"], "content_type": p["content_type"]},
        "parent_binding": {
            "native_handle": parent_metadata["native_handle"],
            "publication_sha256": sha(encode(parent_metadata["publication_identity"])),
            "memberships_sha256": sha(encode(parent_metadata["memberships"]))},
        "mandatory_evidence_refs": {k: "/consumer/llm_context/" + k for k in (
            "required_context", "qualification", "qa_observations")}
        | {"citations": "/citation_locators", "publication": "/publication_identity",
           "consumer_metadata": "/consumer", "scope": "complete_verified_unit_only"},
        "lineage": p["lineage"], "reference_classification": p["reference_classification"],
        "heading_context_sha256": sha(encode(p["heading_context"])),
        "token_count": p["token_count"], "body_token_count": p["body_token_count"],
        "boundary_decision": p["boundary_decision"], "reference_numbers": p["reference_numbers"],
        "unknown_token_offsets": p["unknown_token_offsets"], "review_notes": p["review_notes"],
    }
    return RetrievalChunk(chunk_id=chunk_id(payload), **payload)
