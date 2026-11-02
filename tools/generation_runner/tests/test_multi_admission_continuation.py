"""Exact multi-admission continuation, synthetic roots/providers only."""
import copy
import json
from decimal import Decimal

import pytest
from test_native_trust import write
from test_recovery import publish_policy
from test_recovery import recovered as recovered  # noqa: PLC0414
from test_stage_policies import fake_pipeline, rehash, run_synthetic, synthetic_approval
from test_stage_policies import owned as owned  # noqa: PLC0414
from test_stage_policies import stages as stages  # noqa: PLC0414

from tools.generation_runner import recovery, runner, trust
from tools.preflight_suite.artifacts import sha
from tools.quality_dashboard.artifacts import ArtifactError, digest


@pytest.fixture
def continuation(recovered, monkeypatch):
    s = recovered
    original = s.policy['native_recovery']
    folder = s.root / 'data/evals/generation-runner/owned-second'
    prior = json.loads((s.root / original['parent_manifest']['path']).read_bytes())
    first_base = (s.root / original['parent_manifest']['path']).parent
    second_plan = copy.deepcopy(s.plan)
    qid = second_plan['questions'][0]['question_id']
    row = json.loads((first_base / f'questions/{qid}/RESULT.json').read_bytes())
    auth = 'b' * 64
    write(folder / 'PLAN.json', second_plan)
    write(folder / 'START.json', {'mode': 'live', 'generation_authorized': True, 'authorization_sha256': auth})
    write(folder / 'RESULTS.json', {'mode': 'live', 'questions': [row]})
    for name in ('RESULT.json', 'LIVE_ATTEMPT.json', 'GENERATION_HTTP_ATTEMPT.json'):
        write(folder / f'questions/{qid}/{name}', json.loads((first_base / f'questions/{qid}/{name}').read_bytes()))
    m = prior | {'run_id': folder.name, 'authorization_sha256': auth, 'question_ids': [qid],
                 'plan_sha256': second_plan['plan_sha256']}
    m['files'] = {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}
    write(folder / 'MANIFEST.json', m)
    use = s.root / f'data/evals/generation-runner/authorization-use/{auth}.json'
    write(use, {'run_id': folder.name, 'authorization_sha256': auth,
                'question_ids': [q['question_id'] for q in second_plan['questions']]})
    s.plan['questions'] = s.plan['questions'][1:]
    s.plan.update(aggregate_cap_usd='0.06', aggregate_maximum_estimated_cost_usd='0.04',
        expected_future_calls={'model_metadata': 2, 'token_count': 2, 'generation_maximum': 2, 'retries': 0})
    rehash(s.plan)
    ids = [q['question_id'] for q in s.plan['questions']]
    contract = {k: v for k, v in original.items() if k not in {'parent_manifest', 'parent_authorization_use'}}
    contract.update(schema=recovery.CONTINUATION_SCHEMA, question_ids=ids,
        requests=trust.context(s.plan)['requests'], dispositions={q: recovery.CONTINUE for q in ids},
        parents=[{'parent_manifest': original['parent_manifest'], 'parent_authorization_use': original['parent_authorization_use']},
                 {'parent_manifest': {'path': (folder / 'MANIFEST.json').relative_to(s.root).as_posix(),
                                      'sha256': sha(folder / 'MANIFEST.json')},
                  'parent_authorization_use': {'path': use.relative_to(s.root).as_posix(), 'sha256': sha(use)}}])
    s.policy.update(native_recovery=contract, permitted_question_ids=ids, maximum_stage_cap_usd='0.06',
        request_bindings=trust.context(s.plan)['requests'],
        approved_plan_contract_sha256=digest({k: v for k, v in s.plan.items() if k not in {'plan_sha256', 'created_for_date'}}))
    publish_policy(s, monkeypatch)
    return s


def rebind_parent(s, index):
    reference = s.policy['native_recovery']['parents'][index]['parent_manifest']
    file = s.root / reference['path']
    m = json.loads(file.read_bytes())
    m['files'] = {p.relative_to(file.parent).as_posix(): sha(p) for p in file.parent.rglob('*') if p.is_file() and p != file}
    write(file, m); reference['sha256'] = sha(file)


def test_actual_native_authorizer_accepts_two_parents_without_releasing_reservations(continuation):
    s = continuation
    path, h = synthetic_approval(s, 'two-parent-owned')
    auth = runner.authorize(s.root, s.plan, path, h)
    value = json.loads((s.root / auth['preservation_receipt']['path']).read_bytes())
    assert value['history']['reserved_native_usd'] == '0.14'
    assert Decimal(value['history']['reserved_native_usd']) + Decimal(s.plan['aggregate_maximum_estimated_cost_usd']) == Decimal('0.18')
    recovery_record = value['history']['explicit_recovery']
    assert recovery_record['parent_run_ids'] == ['owned-parent', 'owned-second']
    assert recovery_record['reservation_released_usd'] == '0'
    with pytest.raises(ArtifactError): trust.history(s.root, auth['question_ids'])


