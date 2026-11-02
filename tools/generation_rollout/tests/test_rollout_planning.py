"""Offline planning controls; no pipeline, provider or authorization consumption."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from tools.generation_rollout.planning import (
    authorization_template,
    partition,
    stage_plan,
    verify_partition,
)
from tools.generation_runner.plan import build_plan
from tools.generation_runner.runner import authorize, implementation
from tools.preflight_suite.artifacts import save, sha
from tools.quality_dashboard.artifacts import digest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def plans():
    full, _, _ = build_plan(ROOT)
    groups = partition([r['question_id'] for r in full['questions']])
    return {name: stage_plan(full, ids) for name, ids in groups.items()}


def test_partition_costs_and_calls(plans):
    verify_partition(plans)
    assert [len(p['questions']) for p in plans.values()] == [1, 4, 28]
    assert sum(Decimal(p['aggregate_cap_usd']) for p in plans.values()) == Decimal('0.76430900')
    for p in plans.values():
        assert p['plan_sha256'] == digest({k: v for k, v in p.items() if k != 'plan_sha256'})
        assert not p['generation_authorized']
        assert p['expected_future_calls']['retries'] == 0
        assert all(Decimal(q['maximum_cost_usd']) <= Decimal('.03') for q in p['questions'])


@pytest.mark.parametrize('stage', ['canary', 'pilot', 'remaining'])
def test_plan_matches_existing_builder(plans, stage):
    plan = plans[stage]
    actual, _, _ = build_plan(ROOT, selected=[q['question_id'] for q in plan['questions']],
                              aggregate_cap=plan['aggregate_cap_usd'])
    assert actual == plan


@pytest.mark.parametrize('stage', ['canary', 'pilot', 'remaining'])
def test_templates_rejected_without_markers(tmp_path, plans, stage):
    template = authorization_template(plans[stage], implementation(ROOT))
    path = tmp_path / 'workspace/template.json'
    save(path, template)
    with pytest.raises(ValueError):
        authorize(tmp_path, plans[stage], 'workspace/template.json', sha(path))
    assert not template['owner_statement']
    assert template['allow_paid_inference'] is False
    assert template['allow_source_transfer'] is False
    assert not list(tmp_path.rglob('*ATTEMPT*'))
    assert not (tmp_path / 'data').exists()


def test_stage_authorizations_are_distinct(plans):
    templates = [authorization_template(p, implementation(ROOT)) for p in plans.values()]
    assert len({digest(t) for t in templates}) == 3
    assert len({t['plan_sha256'] for t in templates}) == 3
    assert all(set(a['question_ids']).isdisjoint(b['question_ids'])
               for i, a in enumerate(templates) for b in templates[i+1:])


def test_duplicate_missing_or_completed_inventory_rejected(plans):
    ids = [q['question_id'] for p in plans.values() for q in p['questions']]
    for changed in [ids + [ids[0]], ids[:-1], ids[:-1] + ['M9-Q05'], ids[:-1] + [ids[0]]]:
        with pytest.raises(ValueError):
            partition(changed)


def test_overlapping_or_overbudget_stage_plans_rejected(plans):
    bad = deepcopy(plans)
    bad['remaining']['questions'][0] = bad['canary']['questions'][0]
    with pytest.raises(ValueError):
        verify_partition(bad)
    bad = deepcopy(plans)
    bad['remaining']['aggregate_cap_usd'] = '1.00'
    with pytest.raises(ValueError):
        verify_partition(bad)


def test_completed_question_and_underfunded_plan_fail_closed():
    with pytest.raises(ValueError):
        build_plan(ROOT, selected=['M9-Q05'])
    with pytest.raises(ValueError):
        build_plan(ROOT, selected=['M9-Q04'], aggregate_cap='.001')
