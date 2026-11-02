"""Source-bound PDF review evidence for the optional authoritative QA successor.

An exported file is an operator attestation, not proof of identity. Explicit owner
submission and separate QA-policy authorization remain required outside this module.
"""

import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from rag_hub.acquire import digest, local_path
from rag_hub.pdf_corpus import approved_parents, encoded, load_corpus
from rag_hub.validation_models import EvidenceModel

PACKET_ID = "pdf-prose-owner-review-1.0"
FACETS = (
    "source_text_fidelity",
    "paragraph_extent",
    "reading_order",
    "heading_document_context",
    "context_sufficiency",
    "excluded_dependencies_absent",
    "citation_traceability",
    "furniture_absent",
    "question_support",
)

RELEASE_VERSION = "pdf-scoped-qa-1.0"
RELEASE_COMPONENTS = (
    "src/rag_hub/shared/qa.py",
    "src/rag_hub/validation_models.py",
    "src/rag_hub/validation_reviews.py",
    "src/rag_hub/pdf_prose_review.py",
    "src/rag_hub/pdf_prose_handoff.py",
    "src/rag_hub/pdf_prose_execution.py",
    "src/rag_hub/pdf_corpus.py",
    "src/rag_hub/content_validation.py",
    "src/rag_hub/source_fidelity.py",
    "src/rag_hub/validation_sampling.py",
    "src/rag_hub/validation_pipeline.py",
    "src/rag_hub/acquire.py",
    "src/rag_hub/schemas.py",
    "src/rag_hub/pdf_classification.py",
    "src/rag_hub/pdf_nontext.py",
    "src/rag_hub/shared/contracts.py",
    "src/rag_hub/shared/structure.py",
    "src/rag_hub/shared/guard.py",
    "src/rag_hub/shared/registry.py",
    "src/rag_hub/shared/evidence.py",
    "src/rag_hub/shared/stage_contract.py",
    "src/rag_hub/shared/builtins.py",
    "uv.lock",
)
COMBINED_RELEASE_VERSION = "combined-scoped-qa-1.0"
COMBINED_RELEASE_COMPONENTS = RELEASE_COMPONENTS + (
    "src/rag_hub/html_validation.py",
    "src/rag_hub/html_reviews.py",
    "src/rag_hub/html_corpus.py",
    "src/rag_hub/html_acquire.py",
    "src/rag_hub/parse_html.py",
    "config/html-sources.json",
)
SAFEGUARDS = {
    "C02": "Introduction from C02:b00009[0:15]; exclude detached L and historical title ancestry",
    "C14": "Introduction from C14:b00006 page 1; exclude inherited arXiv-stamp heading path",
    "C06": "Attribute benchmark limitations to the frozen Chroma report; no universal-fact claim",
    "consumption": "complete_parent_bundle_only",
    "exclusions": "No mathematics, tables, code, figures or neighboring Sections admitted",
}


class ConsolidatedCase(EvidenceModel):
    candidate_id: str
    binding: dict


class ConsolidatedSubmission(EvidenceModel):
    """One explicit cohort attestation; never manufactures individual facet votes."""

    schema_version: Literal["pdf-prose-consolidated-owner-submission-1.0"]
    packet_id: Literal["pdf-prose-owner-review-1.0"]
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["PENDING", "APPROVE_SCOPED", "REJECT"]
    reviewer: str
    submitted_at: datetime | None
    cases: tuple[ConsolidatedCase, ...]
    safeguards: dict[str, str]
    basis: Literal["existing_technical_evidence_and_reported_independent_recommendations"]
    notes: str = ""
    corrections: str = ""
    actual_review_seconds: float | None = Field(
        default=None, ge=0, allow_inf_nan=False, strict=True
    )

    @model_validator(mode="after")
    def explicit(self):
        if self.safeguards != SAFEGUARDS:
            raise ValueError("mandatory_safeguards_missing_or_changed")
        if len(self.cases) != 8 or len({c.candidate_id for c in self.cases}) != 8:
            raise ValueError("consolidated_record_requires_exact_eight_cases")
        if self.submitted_at and self.submitted_at.tzinfo is None:
            raise ValueError("submission_requires_timezone")
        if self.decision != "PENDING" and (not self.reviewer.strip() or not self.submitted_at):
            raise ValueError("explicit_owner_identity_and_time_required")
        if self.decision == "APPROVE_SCOPED" and self.corrections.strip():
            raise ValueError("unresolved_corrections_block_approval")
        return self


