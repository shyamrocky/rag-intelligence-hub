"""One QA owner; format components supply evidence, existing engine decides HOLD."""

from collections import defaultdict

import pymupdf

from rag_hub.content_validation import ValidationInput, validate_section
from rag_hub.validation_models import ScopedPdfDecision, ValidationPolicy, ValidationResult
from rag_hub.validation_reviews import cohort_gates, make_decisions
from rag_hub.validation_sampling import sample_sections

from .evidence import Check
from .registry import REQUIRED


def assess(
    root,
    source,
    data,
    blocks,
    sections,
    audit,
    adapter,
    input_id,
    input_hashes,
    *,
    classifications=None,
    pdf_prose_admission=None,
    pdf_replay=None,
    html_evidence=None,
    html_admission=None,
    markdown_qualification=None,
    pdf_text_admission=None,
):
    classification_summary = None
    if source.source_format == "pdf":
        if classifications is None:
            raise ValueError("missing_required_pdf_classification_evidence")
        from rag_hub.pdf_classification import summarize, validate_classification
        from rag_hub.pdf_nontext import inspect_nontext

        if pdf_replay is None:
            observations = inspect_nontext(data, source, blocks)
        else:
            from rag_hub.pdf_prose_review import persisted_nontext

            observations = persisted_nontext(
                root, source, data, blocks, sections, audit, classifications, **pdf_replay
            )
        objects = {r["block_id"]: r for r in observations}
        validate_classification(classifications, source, blocks, object_evidence=objects)
        classification_summary = summarize(classifications, blocks)
    evidence = list(adapter.fidelity(data, source, blocks, sections, dict(adapter.options)))
    evidence = [
        Check.model_validate(x.model_dump() if hasattr(x, "model_dump") else x) for x in evidence
    ]
    names = [e.name for e in evidence]
    if len(set(names)) != len(names) or set(names) != REQUIRED:
        raise ValueError("missing_or_duplicate_required_fidelity_evidence")
    if any(not e.evidence or e.dimension != "source_fidelity" or not e.required for e in evidence):
        raise ValueError("invalid_fidelity_evidence_contract")
    grouped = defaultdict(list)
    for row in audit:
        grouped[row["block_id"]].append(row)
    sizes = {}
    if source.source_format == "pdf":
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            sizes[source.doc_id] = [(p.rect.width, p.rect.height) for p in pdf]
    # A new fixture policy instance pins its actual input artifacts/counts. The
    # unchanged quality-1.0 model still enforces C04-only automatic permissions.
    policy = ValidationPolicy(
        input_run_id=input_id,
        artifact_sha256=input_hashes,
        expected_hold_count=len(sections),
        expected_original_approvals=0,
    )
    context = ValidationInput(
        root,
        input_id,
        sections,
        {b.block_id: b for b in blocks},
        {source.doc_id: source},
        {source.doc_id: data},
        sizes,
        dict(grouped),
        [],
        input_hashes,
        html_evidence=html_evidence,
    )
    results = []
    persisted_pdf_results = None
    if pdf_text_admission is not None:
        from rag_hub.pdf_text_recovery import persisted_results

        persisted_pdf_results = persisted_results(
            root, source, data, blocks, sections, audit, **pdf_text_admission
        )
    fidelity_outcome = (
        "fail"
        if any(e.outcome == "fail" for e in evidence)
        else "manual_required"
        if any(e.outcome == "pending" for e in evidence)
        else "pass"
    )
    for s in sections:
        legacy = (
            persisted_pdf_results[s.section_id]
            if persisted_pdf_results is not None
            else validate_section(s, context, policy)
        )
        values = legacy.model_dump()
        # Only the format-dispatch seam changes. Preserve every existing
        # integrity/context hazard and the exact historical eligibility rules.
        reasons = set(legacy.reasons)
        if source.source_format not in ("pdf", "markdown_mdx", "html"):
            reasons.discard("unsupported_source_format")
            reasons.add("format_qualification_not_established")
            values["eligible_automatic"] = False
        values["checks"]["source_fidelity"] = fidelity_outcome
        if fidelity_outcome != "pass":
            reasons.add("registered_source_fidelity_" + fidelity_outcome)
            values["eligible_automatic"] = False
        if fidelity_outcome == "fail":
            values["blocking_integrity"] = True
            values["risk"] = "high"
        values["reasons"] = tuple(sorted(reasons))
        results.append(ValidationResult.model_validate(values))
    plan = sample_sections(results, policy)
    gates, mapped = cohort_gates(results, plan, policy, [])
    scoped_proofs = {}
    if pdf_prose_admission is not None:
        # Trusted run configuration ONLY, never adapter options or source content.
        from rag_hub.pdf_prose_review import scoped_evidence_proofs

        scoped_proofs = scoped_evidence_proofs(
            root, source, sections, results, **pdf_prose_admission
        )
    html_proofs, html_support = {}, None
    if html_admission is not None:
        from rag_hub.html_qualification import evidence_proofs

        html_proofs, html_support = evidence_proofs(
            root, source, data, blocks, sections, audit, results, **html_admission
        )
    markdown_proofs = {}
    if markdown_qualification is not None:
        from rag_hub.markdown_qualification import evidence_proofs

        markdown_proofs = evidence_proofs(root, source, sections, results, **markdown_qualification)
    pdf_text_proofs, pdf_text_support = {}, None
    if pdf_text_admission is not None:
        if source.source_format != "pdf" or pdf_prose_admission is not None:
            raise ValueError("conflicting_or_foreign_pdf_text_admission")
        from rag_hub.pdf_text_recovery import evidence_proofs

        pdf_text_proofs, pdf_text_support = evidence_proofs(
            root, source, data, blocks, sections, audit, results, **pdf_text_admission
        )
    decisions = make_decisions(
        results,
        policy,
        gates,
        mapped,
        scoped_pdf_proofs=scoped_proofs,
        scoped_html_proofs=html_proofs,
        markdown_proofs=markdown_proofs,
        pdf_text_proofs=pdf_text_proofs,
    )
    if any(
        d.status != "hold"
        and not (
            isinstance(d, ScopedPdfDecision)
            and d.section_id in scoped_proofs
            and d.scope == scoped_proofs[d.section_id]["scope"]
        )
        and d.section_id not in html_proofs
        and d.section_id not in markdown_proofs
        and d.section_id not in pdf_text_proofs
        for d in decisions
    ):
        raise ValueError("unqualified_registration_cannot_promote")
    published = {
        "classification_assessment": classification_summary,
        "fidelity_checks": [e.model_dump(mode="json") for e in evidence],
        "validation_results": [r.model_dump(mode="json") for r in results],
        "quality_decisions": [d.model_dump(mode="json") for d in decisions],
        "policy": policy.model_dump(mode="json"),
        "sample": plan.model_dump(mode="json"),
        "cohort_gates": gates,
        "source_fidelity": fidelity_outcome,
        "context_assessment": [
            {"section_id": r.section_id, "outcome": r.checks["context"], "reasons": r.reasons}
            for r in results
        ],
        "qualification": "pending; registration is not content eligibility or source readiness",
    }
    if html_support is not None:
        published["scoped_html_support"] = html_support
        published["qualification"] = (
            "Scoped frozen textual HTML units only; visual/semantic/source-wide readiness not granted."
        )
    if pdf_text_support is not None:
        published["pdf_text_support"] = pdf_text_support
        published["pdf_text_admission"] = pdf_text_admission
        published["pdf_text_fingerprint_inputs"] = {
            "policy_json": policy.model_dump_json(),
            "validation_json": [r.model_dump_json() for r in results],
        }
        published["qualification"] = (
            "Source-bound complete PDF text units/projections only; no whole-source readiness."
        )
    if markdown_proofs:
        published["markdown_support"] = {
            "schema": "markdown-complete-unit-QA-support-1.0",
            "arguments": markdown_qualification,
            "policy_json": policy.model_dump_json(),
            "validation_json": [r.model_dump_json() for r in results],
        }
        published["qualification"] = (
            "Source-bound documentation units only; limitations mandatory; no readiness grant."
        )
    if scoped_proofs:
        # Supporting receipts live in the sole QA publication, not a new ledger.
        from base64 import b64encode

        published["qualification"] = (
            "Scoped parent-bundle reviews only; source-wide qualification pending; no readiness grant."
        )
        published["scoped_pdf_support"] = {
            "schema": "scoped-pdf-QA-support-1.0",
            "evidence": pdf_prose_admission["evidence"],
            "policy": pdf_prose_admission["policy"],
            "original_owner_submission_base64": b64encode(
                pdf_prose_admission["submission_bytes"]
            ).decode(),
            "original_policy_authorization_base64": b64encode(
                pdf_prose_admission["authorization_bytes"]
            ).decode(),
            "authorization_sha256": pdf_prose_admission["expected_authorization_sha256"],
            "source_wide_fidelity_changed": False,
            "consumption": "complete_parent_bundle_only",
            "release_path": str(pdf_prose_admission["release_path"]),
            "release_sha256": pdf_prose_admission["expected_release_sha256"],
            # Legacy fingerprints use insertion-ordered model_dump_json bytes.
            # Preserve those bytes across canonical (sorted-key) publications.
            "decision_fingerprint_inputs": {
                "policy_json": policy.model_dump_json(),
                "validation_json": {r.section_id: r.model_dump_json() for r in results},
            },
        }
    return published
