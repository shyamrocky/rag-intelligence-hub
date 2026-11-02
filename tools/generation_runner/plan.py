"""Source-free execution planning against strictly verified preflight publications."""
from datetime import date
from decimal import Decimal
from pathlib import Path

from tools.preflight_suite.artifacts import baseline, read_run, sha
from tools.quality_dashboard.artifacts import ArtifactError, digest

PREFLIGHT = 'data/evals/preflight-suite/20261028T162022-model-preflight-b436659c001f/MANIFEST.json'
PREFLIGHT_SHA = 'd16eef36608c293e5f19384fec03fe2307e8c4738ad97f14ff7942180f2ab352'
BASE = 'data/evals/generation-runner'
VERSION = 'grounded-generation-runner-1.0'


def money(value):
    if not isinstance(value, str):
        raise TypeError('COST_MUST_BE_DECIMAL_STRING')
    result = Decimal(value)
    if not result.is_finite() or result <= 0:
        raise ValueError('COST_MUST_BE_FINITE_POSITIVE')
    return result


def build_plan(root, *, selected=None, cohorts=None, preflight=PREFLIGHT,
               per_question_cap='0.03', aggregate_cap='1.00', as_of=None):
    if preflight and preflight.startswith('data/runtime-qualifications/v1/'):
        from .bot_source import build_plan as bot_plan
        return bot_plan(root, selected=selected, cohorts=cohorts, preflight=preflight,
                        per_question_cap=per_question_cap, aggregate_cap=aggregate_cap, as_of=as_of)
    # All imports that could depend on the generator runtime stay out of dashboard imports.
    from tools.generation.profiles import check_fit
    from tools.generation.telemetry import estimate_max_cost
    from tools.preflight_suite.runner import completed_questions, configuration, select

    root = Path(root)
    store, inventory = baseline(root)
    if preflight == PREFLIGHT and sha(root / preflight) != PREFLIGHT_SHA:
        raise ArtifactError('PINNED_PREFLIGHT_CHANGED')
    manifest, values, verified = read_run(root, preflight)
    if manifest['mode'] != 'model-preflight':
        raise ArtifactError('MODEL_PREFLIGHT_REQUIRED')
    done = completed_questions(root) | {'M9-Q05'}
    ids = select(inventory, ids=selected, cohorts=cohorts, completed=done,
                 pending=selected is None and cohorts is None)
    if selected is not None and set(ids) & done:
        raise ValueError('ALREADY_GENERATED_QUESTION_EXCLUDED')
    ids = [q for q in ids if q not in done]
    if not ids:
        raise ValueError('EMPTY_PENDING_SELECTION')
    day = as_of or date.today()
    settings, profile, pricing = configuration(root, day=day)
    per_cap, total_cap = money(per_question_cap), money(aggregate_cap)
    rows = {r['question_id']: r for r in values['questions']}
    base = preflight.rsplit('/', 1)[0]
    questions = []
    for qid in ids:
        r = rows.get(qid)
        if not r or r['status'] != 'MODEL_QUALIFIED':
            raise ArtifactError('SELECTED_QUESTION_NOT_MODEL_QUALIFIED')
        request = verified.json(base + f'/questions/{qid}/REQUEST_PACKAGE.json')
        model = verified.json(base + f'/questions/{qid}/MODEL_PREFLIGHT.json')
        if (request['settings_sha256'] != digest(settings.model_dump())
                or request['profile_sha256'] != digest(profile)):
            raise ArtifactError('CURRENT_MODEL_OR_SETTINGS_CHANGED')
        fit = check_fit(profile, settings, r['input_tokens'])
        cost = estimate_max_cost(settings.model, r['input_tokens'], settings.max_output_tokens,
                                 pricing, tier=settings.service_tier, region=settings.region, as_of=day)
        if (not fit['fits'] or cost['status'] != 'ESTIMATED_MAX_API_COST'
                or cost != model['cost_estimate']):
            raise ArtifactError('CONTEXT_OR_CURRENT_PRICE_CHANGED_REPREFLIGHT_REQUIRED')
        maximum = money(cost['estimated_max_cost_usd'])
        if maximum > per_cap:
            raise ValueError('PER_QUESTION_COST_CAP_EXCEEDED')
        questions.append({'question_id': qid, 'cohort_id': inventory[qid]['cohort_id'],
                          'question_sha256': inventory[qid]['question_sha256'],
                          'request_sha256': request['request_sha256'],
                          'M8_package_sha256': request['M8_package_sha256'],
                          'M7_result_sha256': request['M7_result_sha256'],
                          'input_tokens': r['input_tokens'], 'context_fit': fit,
                          'maximum_cost_usd': str(maximum),
                          'per_question_cap_usd': str(per_cap),
                          'readiness': 'SEALED_PREFLIGHT_VERIFIED_FRESH_EXECUTION_CHECKS_REQUIRED'})
    total = sum((money(q['maximum_cost_usd']) for q in questions), Decimal(0))
    if total > total_cap:
        raise ValueError('AGGREGATE_ESTIMATED_COST_CAP_EXCEEDED')
    plan = {'schema': VERSION, 'preflight_manifest': preflight,
            'preflight_sha256': sha(root / preflight), 'created_for_date': day.isoformat(),
            'questions': questions, 'model': settings.model, 'prompt_version': settings.prompt_version,
            'response_schema': settings.response_schema, 'pricing_version': pricing['version'],
            'settings_sha256': digest(settings.model_dump()), 'profile_sha256': digest(profile),
            'pricing_sha256': digest(pricing), 'aggregate_cap_usd': str(total_cap),
            'aggregate_maximum_estimated_cost_usd': str(total),
            'expected_future_calls': {'model_metadata': len(ids), 'token_count': len(ids),
                                      'generation_maximum': len(ids), 'retries': 0},
            'generation_authorized': False, 'Q05_excluded': True,
            'evidence_completeness_used_for_selection': False}
    plan['plan_sha256'] = digest(plan)
    store.verified.update(verified.verified)
    return plan, store, inventory
