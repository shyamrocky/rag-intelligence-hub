"""Versioned cohort qualification and fail-closed promotion decisions."""

import json
from collections import defaultdict

from rag_hub.acquire import digest
from rag_hub.validation_models import (
    QualityDecision,
    QualityReview,
    SamplePlan,
    ScopedPdfDecision,
    ValidationPolicy,
)
from rag_hub.validation_sampling import fingerprint, validator_fingerprint


def review_map(results, plan: SamplePlan, policy: ValidationPolicy, reviews: list[QualityReview]):
    lookup = {r.section_id: r for r in results}
    if (
        fingerprint(policy) != plan.policy_sha256
        or plan.validator_sha256 != validator_fingerprint()
    ):
        raise ValueError("sampling policy is stale")
    mapped = {}
    for review in reviews:
        if review.section_id in mapped:
            raise ValueError("duplicate quality review")
        r = lookup.get(review.section_id)
        if r is None or review.section_id not in plan.selected_ids:
            raise ValueError("review outside selected sample")
        if (
            review.policy_sha256 != fingerprint(policy)
            or review.sample_sha256 != fingerprint(plan)
            or review.role != plan.role
            or review.raw_sha256 != r.raw_sha256
            or review.normalized_sha256 != r.normalized_sha256
        ):
            raise ValueError("stale quality review evidence")
        if review.verdict == "pass" and (r.blocking_integrity or r.risk == "high"):
            raise ValueError("review cannot pass an unresolved integrity/high-risk record")
        if review.manual_approval and (
            review.method != "visual_source_comparison"
            or r.risk != "medium"
            or any(reason != "pdf_visual_layout_review_required" for reason in r.reasons)
        ):
            raise ValueError("manual approval cannot override unresolved content/context blockers")
        mapped[review.section_id] = review
    return mapped


def cohort_gates(results, plan, policy, reviews):
    mapped = review_map(results, plan, policy, reviews)
    grouped = defaultdict(list)
    for r in results:
        grouped[r.cohort].append(r)
    gates = {}
    for name, members in sorted(grouped.items()):
        eligible = [r for r in members if r.eligible_automatic]
        blockers = []
        relevant = [mapped[r.section_id] for r in members if r.section_id in mapped]
        if any(r.blocking_integrity for r in members) or any(
            v.verdict == "defect" for v in relevant
        ):
            blockers.append("systematic_defect_requires_followup")
        if any(
            r.eligible_automatic
            and r.section_id in mapped
            and mapped[r.section_id].verdict == "confirmed_hold"
            for r in members
        ):
            blockers.append("review_disagrees_with_automatic_eligibility")
        if not eligible:
            blockers.append("no_automatic_candidates")
        if plan.role != "acceptance":
            blockers.append("calibration_is_not_acceptance")
        if set(plan.selected_ids) - mapped.keys():
            blockers.append("incomplete_sample_review")
        if plan.coverage_missing:
            blockers.append("sample_coverage_missing")
        passed = [
            r for r in eligible if r.section_id in mapped and mapped[r.section_id].verdict == "pass"
        ]
        if len(passed) < min(policy.min_eligible_reviews_per_cohort, len(eligible)):
            blockers.append("insufficient_eligible_acceptance_reviews")
        # Every metadata/source category in a cohort must have representative reviewed evidence.
        required = {
            tag
            for r in members
            for tag in r.coverage_tags
            if tag.startswith(("provider:", "group:", "language:", "length:", "type:"))
        }
        covered = {
            tag
            for r in members
            if r.section_id in mapped and mapped[r.section_id].verdict in ("pass", "confirmed_hold")
            for tag in r.coverage_tags
        }
        if required - covered:
            blockers.append("cohort_metadata_coverage_missing")
        gates[name] = {
            "qualified": not blockers,
            "candidate_count": len(eligible),
            "passing_acceptance_reviews": len(passed),
            "blockers": blockers,
            "required_tags": sorted(required),
            "covered_tags": sorted(covered),
            "qualification_sha256": digest(
                (
                    fingerprint(plan)
                    + "".join(
                        fingerprint(mapped[r.section_id])
                        for r in sorted(members, key=lambda x: x.section_id)
                        if r.section_id in mapped
                    )
                ).encode()
            ),
        }
    return gates, mapped


