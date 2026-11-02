"""Reproducible stratification, adaptive coverage and disjoint acceptance selection."""

from pathlib import Path

from rag_hub.acquire import digest
from rag_hub.validation_models import SamplePlan, ValidationPolicy, ValidationResult


def validator_fingerprint() -> str:
    modules = (
        "validation_models",
        "source_fidelity",
        "content_validation",
        "validation_sampling",
        "validation_reviews",
        "validation_pipeline",
    )
    return digest(b"".join(Path(__file__).with_name(m + ".py").read_bytes() for m in modules))


def fingerprint(model) -> str:
    return digest(model.model_dump_json().encode())


def group(result: ValidationResult) -> str:
    return "medium:" + result.doc_id if result.risk == "medium" else result.risk


def sample_sections(
    results: list[ValidationResult],
    policy: ValidationPolicy,
    *,
    excluded_ids=(),
    expansion_cohorts=(),
    role="acceptance",
) -> SamplePlan:
    excluded = set(excluded_ids)
    available = [r for r in results if r.section_id not in excluded]

    def order(row):
        return digest((policy.seed + ":" + role + ":" + row.section_id).encode())

    available.sort(key=order)
    selected = set()
    for g, target in policy.sample_targets.items():
        selected.update(r.section_id for r in [r for r in available if group(r) == g][:target])
    initial = tuple(sorted(selected))

    # Tags are scoped by risk/document so one provider/page category cannot hide another.
    def tags(row):
        return {f"{group(row)}:{row.doc_id}:{tag}" for tag in row.coverage_tags}

    required = set().union(*(tags(r) for r in results)) if results else set()
    covered = (
        set().union(*(tags(r) for r in available if r.section_id in selected))
        if selected
        else set()
    )
    expansion = {}
    while required - covered:
        remaining = [r for r in available if r.section_id not in selected]
        if not remaining:
            break
        # Greedy coverage with deterministic hash tie break, never silently dropping a stratum.
        best = min(remaining, key=lambda r: (-len(tags(r) - covered), order(r)))
        new = tags(best) - covered
        if not new:
            break
        selected.add(best.section_id)
        expansion[best.section_id] = tuple(sorted(new))
        covered |= tags(best)
    for row in available:
        if row.cohort in expansion_cohorts and row.section_id not in selected:
            selected.add(row.section_id)
            expansion[row.section_id] = ("defect_followup_census:" + row.cohort,)
            covered |= tags(row)
    return SamplePlan(
        validator_sha256=validator_fingerprint(),
        policy_sha256=fingerprint(policy),
        seed=policy.seed,
        role=role,
        excluded_ids=tuple(sorted(excluded)),
        initial_ids=initial,
        selected_ids=tuple(sorted(selected)),
        expansion=expansion,
        coverage_required=tuple(sorted(required)),
        coverage_missing=tuple(sorted(required - covered)),
    )