def _preview_consolidated(evidence, value):
    receipt = ConsolidatedSubmission.model_validate(value)
    if (
        receipt.evidence_sha256 != digest(encoded(evidence))
        or receipt.corpus_manifest_sha256 != evidence["corpus_manifest_sha256"]
        or {c.candidate_id: c.binding for c in receipt.cases}
        != {c["candidate_id"]: c["binding"] for c in evidence["cases"]}
    ):
        raise ValueError("stale_or_modified_consolidated_bindings")
    return {
        "receipt_structure_valid": True,
        "approval_requests": [c.candidate_id for c in receipt.cases]
        if receipt.decision == "APPROVE_SCOPED"
        else [],
        "qa_eligible_sections": 0,
        "authority": "preview only; no per-facet attestations inferred",
    }


def _valid_authorization_time(value):
    try:
        start = datetime.fromisoformat(value["valid_from"])
        end = datetime.fromisoformat(value["expires_at"])
        now = datetime.now(UTC)
        if not start.tzinfo or not end.tzinfo or not start <= now < end:
            raise ValueError("authorization_expired_or_not_yet_valid")
    except (KeyError, TypeError) as exc:
        raise ValueError("authorization_requires_validity_interval") from exc


def verify_release(root, path, expected_sha256):
    """Trusted selection pins actual loaded maintained source; defaults stay inert."""
    root = Path(root).resolve()
    raw = local_path(root, path).read_bytes()
    release = json.loads(raw)
    components = {
        RELEASE_VERSION: RELEASE_COMPONENTS,
        COMBINED_RELEASE_VERSION: COMBINED_RELEASE_COMPONENTS,
    }.get(release.get("version"))
    if (
        not expected_sha256
        or digest(raw) != expected_sha256
        or components is None
        or set(release.get("files", {})) != set(components)
        or Path(__file__).resolve() != root / "src/rag_hub/pdf_prose_review.py"
    ):
        raise ValueError("unselected_or_invalid_pdf_QA_successor")
    for name, expected in release["files"].items():
        if digest(local_path(root, name).read_bytes()) != expected:
            raise ValueError("pdf_QA_successor_fingerprint_mismatch: " + name)
    dependencies = release.get("dependencies", {})
    if dependencies != {
        name: importlib.metadata.version(name) for name in ("pydantic", "pymupdf", "markdown-it-py")
    }:
        raise ValueError("pdf_QA_successor_dependency_mismatch")
    return release


def context_projection(case):
    """Reviewed source-bound metadata overlay; never inherit stale Section ancestry."""
    b = case["binding"]
    return {
        "schema": "pdf-reviewed-context-1.0",
        "document_title": b["document_title"],
        "heading_label": b["context_label"],
        "source_spans": b["context_spans"],
        "source_sha256": b["source"]["raw_sha256"],
        "snapshot_id": b["source"]["snapshot_id"],
        "claim_attribution": {
            "mode": "frozen_source_claim",
            "source_url": b["source"]["canonical_url"],
            "source_sha256": b["source"]["raw_sha256"],
            "benchmark_limitation_requires_explicit_report_attribution": case["candidate_id"]
            == "C06-candidate-b00042",
            "universal_fact_verified": False,
        },
    }


def persisted_nontext(
    root,
    source,
    data,
    blocks,
    sections,
    audit,
    classifications,
    *,
    release_path,
    expected_release_sha256,
):
    """Reuse immutable native-object proofs only for exact frozen replay inputs.

    This is not an adapter-supplied empty-text exemption. A new source, changed
    observation or changed normalization still needs the existing native check.
    """
    verify_release(root, release_path, expected_release_sha256)
    document = load_corpus(root)["documents"][source.doc_id]
    if (
        source.model_dump(mode="json") != document["source"]
        or digest(data) != source.raw_sha256
        or [b.model_dump(mode="json") for b in blocks] != document["blocks"]
        or [s.model_dump(mode="json") for s in sections] != document["sections"]
        or audit != document["audit"]
        or classifications != document["pdf_classification"]
    ):
        raise ValueError("persisted_PDF_replay_inputs_changed")
    return document["nontext"]


class Entry(EvidenceModel):
    candidate_id: str
    binding: dict
    facets: dict[str, Literal["PENDING", "PASS", "FAIL", "UNVERIFIED"]]
    owner_decision: Literal["PENDING", "APPROVE_SCOPED", "EXCLUDE", "NEEDS_MORE_CONTEXT"]
    notes: str = ""
    corrections: str = ""
    actual_review_seconds: float | None = Field(
        default=None, ge=0, allow_inf_nan=False, strict=True
    )

    @model_validator(mode="after")
    def consistent(self):
        if set(self.facets) != set(FACETS):
            raise ValueError("missing_or_unknown_review_facet")
        if self.owner_decision == "APPROVE_SCOPED" and (
            any(v != "PASS" for v in self.facets.values()) or self.corrections.strip()
        ):
            raise ValueError("approval_conflicts_with_facets_or_corrections")
        return self


