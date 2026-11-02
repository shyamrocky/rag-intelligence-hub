"""Actual deployment successor and immutable Q04/Q05 records, read-only."""
import json
from pathlib import Path

from tools.generation_runner.trust import load_trust
from tools.generation_trust_anchor import TRUSTED_BASELINES
from tools.quality_dashboard.artifacts import Store, read_json, sha

ROOT = Path(__file__).resolve().parents[3]


def test_successor_preserves_review_contract_without_review_generation_authority():
    path = max(TRUSTED_BASELINES, key=lambda name: int(name.split('/')[-2][1:]))
    _manifest, policy, result = load_trust(ROOT, path, TRUSTED_BASELINES[path])
    assert result['blocking_findings'] == 0 and result['known_transient_absences'] == 2
    # v6's review-only release did not expand generation scope. Separately reviewed
    # pilot/remaining successors may change scope, never human-review authority.
    historical = read_json(ROOT / 'data/evals/generation-trust/v6/POLICY.json')
    assert historical['permitted_question_ids'] == ['M9-Q04']
    assert policy['human_review_contract'] == historical['human_review_contract']
    assert policy['local_poc_review'] == historical['local_poc_review']
    assert not policy['generation_authority']
    assert policy['human_review_contract']['grants_generation_authority'] is False
    assert policy['local_poc_review']['generation_authority'] is False
    critical = read_json(ROOT / path.rsplit('/', 1)[0] / 'CRITICAL_BINDINGS.json')
    assert critical['tools/human_review/identity.py'] == sha(ROOT / 'tools/human_review/identity.py')
    assert critical['tools/answer_quality/review.py'] == sha(ROOT / 'tools/answer_quality/review.py')
    assert len(policy['absence_exceptions']) == 2


def test_original_q04_q05_and_owner_decisions_unchanged():
    expected = {
        'data/evals/generation-runner/20261029T080808-live-143c62d120f7/MANIFEST.json':
            '5672e13e710d38f84bd97c3c994d2892ffe9b000723c663a58e3e978419c1038',
        'data/evals/generation/live-q05-funded-v1/MANIFEST.json':
            '3077d9d502dfdab16791ce85f2b1ab432ef8c0e8f39e2f5874dce36c279297f8',
        'data/evals/generation-runner-reviews/q04-owner-review-eligibility-v1/MANIFEST.json':
            'e4813843f869f329e1eccaaa6dda3b6b867e4926dab126aa6e22665aecdfd0d6'}
    for name, fingerprint in expected.items():
        Store(ROOT).manifest(name, expected=fingerprint)
    row = json.loads((ROOT / 'data/evals/generation-runner/20261029T080808-live-143c62d120f7/questions/M9-Q04/RESULT.json').read_bytes())
    assert row['post_validation']['overall_status'] == 'FAILED'



def test_actual_q04_packages_are_one_approved_target():
    from tools.human_review import local_poc
    from tools.human_review.review_state import current_decision, group_packages, package_history
    values = [p for p in package_history(ROOT) if p[1]['question_id'] == 'M9-Q04']
    groups = group_packages(values)
    assert len(values) >= 2 and len(groups) == 1
    current = groups[0][-1]
    assert current[1]['created_at'] == max(p[1]['created_at'] for p in values)
    history, rejected = local_poc.discover(ROOT)
    assert not rejected
    decision, path = current_decision(current[1], history)
    assert decision['status'] == 'OWNER_APPROVED_POC'
    assert path == 'data/evals/human-review/local-poc/poc-b1743fe6e42a41ea8a7c07d56804222c/MANIFEST.json'
    assert not decision['authenticated'] and not decision['fully_validated']