@pytest.mark.parametrize('failure', [False, True])
def test_native_execution_uses_only_two_ids_then_cannot_repeat(continuation, monkeypatch, failure):
    s = continuation
    parents = {ref['parent_manifest']['path']: ref['parent_manifest']['sha256']
               for ref in s.policy['native_recovery']['parents']}
    path, h = synthetic_approval(s, 'two-parent-execution-owned')
    calls = fake_pipeline(monkeypatch, s, failure=failure)
    run = run_synthetic(s, path, h)
    result = json.loads((run / 'RESULTS.json').read_bytes())
    assert result['selected'] == 2 and result['completed'] == (1 if failure else 2)
    assert len(calls) == result['completed']
    assert all(sha(s.root / p) == expected for p, expected in parents.items())
    with pytest.raises(ArtifactError): run_synthetic(s, path, h)
    assert len(calls) == result['completed']


@pytest.mark.parametrize('change', ['duplicate', 'reverse', 'omit', 'retry', 'unknown-key', 'bad-hash', 'reuse-use'])
def test_invalid_multi_parent_contracts_fail_closed(continuation, change):
    s = continuation
    c = copy.deepcopy(s.policy['native_recovery'])
    if change == 'duplicate': c['parents'].append(copy.deepcopy(c['parents'][0]))
    elif change == 'reverse': c['parents'].reverse()
    elif change == 'omit': c['parents'].pop()
    elif change == 'retry': c['dispositions'][c['question_ids'][0]] = recovery.RETRY
    elif change == 'unknown-key': c['history_waiver'] = True
    elif change == 'bad-hash': c['parents'][0]['parent_manifest']['sha256'] = None
    else: c['parents'][1]['parent_authorization_use'] = c['parents'][0]['parent_authorization_use']
    with pytest.raises(ArtifactError): recovery.validate_scope(c, c['question_ids'])


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('change', ['unknown-billing', 'attempted-question', 'source-binding', 'use-tamper', 'parent-tamper'])
def test_each_parent_is_authenticated_and_selected_questions_were_never_attempted(continuation, monkeypatch, index, change):
    s = continuation; ref = s.policy['native_recovery']['parents'][index]
    folder = (s.root / ref['parent_manifest']['path']).parent
    if change == 'unknown-billing':
        result = json.loads((folder / 'RESULTS.json').read_bytes())
        row = result['questions'][0]; row['audit']['usage']['cost_status'] = 'COST_UNAVAILABLE'
        write(folder / 'RESULTS.json', result); write(folder / f'questions/{row["question_id"]}/RESULT.json', row)
        rebind_parent(s, index)
    elif change == 'attempted-question':
        write(folder / f'questions/{s.plan["questions"][0]["question_id"]}/LIVE_ATTEMPT.json', {})
        rebind_parent(s, index)
    elif change == 'source-binding':
        p = json.loads((folder / 'PLAN.json').read_bytes())
        next(q for q in p['questions'] if q['question_id'] == s.plan['questions'][0]['question_id'])['M8_package_sha256'] = 'e'*64
        rehash(p); write(folder / 'PLAN.json', p); rebind_parent(s, index)
    elif change == 'use-tamper': write(s.root / ref['parent_authorization_use']['path'], {})
    else: write(folder / 'START.json', {})
    publish_policy(s, monkeypatch)
    with pytest.raises(ArtifactError): synthetic_approval(s, 'must-not-approve')
    assert not (s.root / 'workspace/must-not-approve').exists()


def test_third_admission_is_not_waived(continuation):
    s = continuation
    folder = s.root / 'data/evals/generation-runner/owned-third'
    write(folder / 'PLAN.json', s.plan); write(folder / 'START.json', {'mode': 'live'})
    with pytest.raises(ArtifactError, match='PRIOR_LIVE_RUN'):
        synthetic_approval(s, 'third-is-blocked')


@pytest.mark.parametrize('change', ['individual', 'aggregate', 'rollout', 'wrong-id'])
def test_scope_and_all_spending_guards_still_apply(continuation, monkeypatch, change):
    s = continuation
    if change == 'individual': s.plan['questions'][0]['per_question_cap_usd'] = '0.04'
    elif change == 'aggregate': s.plan['aggregate_cap_usd'] = '0.07'
    elif change == 'wrong-id': s.plan['questions'][0]['question_id'] = s.policy['native_recovery']['excluded_question_ids'][0]
    else: s.policy['maximum_rollout_cap_usd'] = '0.15'
    rehash(s.plan); publish_policy(s, monkeypatch)
    with pytest.raises(ArtifactError): synthetic_approval(s, 'cap-scope-blocked')