class Submission(EvidenceModel):
    schema_version: Literal["pdf-prose-owner-submission-1.0"]
    packet_id: Literal["pdf-prose-owner-review-1.0"]
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str
    submitted_at: datetime
    entries: tuple[Entry, ...]

    @model_validator(mode="after")
    def identified(self):
        if self.submitted_at.tzinfo is None:
            raise ValueError("submission_requires_timezone")
        if (
            any(
                e.owner_decision != "PENDING" or any(v != "PENDING" for v in e.facets.values())
                for e in self.entries
            )
            and not self.reviewer.strip()
        ):
            raise ValueError("decisions_require_reviewer_identity")
        if len({e.candidate_id for e in self.entries}) != len(self.entries):
            raise ValueError("duplicate_review_case")
        return self


def validate_evidence(root, evidence):
    """Validate existing corpus, source/crop bindings and all candidate/context spans."""
    root = Path(root).resolve()
    if evidence.get("schema") != "pdf-prose-review-evidence-1.0":
        raise ValueError("unknown_evidence_schema")
    if evidence.get("packet_id") != PACKET_ID:
        raise ValueError("unknown_review_packet")
    if (
        evidence["input_fingerprints"].get(evidence["corpus_manifest_path"])
        != evidence["corpus_manifest_sha256"]
    ):
        raise ValueError("inconsistent_corpus_manifest_binding")
    for name, sha in evidence["input_fingerprints"].items():
        if digest(local_path(root, name).read_bytes()) != sha:
            raise ValueError("stale_evidence_input: " + name)
    corpus = load_corpus(root)
    if approved_parents(corpus) != []:
        raise ValueError("unexpected_existing_PDF_admission")
    cases = evidence["cases"]
    expected = json.loads(local_path(root, evidence["candidate_path"]).read_bytes())
    if len(cases) != 8 or {c["candidate_id"] for c in cases} != {
        c["candidate_id"] for c in expected
    }:
        raise ValueError("wrong_or_duplicate_candidate_set")
    candidates = {c["candidate_id"]: c for c in expected}
    if len({c["candidate_id"] for c in cases}) != 8:
        raise ValueError("duplicate_evidence_case")
    total_sections = set()
    for case in cases:
        c = candidates[case["candidate_id"]]
        doc = corpus["documents"][c["doc_id"]]
        parent = next(p for p in doc["parents"] if p["id"] == c["parent_id"])
        blocks = {b["block_id"]: b for b in doc["blocks"]}
        sections = {s["section_id"]: s for s in doc["sections"]}
        qa = {d["section_id"]: d for d in doc["qa"]["quality_decisions"]}
        binding = case["binding"]
        if (
            binding["source"] != c["source"]
            or binding["source"]["source_format"] != "pdf"
            or binding["parent"] != parent
            or binding["parent_sha256"] != digest(encoded(parent))
            or binding["members"] != c["members"]
            or case["text"] != c["text"]
            or case["text"] != parent["text"]
            or binding["text_sha256"] != digest(case["text"].encode())
            or binding["context_spans"] != c["proposed_heading_context_spans"]
            or binding["context_label"] != c["proposed_context"]
            or binding["document_title"] != c["document_title_context"]
        ):
            raise ValueError("candidate_parent_or_context_binding_mismatch")
        if binding["atomic_sections"] != c["atomic_section_bindings"]:
            raise ValueError("section_binding_mismatch")
        covered = set()
        for item in binding["atomic_sections"]:
            ident = item["section_id"]
            if ident in total_sections or ident not in sections or item["qa_decision"] != qa[ident]:
                raise ValueError("duplicate_or_stale_section_decision")
            total_sections.add(ident)
            section = sections[ident]
            if (
                binding["atomic_section_records"].get(ident) != section
                or section["normalized_sha256"] != item["normalized_sha256"]
                or section["index_status"] != "hold"
                or qa[ident]["risk"] != "medium"
                or qa[ident]["status"] != "hold"
                or len(section["block_ids"]) != 1
            ):
                raise ValueError("unsupported_or_unqualified_section_scope")
            b = blocks[section["block_ids"][0]]
            if section["text"] != b["content"]:
                raise ValueError("unsupported_section_transformation")
            covered.add(b["block_id"])
        if covered != {m["block_id"] for m in parent["members"]}:
            raise ValueError("incomplete_parent_section_bundle")
        for m in binding["members"] + binding["context_spans"]:
            b = blocks[m["block_id"]]
            if (
                not (
                    type(m["start"]) is int
                    and type(m["end"]) is int
                    and 0 <= m["start"] < m["end"] <= len(b["content"])
                )
                or m["block_content_sha256"] != b["content_sha256"]
                or m["span_sha256"] != digest(b["content"][m["start"] : m["end"]].encode())
                or m["locator"] != b["locator"]
            ):
                raise ValueError("invalid_or_stale_source_context_span")
        for image in case["source_images"]:
            if digest(local_path(root, image["path"]).read_bytes()) != image["sha256"]:
                raise ValueError("source_image_binding_mismatch")
        if not case["source_images"] or not case["proposed_assessment"]:
            raise ValueError("missing_review_evidence")
    if len(total_sections) != 19:
        raise ValueError("incomplete_atomic_section_universe")
    return corpus


