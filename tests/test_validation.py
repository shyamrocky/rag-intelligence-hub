"""Synthetic safety/regression tests for quality decisions; no corpus text included."""

import socket

import pytest
from pydantic import ValidationError

from rag_hub.acquire import Registry, digest
from rag_hub.content_validation import classify_all, load_input, validate_section
from rag_hub.pipeline import ingest
from rag_hub.validation_models import QualityReview, ValidationPolicy
from rag_hub.validation_pipeline import validate_content
from rag_hub.validation_reviews import cohort_gates, make_decisions
from rag_hub.validation_sampling import fingerprint, sample_sections


@pytest.fixture
def quality_input(tmp_path):
    data = b"# Example\n\nA complete independent explanation.\n\n```python\nvalue = 42\nprint(value)\n```\n"
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    (raw / "example.md").write_bytes(data)
    spec = {
        "doc_id": "C04",
        "file": "example.md",
        "byte_size": len(data),
        "sha256": digest(data),
        "title": "Synthetic",
        "publisher": "Tests",
        "canonical_url": "https://example.org/docs",
        "original_url": "https://example.org/docs.md",
        "source_version": None,
        "source_format": "markdown_mdx",
        "expected_pages": None,
        "language": "en",
    }
    registry = Registry(schema_version="0.1", sources=[spec])
    (tmp_path / "config").mkdir()
    (tmp_path / "config/sources.json").write_text(registry.model_dump_json())
    out = ingest(tmp_path, use_basis="synthetic fixture")
    directory = tmp_path / out["output"]
    policy = ValidationPolicy(
        input_run_id=out["run_id"],
        expected_hold_count=3,
        expected_original_approvals=0,
        artifact_sha256={p.name: digest(p.read_bytes()) for p in directory.iterdir()},
    )
    (tmp_path / "config/validation-policy.json").write_text(policy.model_dump_json())
    return load_input(tmp_path, policy), policy


def review_for(result, plan, policy, verdict=None, **kwargs):
    return QualityReview(
        section_id=result.section_id,
        raw_sha256=result.raw_sha256,
        normalized_sha256=result.normalized_sha256,
        policy_sha256=fingerprint(policy),
        sample_sha256=fingerprint(plan),
        role=plan.role,
        reviewer="synthetic-reviewer",
        method="source_comparison",
        evidence_note="Compared owned fixture and context",
        verdict=verdict or ("pass" if result.eligible_automatic else "confirmed_hold"),
        **kwargs,
    )


def test_qualified_low_source_promotes_only_after_review(quality_input):
    ctx, policy = quality_input
    rows = classify_all(ctx, policy)
    plan = sample_sections(rows, policy)
    gates, mapped = cohort_gates(rows, plan, policy, [])
    assert all(d.status == "hold" for d in make_decisions(rows, policy, gates, mapped))
    reviews = [review_for(r, plan, policy) for r in rows]
    gates, mapped = cohort_gates(rows, plan, policy, reviews)
    decisions = make_decisions(rows, policy, gates, mapped)
    assert sum(d.basis == "deterministic_source_match" for d in decisions) == 2
    assert next(d for d in decisions if d.section_id == rows[0].section_id).status == "hold"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"raw_sha256": "b" * 64}, "lineage_mismatch"),
        ({"snapshot_id": "wrong"}, "lineage_mismatch"),
        ({"block_ids": ("missing",)}, "missing_or_multiple_parent_blocks"),
        ({"normalized_sha256": "b" * 64}, "normalized_hash_mismatch"),
        ({"provider_tab": "Other"}, "block_metadata_mismatch"),
        ({"heading_path": ("Wrong",)}, "block_metadata_mismatch"),
    ],
)
def test_section_tampering_fails_closed(quality_input, change, reason):
    ctx, p = quality_input
    s = ctx.sections[1].model_copy(update=change)
    r = validate_section(s, ctx, p)
    assert reason in r.reasons and not r.eligible_automatic and r.blocking_integrity


def test_raw_source_and_normalized_body_independently_verified(quality_input):
    ctx, p = quality_input
    s = ctx.sections[1]
    b = ctx.blocks[s.block_ids[0]]
    text = "A changed sentence.\n"
    ctx.blocks[b.block_id] = b.model_copy(
        update={"content": text, "content_sha256": digest(text.encode())}
    )
    changed = s.model_copy(update={"text": text, "normalized_sha256": digest(text.encode())})
    result = validate_section(changed, ctx, p)
    assert "raw_source_body_mismatch" in result.reasons


