"""Optional full-corpus quality acceptance regression; data/reviews stay private."""

import json
from collections import Counter
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.content_validation import classify_all, load_input
from rag_hub.validation_models import ValidationPolicy
from rag_hub.validation_pipeline import validate_content

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = "workspace/milestone2.5-review/reviews.json"


@pytest.mark.skipif(
    not (ROOT / REVIEWS).exists(), reason="private completed review evidence not provided"
)
def test_actual_1665_coverage_promotion_boundaries_and_preservation():
    p = ValidationPolicy.model_validate_json((ROOT / "config/validation-policy.json").read_text())
    before = {
        f: digest((ROOT / "data/ingestion" / p.input_run_id / f).read_bytes())
        for f in p.artifact_sha256
    }
    ctx = load_input(ROOT, p)
    results = classify_all(ctx, p)
    assert len(results) == 1665
    assert Counter(r.doc_id for r in results) == {"C01": 407, "C04": 154, "C06": 1104}
    first = validate_content(ROOT, reviews_path=REVIEWS, expansion_cohorts=["C04:prose"])
    directory = ROOT / first["output"]
    hashes = {f.name: digest(f.read_bytes()) for f in directory.iterdir()}
    second = validate_content(ROOT, reviews_path=REVIEWS, expansion_cohorts=["C04:prose"])
    assert first == second and hashes == {
        f.name: digest(f.read_bytes()) for f in directory.iterdir()
    }
    assert before == {
        f: digest((ROOT / "data/ingestion" / p.input_run_id / f).read_bytes())
        for f in p.artifact_sha256
    }
    report = json.loads((directory / "report.json").read_text())
    assert report["sample"]["reviewed"] == 195 and report["sample"]["expanded"] == 195
    assert report["sample"]["verdicts"] == {"pass": 27, "confirmed_hold": 167, "defect": 1}
    assert report["approved_total"] == 40 and report["remaining_hold_total"] == 1634
    approved = json.loads((directory / "approved_manifest.json").read_text())["approved"]
    auto = [r for r in approved if r["basis"] == "deterministic_source_match"]
    sections = {s.section_id: s for s in ctx.sections}
    assert len(auto) == 38 and all(r["doc_id"] == "C04" and r["risk"] == "low" for r in auto)
    assert all(sections[r["section_id"]].block_type == "code" for r in auto)
    assert report["original_receipts_preserved"] == 9
    assert report["original_approvals_suspended_for_new_manifest"] == 7
    assert not report["cohort_gates"]["C04:prose"]["qualified"]