def preview_submission(root, evidence, value):
    """Validate attestations, never establish identity or activate QA admission."""
    validate_evidence(root, evidence)
    if value.get("schema_version") == "pdf-prose-consolidated-owner-submission-1.0":
        return _preview_consolidated(evidence, value)
    submission = Submission.model_validate(value)
    if submission.evidence_sha256 != digest(encoded(evidence)):
        raise ValueError("stale_review_evidence")
    if submission.corpus_manifest_sha256 != evidence["corpus_manifest_sha256"]:
        raise ValueError("stale_review_corpus")
    cases = {c["candidate_id"]: c for c in evidence["cases"]}
    if {e.candidate_id for e in submission.entries} != set(cases):
        raise ValueError("missing_or_foreign_review_cases")
    requests = []
    for entry in submission.entries:
        case = cases[entry.candidate_id]
        if entry.binding != case["binding"]:
            raise ValueError("stale_or_modified_review_binding")
        if entry.owner_decision == "APPROVE_SCOPED":
            if case["proposed_assessment"] != "ACCEPTABLE FOR OWNER APPROVAL":
                raise ValueError("unresolved_case_cannot_request_approval")
            requests.append(entry.candidate_id)
    return {
        "schema": "pdf-prose-receipt-preview-1.0",
        "receipt_structure_valid": True,
        "approval_requests": requests,
        "owner_identity_or_submission_authenticity": "not_established_by_JSON_alone",
        "authority": "none; preview only",
        "qa_eligible_sections": 0,
        "source_fidelity": "manual_required_unchanged",
        "readiness": "not_executed",
        "requires": "explicit owner submission plus separately approved authoritative QA integration",
    }


SCOPED_REASONS = {
    "pdf_visual_layout_review_required": "source_text_fidelity + paragraph_extent + reading_order",
    "registered_source_fidelity_manual_required": "source_text_fidelity, exact parent spans only; source-wide pending unchanged",
    "incomplete_or_list_context": "paragraph_extent + context_sufficiency, complete parent only",
    "sentence_fragment": "paragraph_extent + reading_order, complete parent only",
    "unresolved_context_reference": "heading_document_context + context_sufficiency + excluded_dependencies_absent",
}


def scoped_evidence_proofs(
    root,
    source,
    sections,
    results,
    *,
    evidence,
    submission_bytes,
    policy,
    authorization_bytes,
    expected_authorization_sha256,
    release_path,
    expected_release_sha256,
):
    """New QA execution remains strict about the current authorization window."""
    return _evidence_proofs(
        root,
        source,
        sections,
        results,
        evidence=evidence,
        submission_bytes=submission_bytes,
        policy=policy,
        authorization_bytes=authorization_bytes,
        expected_authorization_sha256=expected_authorization_sha256,
        release_path=release_path,
        expected_release_sha256=expected_release_sha256,
        release_check=verify_release,
        authorization_check=_valid_authorization_time,
    )