def test_code_audit_required(quality_input):
    ctx, p = quality_input
    s = ctx.sections[-1]
    ctx.audit.clear()
    assert "missing_audit" in validate_section(s, ctx, p).reasons


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("provider_tab", "fake", "provider_mismatch"),
        ("code_group", "fake", "code_group_mismatch"),
        ("fence_info", "bash", "fence_metadata_mismatch"),
        ("content", "print(9)\n", "raw_source_body_mismatch"),
    ],
)
def test_independent_code_metadata_check(quality_input, field, value, reason):
    ctx, p = quality_input
    s = ctx.sections[-1]
    b = ctx.blocks[s.block_ids[0]]
    ctx.blocks[b.block_id] = b.model_copy(update={field: value})
    result = validate_section(s, ctx, p)
    assert reason in result.reasons and not result.eligible_automatic


def test_medium_risk_never_auto_promotes(quality_input):
    ctx, p = quality_input
    row = classify_all(ctx, p)[1]
    medium = row.model_copy(
        update={
            "risk": "medium",
            "eligible_automatic": False,
            "reasons": ("pdf_visual_layout_review_required",),
        }
    )
    plan = sample_sections([medium], p)
    gates, mapped = cohort_gates([medium], plan, p, [review_for(medium, plan, p, "pass")])
    assert make_decisions([medium], p, gates, mapped)[0].status == "hold"


def test_manual_medium_requires_explicit_receipt_and_resolved_context(quality_input):
    ctx, p = quality_input
    row = classify_all(ctx, p)[1]
    medium = row.model_copy(
        update={
            "risk": "medium",
            "eligible_automatic": False,
            "reasons": ("pdf_visual_layout_review_required",),
        }
    )
    plan = sample_sections([medium], p)
    review = review_for(medium, plan, p, "pass", manual_approval=True).model_copy(
        update={"method": "visual_source_comparison"}
    )
    gates, mapped = cohort_gates([medium], plan, p, [review])
    assert make_decisions([medium], p, gates, mapped)[0].basis == "visual_manual_review"
    bad = medium.model_copy(update={"reasons": ("incomplete_or_list_context",)})
    with pytest.raises(ValueError, match="override"):
        cohort_gates([bad], plan, p, [review])


@pytest.mark.parametrize(
    "issue",
    [
        "corrupted_or_fragmented_glyphs",
        "unverified_table",
        "unsupported_mdx_or_html",
        "new_unknown_issue",
    ],
)
def test_hazards_and_unknown_issues_never_promote(quality_input, issue):
    ctx, p = quality_input
    s = ctx.sections[1].model_copy(update={"issues": (issue,)})
    row = validate_section(s, ctx, p)
    assert row.risk == "high" and not row.eligible_automatic


def test_unknown_policy_version_rejected(quality_input):
    with pytest.raises(ValidationError):
        ValidationPolicy.model_validate(quality_input[1].model_dump() | {"version": "unknown"})


@pytest.mark.parametrize(
    "update",
    [
        {"policy_sha256": "stale"},
        {"sample_sha256": "stale"},
        {"raw_sha256": "b" * 64},
        {"role": "calibration"},
    ],
)
def test_stale_review_rejected(quality_input, update):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    plan = sample_sections(rows, p)
    receipt = review_for(rows[1], plan, p).model_copy(update=update)
    with pytest.raises(ValueError, match="stale"):
        cohort_gates(rows, plan, p, [receipt])


