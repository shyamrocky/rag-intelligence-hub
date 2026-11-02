"""Strict saved input checks; no provider calls, credentials or source assembly."""
from pathlib import Path

import pytest

from tools.generation_runner.plan import build_plan
from tools.quality_dashboard.artifacts import digest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def plan():
    return build_plan(ROOT)[0]


def test_all33_exact_inventory_cost_and_calls(plan):
    assert len(plan['questions']) == 33
    assert 'M9-Q05' not in {q['question_id'] for q in plan['questions']}
    assert plan['aggregate_maximum_estimated_cost_usd'] == '0.76430900'
    assert plan['aggregate_cap_usd'] == '1.00'
    assert plan['expected_future_calls'] == {'model_metadata': 33, 'token_count': 33,
                                              'generation_maximum': 33, 'retries': 0}
    assert plan['plan_sha256'] == digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
    assert not plan['generation_authorized']
    assert sum(q['input_tokens'] for q in plan['questions']) == 2786900
    assert {c: sum(q['cohort_id'] == c for q in plan['questions']) for c in 'ABCD'} == {'A': 9, 'B': 5, 'C': 16, 'D': 3}


def test_deterministic_plan(plan):
    assert build_plan(ROOT)[0] == plan


@pytest.mark.parametrize('kwargs', [{'selected': ['M9-Q05']}, {'selected': ['R01', 'R01']},
                                    {'selected': ['unknown']}, {'aggregate_cap': '.5'},
                                    {'per_question_cap': '.001'}])
def test_selection_and_budget_fail_closed(kwargs):
    with pytest.raises(ValueError):
        build_plan(ROOT, **kwargs)


def test_selected_cohort_excludes_previously_generated():
    # Original Difficult contains Q05; it must be excluded explicitly for cohort execution too.
    a, _, _ = build_plan(ROOT, cohorts=['A'])
    assert len(a['questions']) == 9
    p, _, _ = build_plan(ROOT, cohorts=['B'])
    assert [q['question_id'] for q in p['questions']] == ['R01', 'R02', 'R03', 'R04', 'R05']


def test_live_authorization_rejected_without_consuming_anything(tmp_path, plan):
    from tools.generation_runner.runner import authorize
    from tools.preflight_suite.artifacts import save, sha
    auth = tmp_path / 'workspace/owner.json'
    save(auth, {'schema': 'grounded-generation-authorization-1.0', 'expires_at': '2000-01-01T00:00:00+00:00'})
    with pytest.raises(ValueError):
        authorize(tmp_path, plan, 'workspace/owner.json', sha(auth))
    assert not list(tmp_path.rglob('*ATTEMPT*'))


def test_stale_pricing_or_model_profile_blocks():
    from datetime import date
    with pytest.raises(ValueError):
        build_plan(ROOT, as_of=date(2030, 1, 1))
