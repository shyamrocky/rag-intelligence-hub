"""Source-bound HTML review receipt validation, reusing existing review machinery.

This module validates future evidence only. It cannot authorize or construct an
eligible decision, clear a source restriction or mutate an ingestion record.
"""

import json

from pydantic import Field

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode
from rag_hub.validation_models import EvidenceModel, QualityReview
from rag_hub.validation_reviews import review_map
from rag_hub.validation_sampling import fingerprint


class HtmlReviewReceipt(EvidenceModel):
    schema_version: str = Field(
        default="html-section-review-1.0", pattern=r"^html-section-review-1\.0$"
    )
    binding: dict
    review: QualityReview
    evidence_references: dict[str, str] = Field(min_length=1)


def review_binding(document, row, result, *, qa_artifact_sha256):
    """Exact evidence scope for one Section; a cohort is an exact set of these."""
    source = document["source"]
    section = row["section"]
    if source.source_format != "html" or not document.get("bindings_verified"):
        raise ValueError("HTML_review_requires_verified_HTML_source")
    record = next(
        r for r in document["parsed"]["records"] if r["block"]["block_id"] in section["block_ids"]
    )
    neighbors = document["normalized"]["records"]
    position = next(
        i for i, r in enumerate(neighbors) if r["section"]["section_id"] == section["section_id"]
    )
    containers = {c["dom_path"]: c for c in document["parsed"]["containers"]}
    heading_records = [
        r
        for r in document["parsed"]["records"]
        if r["classification"] == "heading"
        and r["block"]["sequence"] <= record["block"]["sequence"]
        and r["block"]["heading_path"] == section["heading_path"][: len(r["block"]["heading_path"])]
    ]
    if (
        result.section_id != section["section_id"]
        or result.normalized_sha256 != section["normalized_sha256"]
        or result.raw_sha256 != source.raw_sha256
    ):
        raise ValueError("HTML_review_result_binding_mismatch")
    return {
        "source_format": "html",
        "corpus_id": document["corpus_id"],
        "doc_id": source.doc_id,
        "section_id": section["section_id"],
        "canonical_url": str(source.canonical_url),
        "original_url": str(source.original_url),
        "source_snapshot_sha256": source.raw_sha256,
        "snapshot_id": source.snapshot_id,
        "normalized_sha256": section["normalized_sha256"],
        "raw_locator": {k: record[k] for k in ("dom_path", "raw_char_span", "raw_fragment_sha256")},
        "citation_locators": section["locators"],
        "heading_path": section["heading_path"],
        "source_tree_sha256": digest(encode(record["source_tree"])),
        "dependencies": {
            "containers": [containers[p] for p in record["contexts"]],
            "declared_heading_evidence": [
                {
                    "block_id": r["block"]["block_id"],
                    "dom_path": r["dom_path"],
                    "raw_char_span": r["raw_char_span"],
                    "raw_fragment_sha256": r["raw_fragment_sha256"],
                }
                for r in heading_records
            ],
            "adjacent_sections": [
                {
                    "section_id": r["section"]["section_id"],
                    "normalized_sha256": r["section"]["normalized_sha256"],
                }
                for i, r in enumerate(neighbors)
                if abs(i - position) == 1
            ],
            "unresolved_reasons": list(result.reasons),
            "source_restriction": "pending_independent_scoped_review_no_source_wide_certification",
        },
        "applicable_validation_checks": result.checks,
        "validation_result_sha256": fingerprint(result),
        "qa_artifact_sha256": qa_artifact_sha256,
        "required_evidence_references": {
            str(source.raw_path): source.raw_sha256,
            str(source.snapshot_path): source.raw_sha256,
            f"data/validation/html/v2/{source.doc_id}.json": qa_artifact_sha256,
            **{
                a["path"]: a["sha256"]
                for name, a in document.get("entry", {}).get("paths", {}).items()
                if name in {"source", "parsed", "normalized", "acquisition"}
            },
        },
    }


def validate_receipt(
    submission, *, expected_submission_sha256, expected_binding, results, plan, policy, root
):
    """Validate an explicitly owner-confirmed submission; return a review, not eligibility.

    expected_submission_sha256 must come from trusted owner-confirmed run input,
    never the submitted JSON or source/adapter options. Local receipts are operator
    attestations, not cryptographic signatures. Missing confirmation fails closed.
    """
    if not expected_submission_sha256 or digest(submission) != expected_submission_sha256:
        raise ValueError("HTML_review_missing_or_unconfirmed_submission")
    receipt = HtmlReviewReceipt.model_validate_json(submission)
    if receipt.binding != expected_binding:
        raise ValueError("HTML_review_stale_source_DOM_context_or_QA_binding")
    if expected_binding.get("source_format") != "html":
        raise ValueError("HTML_review_requires_HTML_format")
    required = expected_binding.get("required_evidence_references", {})
    if not required or any(
        receipt.evidence_references.get(path) != sha for path, sha in required.items()
    ):
        raise ValueError("HTML_review_missing_required_source_or_QA_evidence")
    review = receipt.review
    if (
        review.section_id != expected_binding["section_id"]
        or review.raw_sha256 != expected_binding["source_snapshot_sha256"]
        or review.normalized_sha256 != expected_binding["normalized_sha256"]
        or review.manual_approval
    ):
        raise ValueError("HTML_review_cannot_override_eligibility_or_source_restrictions")
    selected = next((r for r in results if r.section_id == review.section_id), None)
    if selected is None or fingerprint(selected) != expected_binding["validation_result_sha256"]:
        raise ValueError("HTML_review_current_validation_mismatch")
    for path, expected in receipt.evidence_references.items():
        if len(expected) != 64 or digest(local_path(root, path).read_bytes()) != expected:
            raise ValueError("HTML_review_missing_or_changed_evidence_reference")
    # Existing policy/sample/role/hash and high-risk/integrity checks stay authoritative.
    review_map(results, plan, policy, [review])
    return review


def validate_cohort(
    submissions, *, expected_ids, expected_submission_hashes, bindings, results, plan, policy, root
):
    """An exact declared cohort; reject missing, duplicate or extra Section reviews."""
    reviewed = {}
    for submission in submissions:
        # Identity is untrusted until validated below.
        section_id = json.loads(submission)["review"]["section_id"]
        if section_id in reviewed or section_id not in expected_ids:
            raise ValueError("HTML_review_duplicate_or_out_of_scope_Section")
        reviewed[section_id] = validate_receipt(
            submission,
            expected_submission_sha256=expected_submission_hashes.get(section_id),
            expected_binding=bindings[section_id],
            results=results,
            plan=plan,
            policy=policy,
            root=root,
        )
    if set(reviewed) != set(expected_ids):
        raise ValueError("HTML_review_incomplete_declared_cohort")
    return reviewed