def make_decisions(
    results,
    policy,
    gates,
    mapped,
    *,
    scoped_pdf_proofs=None,
    scoped_html_proofs=None,
    markdown_proofs=None,
    pdf_text_proofs=None,
):
    if set(pdf_text_proofs or {}) & (
        set(scoped_pdf_proofs or {}) | set(scoped_html_proofs or {}) | set(markdown_proofs or {})
    ):
        raise ValueError("conflicting_format_admission_proofs")
    if set(markdown_proofs or {}) & (set(scoped_pdf_proofs or {}) | set(scoped_html_proofs or {})):
        raise ValueError("conflicting_format_admission_proofs")
    decisions = []
    for r in results:
        reasons = list(r.reasons)
        pdf_text_proof = (pdf_text_proofs or {}).get(r.section_id)
        if pdf_text_proof is not None:
            from rag_hub.pdf_text_recovery import decision_from_proof

            decisions.append(decision_from_proof(r, policy, pdf_text_proof))
            continue
        markdown_proof = (markdown_proofs or {}).get(r.section_id)
        if markdown_proof is not None:
            from rag_hub.markdown_qualification import decision_from_proof

            decisions.append(decision_from_proof(r, policy, markdown_proof))
            continue
        html_proof = (scoped_html_proofs or {}).get(r.section_id)
        if html_proof is not None:
            from rag_hub.html_qualification import decision_from_proof

            if (scoped_pdf_proofs or {}).get(r.section_id) is not None:
                raise ValueError("conflicting_format_admission_proofs")
            decisions.append(decision_from_proof(r, policy, html_proof))
            continue
        proof = (scoped_pdf_proofs or {}).get(r.section_id)
        if proof is not None:
            # Only the QA owner supplies validated, explicitly authorized evidence.
            # Preserve legacy ValidationResult and original ledger unchanged.
            if (
                r.risk != "medium"
                or r.blocking_integrity
                or set(proof["reviewed_reasons"]) != set(r.reasons)
            ):
                raise ValueError("scoped_evidence_cannot_override_unresolved_checks")
            decisions.append(
                ScopedPdfDecision(
                    section_id=r.section_id,
                    doc_id=r.doc_id,
                    risk=r.risk,
                    status="approved_for_index",
                    basis="scoped_pdf_owner_review",
                    raw_sha256=r.raw_sha256,
                    normalized_sha256=r.normalized_sha256,
                    policy_sha256=fingerprint(policy),
                    validation_sha256=fingerprint(r),
                    receipt_sha256=proof["receipt_sha256"],
                    reasons=(),
                    scope=proof["scope"],
                    reviewed_reason_dispositions=proof["reviewed_reasons"],
                )
            )
            continue
        status, basis, receipt = "hold", "hold", None
        manual = mapped.get(r.section_id)
        if (
            r.risk == "medium"
            and manual
            and manual.manual_approval
            and manual.verdict == "pass"
            and not r.blocking_integrity
            and r.reasons == ("pdf_visual_layout_review_required",)
        ):
            status, basis, receipt = (
                "approved_for_index",
                "visual_manual_review",
                fingerprint(manual),
            )
        elif (
            r.eligible_automatic
            and r.risk == "low"
            and r.doc_id in policy.automatic_documents
            and not r.reasons
            and all(v == "pass" for v in r.checks.values())
            and gates[r.cohort]["qualified"]
        ):
            status, basis = "approved_for_index", "deterministic_source_match"
            receipt = digest(
                (
                    fingerprint(r)
                    + fingerprint(policy)
                    + json.dumps(gates[r.cohort], sort_keys=True)
                ).encode()
            )
        elif r.eligible_automatic:
            reasons.extend(gates[r.cohort]["blockers"])
        if manual and manual.verdict in ("defect", "confirmed_hold") and r.eligible_automatic:
            status, basis, receipt = "hold", "hold", None
            reasons.append("manual_defect_requires_followup")
        decisions.append(
            QualityDecision(
                section_id=r.section_id,
                doc_id=r.doc_id,
                risk=r.risk,
                status=status,
                basis=basis,
                raw_sha256=r.raw_sha256,
                normalized_sha256=r.normalized_sha256,
                policy_sha256=fingerprint(policy),
                validation_sha256=fingerprint(r),
                receipt_sha256=receipt,
                reasons=tuple(sorted(set(reasons))),
            )
        )
    return decisions


def original_decisions(context, policy, validator):
    """Preserve original receipts; stricter context rules can suspend new manifest eligibility."""
    receipts = {r.section_id: r for r in context.original_receipts}
    decisions = []
    for section in context.sections:
        if section.section_id not in receipts:
            continue
        r = validator(section, context, policy)
        reasons = [reason for reason in r.reasons if reason != "pdf_visual_layout_review_required"]
        approved = not reasons and r.risk != "high"
        decisions.append(
            QualityDecision(
                section_id=r.section_id,
                doc_id=r.doc_id,
                risk=r.risk,
                status="approved_for_index" if approved else "hold",
                basis="original_manual_receipt" if approved else "hold",
                raw_sha256=r.raw_sha256,
                normalized_sha256=r.normalized_sha256,
                policy_sha256=fingerprint(policy),
                validation_sha256=fingerprint(r),
                receipt_sha256=fingerprint(receipts[r.section_id]),
                reasons=tuple(
                    sorted(
                        set(
                            reasons + ([] if approved else ["original_review_context_not_complete"])
                        )
                    )
                ),
            )
        )
    return decisions