def _evidence_proofs(
    root,
    source,
    sections,
    results,
    *,
    evidence,
    submission_bytes,
    policy,
    authorization_bytes,
    expected_authorization_sha256,
    release_path,
    expected_release_sha256,
    release_check,
    authorization_check,
):
    """PROPOSED boundary preconditions only: return evidence, never QA decisions.

    Only the explicitly selected QA successor supplies this evidence. Authorization
    bytes and their expected hash must come from separately approved trusted run
    configuration, never a source document, adapter options or the owner HTML.
    JSON attestations do not cryptographically prove identity; that is an operator
    trust boundary, as with existing project review receipts.
    """
    release_check(root, release_path, expected_release_sha256)
    if (
        not expected_authorization_sha256
        or digest(authorization_bytes) != expected_authorization_sha256
    ):
        raise ValueError("missing_or_unbound_owner_policy_authorization")
    authorization = json.loads(authorization_bytes)
    receipt = json.loads(submission_bytes)
    preview = preview_submission(root, evidence, receipt)
    if (
        authorization.get("action") != "authorize_scoped_pdf_qa_execution"
        or not authorization.get("owner", "").strip()
        or authorization.get("owner") != receipt.get("reviewer")
        or authorization.get("policy_sha256") != digest(encoded(policy))
        or authorization.get("owner_submission_sha256") != digest(submission_bytes)
        or authorization.get("evidence_sha256") != digest(encoded(evidence))
    ):
        raise ValueError("owner_policy_and_content_authorization_mismatch")
    expected_scope = {c["candidate_id"]: digest(encoded(c["binding"])) for c in evidence["cases"]}
    if (
        policy.get("schema") != "bounded-pdf-prose-policy-proposal-1.0"
        or policy.get("case_bindings") != expected_scope
        or policy.get("reason_dispositions") != SCOPED_REASONS
        or policy.get("evidence_sha256") != digest(encoded(evidence))
        or policy.get("consumption") != "complete_parent_bundle_only"
    ):
        raise ValueError("unknown_or_broadened_pdf_prose_policy")
    authorization_check(authorization)
    if datetime.fromisoformat(receipt["submitted_at"]) > datetime.now(UTC):
        raise ValueError("owner_receipt_is_future_dated")
    source_value = source.model_dump(mode="json") if hasattr(source, "model_dump") else source
    if source_value["source_format"] != "pdf" or source_value["doc_id"] not in {
        "C01",
        "C02",
        "C06",
        "C14",
    }:
        raise ValueError("scoped_policy_cannot_admit_other_formats_or_sources")
    current_sections = {s.section_id: s for s in sections}
    current_results = {r.section_id: r for r in results}
    if len(current_sections) != len(sections) or len(current_results) != len(results):
        raise ValueError("duplicate_current_section_or_validation_id")
    requests = set(preview["approval_requests"])
    proofs = {}
    for case in evidence["cases"]:
        if case["candidate_id"] not in requests or case["doc_id"] != source_value["doc_id"]:
            continue
        binding = case["binding"]
        if binding["source"] != source_value:
            raise ValueError("current_source_differs_from_reviewed_snapshot")
        ids = tuple(s["section_id"] for s in binding["atomic_sections"])
        if not set(ids) <= current_sections.keys() or not set(ids) <= current_results.keys():
            raise ValueError("partial_parent_bundle_cannot_be_admitted")
        scope = {
            "candidate_id": case["candidate_id"],
            "retrieval_context_projection": context_projection(case),
            "parent_id": binding["parent"]["id"],
            "parent_sha256": binding["parent_sha256"],
            "context_sha256": digest(
                encoded(
                    {k: binding[k] for k in ("context_spans", "context_label", "document_title")}
                )
            ),
            "required_section_ids": ids,
            "whole_parent_required": True,
            "policy_scope_sha256": digest(encoded(policy)),
            "owner_policy_authorization_sha256": expected_authorization_sha256,
            "qa_release_sha256": expected_release_sha256,
        }
        for item in binding["atomic_sections"]:
            ident = item["section_id"]
            section, result = current_sections[ident], current_results[ident]
            expected_reasons = set(item["qa_decision"]["reasons"])
            if (
                section.model_dump(mode="json") != binding["atomic_section_records"][ident]
                or section.normalized_sha256 != item["normalized_sha256"]
                or result.doc_id != source_value["doc_id"]
                or section.raw_sha256 != source_value["raw_sha256"]
                or section.index_status != "hold"
                or result.raw_sha256 != source_value["raw_sha256"]
                or result.normalized_sha256 != section.normalized_sha256
                or result.risk != "medium"
                or result.blocking_integrity
                or set(result.reasons) != expected_reasons
                or not set(result.reasons) <= SCOPED_REASONS.keys()
                or set(result.checks)
                != {"audit", "context", "integrity", "provenance", "source_fidelity"}
                or any(result.checks[k] != "pass" for k in ("audit", "integrity", "provenance"))
                or result.checks["context"] not in ("pass", "manual_required")
                or result.checks["source_fidelity"] != "manual_required"
            ):
                raise ValueError("unresolved_or_changed_Section_checks_cannot_be_overridden")
            proofs[ident] = {
                "scope": scope,
                "receipt_sha256": digest(submission_bytes),
                "reviewed_reasons": {r: SCOPED_REASONS[r] for r in result.reasons},
                "source_fidelity": "manual_required_unchanged",
                "authority": "evidence_preconditions_only_not_eligibility",
            }
    return proofs