def test_duplicate_reviews_rejected(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    plan = sample_sections(rows, p)
    receipt = review_for(rows[1], plan, p)
    with pytest.raises(ValueError, match="duplicate"):
        cohort_gates(rows, plan, p, [receipt, receipt])


def test_sampling_adapts_for_coverage_and_is_deterministic(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    extra = [
        rows[1].model_copy(update={"section_id": f"s{i}", "coverage_tags": ("provider:" + str(i),)})
        for i in range(60)
    ]
    plan = sample_sections(extra, p)
    assert len(plan.initial_ids) == 45 and len(plan.selected_ids) == 60
    assert not plan.coverage_missing and plan == sample_sections(list(reversed(extra)), p)


def test_disjoint_acceptance_and_unavailable_coverage_block(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    initial = sample_sections(rows, p, role="calibration")
    acceptance = sample_sections(rows, p, excluded_ids=initial.selected_ids)
    assert not set(initial.selected_ids) & set(acceptance.selected_ids)
    assert acceptance.coverage_missing
    gates, _ = cohort_gates(rows, acceptance, p, [])
    assert all(not g["qualified"] for g in gates.values())


def test_calibration_cannot_qualify(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    plan = sample_sections(rows, p, role="calibration")
    reviews = [review_for(r, plan, p) for r in rows]
    gates, _ = cohort_gates(rows, plan, p, reviews)
    assert all(not v["qualified"] for v in gates.values())


def test_systematic_defect_blocks_whole_cohort_and_expands_review(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    candidates = [rows[1].model_copy(update={"section_id": f"s{i}"}) for i in range(70)]
    plan = sample_sections(candidates, p)
    expanded = sample_sections(candidates, p, expansion_cohorts=(candidates[0].cohort,))
    assert len(expanded.selected_ids) == 70
    reviews = [
        review_for(r, plan, p, "defect" if r.section_id == plan.selected_ids[0] else "pass")
        for r in candidates
        if r.section_id in plan.selected_ids
    ]
    gates, mapped = cohort_gates(candidates, plan, p, reviews)
    assert all(d.status == "hold" for d in make_decisions(candidates, p, gates, mapped))


def test_missing_review_blocks_unreviewed_neighbors(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    plan = sample_sections(rows, p)
    gates, mapped = cohort_gates(rows, plan, p, [review_for(rows[1], plan, p)])
    assert all(d.status == "hold" for d in make_decisions(rows, p, gates, mapped))


def test_immutable_inputs_and_outputs_and_no_network(quality_input, monkeypatch):
    ctx, p = quality_input

    def forbidden(*args, **kwargs):
        raise AssertionError("network is not allowed")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    before = {
        f: digest((ctx.root / "data/ingestion" / p.input_run_id / f).read_bytes())
        for f in p.artifact_sha256
    }
    a = validate_content(ctx.root)
    b = validate_content(ctx.root)
    assert a == b
    assert before == {
        f: digest((ctx.root / "data/ingestion" / p.input_run_id / f).read_bytes())
        for f in p.artifact_sha256
    }
    output = ctx.root / a["output"] / "report.json"
    output.write_text("changed")
    with pytest.raises(ValueError, match="immutable validation"):
        validate_content(ctx.root)
    (ctx.root / "data/ingestion" / p.input_run_id / "reviews.json").write_text("changed")
    with pytest.raises(ValueError, match="artifact mismatch"):
        load_input(ctx.root, p)


def test_earlier_use_not_satisfied_by_later_binding(quality_input):
    from rag_hub.source_fidelity import contextual_reasons

    ctx, _ = quality_input
    b = ctx.blocks[ctx.sections[-1].block_ids[0]]
    bad = b.model_copy(update={"content": "value = value + 1\n"})
    assert "code_requires_external_bindings" in contextual_reasons(ctx.sections[-1], bad)


@pytest.mark.parametrize("text", ["x = y + z.", "P(x) = 0.7.", "A table | --- | number"])
def test_hidden_math_or_table_in_prose_held(quality_input, text):
    ctx, p = quality_input
    s = ctx.sections[1].model_copy(
        update={"text": text, "normalized_sha256": digest(text.encode())}
    )
    r = validate_section(s, ctx, p)
    assert "concealed_math_or_table" in r.reasons and r.risk == "high" and not r.eligible_automatic


def test_manifest_cannot_be_forged_by_setting_candidate_flag(quality_input):
    ctx, p = quality_input
    r = classify_all(ctx, p)[1]
    medium = r.model_copy(update={"risk": "medium", "eligible_automatic": True})
    gates = {medium.cohort: {"qualified": True, "blockers": []}}
    assert make_decisions([medium], p, gates, {})[0].status == "hold"


def test_manual_hold_cannot_be_overridden_by_batch_promotion(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    plan = sample_sections(rows, p)
    reviews = [review_for(r, plan, p) for r in rows]
    reviews[1] = reviews[1].model_copy(update={"verdict": "confirmed_hold"})
    gates, mapped = cohort_gates(rows, plan, p, reviews)
    decision = make_decisions(rows, p, gates, mapped)[1]
    assert decision.status == "hold"
    assert not gates[rows[1].cohort]["qualified"]


def test_stale_validator_fingerprint_rejected(quality_input):
    ctx, p = quality_input
    rows = classify_all(ctx, p)
    plan = sample_sections(rows, p)
    with pytest.raises(ValueError, match="stale"):
        cohort_gates(rows, plan.model_copy(update={"validator_sha256": "stale"}), p, [])
