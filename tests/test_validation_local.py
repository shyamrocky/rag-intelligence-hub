"""Historical exact replay and current-validator fail-closed compatibility are distinct."""

import json
from pathlib import Path

import pytest
from historical_replay import replay_reviews

from rag_hub.content_validation import classify_all, load_input
from rag_hub.validation_models import QualityReview, ValidationPolicy
from rag_hub.validation_reviews import review_map
from rag_hub.validation_sampling import fingerprint, sample_sections

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = "workspace/milestone2.5-review/reviews.json"


@pytest.mark.skipif(
    not (ROOT / REVIEWS).exists(), reason="private completed review evidence not provided"
)
def test_actual_1665_coverage_promotion_boundaries_and_preservation():
    assert "PASS: archived validator" in replay_reviews()


@pytest.mark.skipif(
    not (ROOT / REVIEWS).exists(), reason="private completed review evidence not provided"
)
def test_current_validator_rejects_historical_reviews_without_new_authority():
    policy = ValidationPolicy.model_validate_json((ROOT / "config/validation-policy.json").read_bytes())
    results = classify_all(load_input(ROOT, policy), policy)
    plan = sample_sections(results, policy, expansion_cohorts=["C04:prose"])
    reviews = [QualityReview.model_validate(r) for r in json.loads((ROOT / REVIEWS).read_bytes())]
    assert len(results) == 1665 and len(reviews) == 195
    assert all(r.sample_sha256 != fingerprint(plan) for r in reviews)
    with pytest.raises(ValueError, match="^stale quality review evidence$"):
        review_map(results, plan, policy, reviews)
    # No new observations, signatures, decisions or publication are fabricated.
