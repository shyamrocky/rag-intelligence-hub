"""Partition existing runner plans, without new inference or authorization machinery."""
from copy import deepcopy
from decimal import Decimal

from tools.quality_dashboard.artifacts import digest

CANARY = ['M9-Q04']
PILOT = ['M9-Q01', 'M9-Q09', 'M9-Q27', 'R03']  # Existing runner sorts exact IDs.


def partition(ids):
    ids = list(ids)
    if len(ids) != 33 or len(set(ids)) != 33 or 'M9-Q05' in ids:
        raise ValueError('EXPECTED_33_UNIQUE_PENDING_QUESTIONS')
    if not set(CANARY + PILOT) <= set(ids):
        raise ValueError('REQUIRED_ROLLOUT_QUESTIONS_MISSING')
    return {'canary': CANARY[:], 'pilot': PILOT[:],
            'remaining': sorted(set(ids) - set(CANARY + PILOT))}


def stage_plan(full, ids):
    """Exact build_plan-equivalent subset; fixed stage caps also bound cumulative spend."""
    plan = deepcopy(full)
    plan.pop('plan_sha256')
    plan['questions'] = [q for q in plan['questions'] if q['question_id'] in ids]
    if [q['question_id'] for q in plan['questions']] != sorted(ids):
        raise ValueError('STAGE_QUESTION_ORDER_MISMATCH')
    total = sum((Decimal(q['maximum_cost_usd']) for q in plan['questions']), Decimal(0))
    if total > Decimal('1.00') or any(Decimal(q['maximum_cost_usd']) > Decimal('0.03')
                                      for q in plan['questions']):
        raise ValueError('ROLLOUT_SPENDING_LIMIT_EXCEEDED')
    plan['aggregate_cap_usd'] = plan['aggregate_maximum_estimated_cost_usd'] = str(total)
    plan['expected_future_calls'] = {'model_metadata': len(ids), 'token_count': len(ids),
                                     'generation_maximum': len(ids), 'retries': 0}
    plan['plan_sha256'] = digest(plan)
    return plan


def authorization_template(plan, bindings):
    """Intentionally rejected by existing authorize(): no approval, expiry or permissions."""
    return {'schema': 'grounded-generation-authorization-1.0',
            'plan_sha256': plan['plan_sha256'], 'preflight_sha256': plan['preflight_sha256'],
            'question_ids': [q['question_id'] for q in plan['questions']],
            'implementation_bindings': bindings,
            'aggregate_cap_usd': plan['aggregate_cap_usd'],
            'per_question_caps_usd': {q['question_id']: q['per_question_cap_usd']
                                      for q in plan['questions']},
            'allow_paid_inference': False, 'allow_source_transfer': False,
            'maximum_generation_requests_per_question': 1,
            'expires_at': '1970-01-01T00:00:00+00:00', 'owner_statement': ''}


def verify_partition(plans):
    groups = [[q['question_id'] for q in p['questions']] for p in plans.values()]
    ids = [q for group in groups for q in group]
    if (list(map(len, groups)) != [1, 4, 28] or len(set(ids + ['M9-Q05'])) != 34
            or sum((Decimal(p['aggregate_cap_usd']) for p in plans.values()), Decimal(0))
            > Decimal('1.00')):
        raise ValueError('ROLLOUT_RECONCILIATION_OR_CAP_FAILED')
