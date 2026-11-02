"""Small read-only projections of accepted format contracts, never QA decisions."""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, TypedDict

Format = Literal["html", "markdown", "pdf"]
Status = Literal["ADMITTED", "EXCLUDED", "HOLD"]


class DocumentRecord(TypedDict):
    document_id: str
    format: Format
    source: dict
    snapshot: dict
    counts: dict[str, int]
    unit_ids: list[str]
    publication_identity: dict
    selector_path: str


class SectionRecord(TypedDict):
    section_id: str
    document_id: str
    format: Format
    admission_status: Status
    native_disposition: str
    reference_classification: str | None
    native_reference_classification: str | None
    citation_locators: list[dict]
    provenance: dict
    issue_ids: list[str]
    issues: list[dict]
    reason: str | None
    evidence_refs: list[dict]
    scope_limited_projection: bool
    memberships: list[dict]
    unit_ids: list[str]
    context_only: bool
    publication_identity: dict
    raw_section_is_independent_consumption_unit: bool
    authority: str


def plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"unsupported consumer value: {type(value).__name__}")


def encode(value):
    return json.dumps(
        value, default=plain, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Membership:
    section_id: str
    role: str
    native_role: str


@dataclass(frozen=True)
class AdaptedUnit:
    native_id: str
    document_id: str
    format: Format
    classification: str
    native_classification: str | None
    memberships: tuple[Membership, ...]
    native_json: bytes
    consumer_json: bytes
    publication_json: bytes
    citations_json: bytes
    scope_limited: bool

    @property
    def unit_id(self):
        # Publication identity is part of the handle, preventing historical ID aliasing.
        return f"{self.format}:{sha(self.publication_json)}:{self.native_id}"

    def native_handle(self):
        value = json.loads(self.native_json)
        # Clock-derived expiration views are not immutable publication identity.
        if self.format == "pdf":
            value.pop("publication_expiration", None)
            if "qa_observations" in value:
                value["qa_observations"] = [o for o in value["qa_observations"]
                                            if o.get("issue_id") != "PDF_PUBLICATION_EXPIRED"]
            if "llm_context" in value:
                value["llm_context"]["qa_observations"] = [
                    o for o in value["llm_context"]["qa_observations"]
                    if o.get("issue_id") != "PDF_PUBLICATION_EXPIRED"]
        return sha(encode(value))

    def metadata(self):
        return {
            "unit_id": self.unit_id,
            "native_unit_id": self.native_id,
            "document_id": self.document_id,
            "format": self.format,
            "admission_status": "ADMITTED",
            "reference_classification": self.classification,
            "native_reference_classification": self.native_classification,
            "memberships": [vars(m) for m in self.memberships],
            "scope_limited_projection": self.scope_limited,
            "publication_identity": json.loads(self.publication_json),
            "citation_locators": json.loads(self.citations_json),
            "native_handle": self.native_handle(),
        }

    def evidence(self):
        return {
            **self.metadata(),
            "schema": "unified-verified-unit-1.0",
            "validation": "VERIFIED_NATIVE_PUBLICATION_BOUND_SNAPSHOT",
            "consumer": json.loads(self.consumer_json),
        }
