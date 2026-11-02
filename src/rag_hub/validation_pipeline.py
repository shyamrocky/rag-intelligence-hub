"""Offline immutable validation runs over a pinned ingestion snapshot."""

import difflib
import importlib.metadata
import json
import tempfile
from collections import Counter
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.content_validation import classify_all, load_input, validate_section
from rag_hub.pipeline import encode, jsonl
from rag_hub.validation_models import QualityReview, ValidationPolicy
from rag_hub.validation_reviews import cohort_gates, make_decisions, original_decisions
from rag_hub.validation_sampling import fingerprint, sample_sections

MODULES = (
    "validation_models",
    "source_fidelity",
    "content_validation",
    "validation_sampling",
    "validation_reviews",
    "validation_pipeline",
)


def private_json(root, path):
    p = local_path(root, path)
    if not any(p.is_relative_to(root.resolve() / base) for base in ("workspace", "data")):
        raise ValueError("review/exclusion artifacts must be private")
    return json.loads(p.read_text())


def validate_content(
    root: Path,
    *,
    policy_path="config/validation-policy.json",
    reviews_path=None,
    exclusions_path=None,
    expansion_cohorts=(),
    role="acceptance",
):
    root = root.resolve()
    policy = ValidationPolicy.model_validate_json(local_path(root, policy_path).read_text())
    context = load_input(root, policy)
    results = classify_all(context, policy)
    exclusions = private_json(root, exclusions_path) if exclusions_path else []
    if not isinstance(exclusions, list) or any(not isinstance(v, str) for v in exclusions):
        raise ValueError("exclusions must be a list of prior calibration section IDs")
    if set(exclusions) - {r.section_id for r in results}:
        raise ValueError("unknown excluded sample IDs")
    plan = sample_sections(
        results, policy, excluded_ids=exclusions, expansion_cohorts=expansion_cohorts, role=role
    )
    reviews = (
        [QualityReview.model_validate(x) for x in private_json(root, reviews_path)]
        if reviews_path
        else []
    )
    gates, mapped = cohort_gates(results, plan, policy, reviews)
    decisions = make_decisions(results, policy, gates, mapped)
    legacy = original_decisions(context, policy, validate_section)
    all_decisions = decisions + legacy
    lookup = {s.section_id: s for s in context.sections}
    versions = {p: importlib.metadata.version(p) for p in ("pydantic", "pymupdf", "markdown-it-py")}
    implementation = digest(
        b"".join(Path(__file__).with_name(m + ".py").read_bytes() for m in MODULES)
    )
    lock = local_path(root, "uv.lock")
    identity = {
        "policy": policy.model_dump(),
        "sample": plan.model_dump(),
        "reviews": [r.model_dump() for r in reviews],
        "versions": versions,
        "implementation_sha256": implementation,
        "lock_sha256": digest(lock.read_bytes()) if lock.exists() else None,
    }
    run_id = digest(encode(identity).encode())
    queue = []
    for sid in plan.selected_ids:
        s = lookup[sid]
        b = context.blocks[s.block_ids[0]]
        loc = b.locator
        source = context.sources[s.doc_id]
        entry = {
            "section": s.model_dump(mode="json"),
            "block": b.model_dump(mode="json"),
            "validation": next(r.model_dump() for r in results if r.section_id == sid),
            "sample_sha256": fingerprint(plan),
            "policy_sha256": fingerprint(policy),
            "raw_path": str(source.raw_path),
            "neighbors": [
                x.model_dump(mode="json")
                for x in context.sections
                if x.doc_id == s.doc_id
                and any(abs(context.blocks[i].sequence - b.sequence) <= 2 for i in x.block_ids)
            ],
        }
        if loc.line_start:
            lines = context.raw[s.doc_id].decode().splitlines(keepends=True)
            raw_span = "".join(lines[loc.line_start - 1 : loc.line_end])
            entry["original_source_span"] = raw_span
            entry["source_context"] = "".join(lines[max(0, loc.line_start - 5) : loc.line_end + 4])
            entry["source_diff"] = "".join(
                difflib.unified_diff(
                    raw_span.splitlines(True),
                    s.text.splitlines(True),
                    fromfile="raw source span",
                    tofile="normalized section",
                )
            )
        queue.append(entry)
    by_doc = {}
    for doc in sorted(context.sources):
        doc_d = [d for d in all_decisions if d.doc_id == doc]
        by_doc[doc] = {
            "baseline_hold": sum(r.doc_id == doc for r in results),
            "validation_coverage": sum(r.doc_id == doc for r in results),
            "risk": dict(Counter(r.risk for r in results if r.doc_id == doc)),
            "approved_by_basis": dict(
                Counter(d.basis for d in doc_d if d.status == "approved_for_index")
            ),
            "remaining_hold_including_originals": sum(d.status == "hold" for d in doc_d),
        }
    blocked = {k: v for k, v in gates.items() if not v["qualified"]}
    report = {
        "run_id": run_id,
        "input_run_id": context.run_id,
        "policy_sha256": fingerprint(policy),
        "input_artifact_sha256": context.artifact_sha256,
        "validation_coverage": len(results),
        "expected_hold": policy.expected_hold_count,
        "coverage_percent": 100 * len(results) / policy.expected_hold_count
        if policy.expected_hold_count
        else 100,
        "by_document": by_doc,
        "risk": dict(Counter(r.risk for r in results)),
        "automatic_candidates": sum(r.eligible_automatic for r in results),
        "approvals_by_risk_and_basis": dict(
            Counter(
                d.risk + ":" + d.basis for d in all_decisions if d.status == "approved_for_index"
            )
        ),
        "approved_total": sum(d.status == "approved_for_index" for d in all_decisions),
        "remaining_hold_total": sum(d.status == "hold" for d in all_decisions),
        "remaining_baseline_hold": sum(d.status == "hold" for d in decisions),
        "original_receipts_preserved": len(context.original_receipts),
        "original_approvals_suspended_for_new_manifest": sum(d.status == "hold" for d in legacy),
        "hold_reason_counts_overlapping": dict(
            Counter(v for d in all_decisions if d.status == "hold" for v in d.reasons)
        ),
        "sample": {
            "initial": len(plan.initial_ids),
            "expanded": len(plan.selected_ids),
            "expansion_count": len(plan.expansion),
            "reviewed": len(mapped),
            "role": plan.role,
            "coverage_missing": list(plan.coverage_missing),
            "verdicts": dict(Counter(v.verdict for v in mapped.values())),
        },
        "blocked_cohorts": blocked,
        "cohort_gates": gates,
        "systematic_integrity_defects": dict(
            Counter(r.cohort for r in results if r.blocking_integrity)
        ),
        "versions": versions,
        "implementation_sha256": implementation,
        "limits": [
            "Manual sample reviews are operator attestations, not independent human certification",
            "No automatic medium/high promotion; PDF source fidelity needs visual review",
            "Context heuristics are conservative, not proof of factual correctness",
            "Source approval is not indexing or answer quality readiness",
        ],
    }
    approved_manifest = {
        "validation_run_id": run_id,
        "input_run_id": context.run_id,
        "policy_sha256": fingerprint(policy),
        "approved": [d.model_dump() for d in all_decisions if d.status == "approved_for_index"],
    }
    artifacts = {
        "policy.json": encode(policy.model_dump()),
        "results.jsonl": jsonl(results),
        "sample.json": encode(plan.model_dump()),
        "review_queue.jsonl": jsonl(queue),
        "reviews.json": encode([r.model_dump() for r in reviews]),
        "decisions.jsonl": jsonl(all_decisions),
        "approved_manifest.json": encode(approved_manifest),
        "holds.jsonl": jsonl([d for d in all_decisions if d.status == "hold"]),
        "original_reviews.json": encode([r.model_dump() for r in context.original_receipts]),
        "identity.json": encode(identity),
        "report.json": encode(report),
    }
    directory = local_path(root, Path("data/validation") / run_id)
    directory.parent.mkdir(parents=True, exist_ok=True)
    if directory.exists():
        for name, text in artifacts.items():
            p = local_path(root, directory.relative_to(root) / name)
            if not p.exists() or p.read_text() != text:
                raise ValueError("immutable validation artifacts differ")
    else:
        with tempfile.TemporaryDirectory(dir=directory.parent) as temp:
            p = Path(temp) / "run"
            p.mkdir()
            for name, text in artifacts.items():
                (p / name).write_text(text)
            p.rename(directory)
    return {
        "run_id": run_id,
        "output": str(directory.relative_to(root)),
        "coverage": len(results),
        "sample": len(plan.selected_ids),
        "reviewed": len(mapped),
        "approved": report["approved_total"],
        "remaining_hold": report["remaining_hold_total"],
    }
