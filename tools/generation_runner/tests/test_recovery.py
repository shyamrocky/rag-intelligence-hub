"""Native recovery admission in disposable roots only. No real approval or provider."""
import copy
import json
import shutil
from decimal import Decimal

import pytest
from test_native_trust import write
from test_stage_policies import (
    fake_pipeline,
    rehash,
    run_synthetic,
    synthetic_approval,
)
from test_stage_policies import (
    owned as owned,  # noqa: PLC0414
)
from test_stage_policies import (
    stages as stages,  # noqa: PLC0414
)

from tools.generation_runner import recovery, runner, trust
from tools.preflight_suite.artifacts import sha
from tools.quality_dashboard.artifacts import ArtifactError, digest


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def denied(*a, **kw):
        pytest.fail('RECOVERY_TESTS_HAVE_NO_PROVIDER_OR_REAL_CREDENTIAL_ACCESS')
    for name in ('socket.create_connection', 'socket.socket.connect',
                 'socket.socket.connect_ex', 'socket.getaddrinfo',
                 'tools.preflight_suite.provider.load_key'):
        monkeypatch.setattr(name, denied)


def seal_parent(s):
    folder = s.root / 'data/evals/generation-runner/owned-parent'
    mpath = folder / 'MANIFEST.json'
    m = json.loads(mpath.read_bytes())
    m['files'] = {p.relative_to(folder).as_posix(): sha(p)
                  for p in folder.rglob('*') if p.is_file() and p != mpath}
    write(mpath, m)
    s.policy['native_recovery']['parent_manifest']['sha256'] = sha(mpath)


def publish_policy(s, monkeypatch):
    base = s.root / s.manifest
    write(base.parent / 'POLICY.json', s.policy)
    m = json.loads(base.read_bytes())
    m['files'] = {p.name: sha(p) for p in base.parent.iterdir() if p.is_file() and p != base}
    write(base, m)
    s.sha = sha(base)
    monkeypatch.setattr(trust, 'TRUSTED_BASELINES', {s.manifest: s.sha})


@pytest.fixture
def recovered(stages, monkeypatch):
    s = stages['pilot']
    original = copy.deepcopy(s.plan)
    ids = [r['question_id'] for r in original['questions']]
    base = s.root / 'data/evals/generation-runner/owned-parent'
    auth_sha = 'a' * 64
    write(base / 'PLAN.json', original)
    write(base / 'START.json', {'mode': 'live', 'generation_authorized': True,
                              'authorization_sha256': auth_sha})
    rows = []
    for i, q in enumerate(original['questions'][:2]):
        qid = q['question_id']
        row = copy.deepcopy(q) | {'generation_executed': True, 'source_integrity': 'LIVE_M8_VALIDATED',
            'status': 'VALID' if i == 0 else 'INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE',
            'response': {'synthetic': True} if i == 0 else None,
            'audit': {'generation_executed': True, 'response_status': 'completed',
                'usage': {'usage_status': 'MEASURED_API_USAGE', 'cost_status': 'ESTIMATED_API_COST',
                          'model': original['model'], 'input_tokens': q['input_tokens'],
                          'total_estimated_cost_usd': '0.001', 'usage_errors': [], 'cost_reasons': []}}}
        write(base / f'questions/{qid}/RESULT.json', row)
        write(base / f'questions/{qid}/LIVE_ATTEMPT.json', {'question_id': qid, 'mode': 'live',
              'request_sha256': q['request_sha256']})
        write(base / f'questions/{qid}/GENERATION_HTTP_ATTEMPT.json', {'method': 'POST',
              'endpoint': '/v1/responses', 'request_sha256': q['request_sha256']})
        rows.append(row)
    write(base / 'RESULTS.json', {'mode': 'live', 'questions': rows})
    write(base / 'MANIFEST.json', {'schema': 'grounded-generation-runner-1.0', 'mode': 'live',
        'run_id': 'owned-parent', 'status': 'SEALED_PENDING_OWNER_REVIEW', 'generation_authorized': True,
        'authorization_sha256': auth_sha, 'question_ids': ids[:2],
        'plan_sha256': original['plan_sha256'], 'files': {}})
    use = s.root / f'data/evals/generation-runner/authorization-use/{auth_sha}.json'
    write(use, {'run_id': 'owned-parent', 'authorization_sha256': auth_sha, 'question_ids': ids})
    s.plan = copy.deepcopy(original)
    s.plan['questions'] = s.plan['questions'][1:]
    s.plan.update(aggregate_cap_usd='0.09', aggregate_maximum_estimated_cost_usd='0.06',
        expected_future_calls={'model_metadata': 3, 'token_count': 3, 'generation_maximum': 3, 'retries': 0})
    rehash(s.plan)
    ctx = trust.context(s.plan)
    s.policy.update(permitted_question_ids=ids[1:], maximum_stage_cap_usd='0.09',
        request_bindings=ctx['requests'], approved_plan_contract_sha256=digest({k: v for k, v in s.plan.items()
            if k not in {'plan_sha256', 'created_for_date'}}),
        native_recovery={'schema': recovery.SCHEMA,
            'parent_manifest': {'path': (base / 'MANIFEST.json').relative_to(s.root).as_posix(), 'sha256': ''},
            'parent_authorization_use': {'path': use.relative_to(s.root).as_posix(), 'sha256': sha(use)},
            'question_ids': ids[1:], 'requests': ctx['requests'],
            'dispositions': {q: recovery.RETRY if q == ids[1] else recovery.CONTINUE for q in ids[1:]},
            'maximum_additional_requests_per_question': 1, 'automatic_retries': 0,
            'excluded_question_ids': ids[:1], 'owner_permission_record': 'SYNTHETIC ONLY NOT REAL OWNER CONSENT'})
    target = s.root / 'tools/generation_runner/recovery.py'
    shutil.copyfile(recovery.__file__, target)
    for name in ('BASELINE_BINDINGS.json', 'CRITICAL_BINDINGS.json'):
        p = (s.root / s.manifest).parent / name
        value = json.loads(p.read_bytes())
        value[target.relative_to(s.root).as_posix()] = sha(target)
        write(p, value)
    seal_parent(s)
    publish_policy(s, monkeypatch)
    return s


def test_actual_authorizer_recovery_preserves_full_original_reservation(recovered):
    s = recovered
    path, h = synthetic_approval(s, 'owned-recovery')
    auth = runner.authorize(s.root, s.plan, path, h)
    receipt = json.loads((s.root / auth['preservation_receipt']['path']).read_bytes())
    assert receipt['history']['reserved_native_usd'] == '0.08'
    assert receipt['history']['explicit_recovery']['reservation_released_usd'] == '0'
    assert Decimal('0.08') + Decimal(s.plan['aggregate_maximum_estimated_cost_usd']) == Decimal('0.14')
    with pytest.raises(ArtifactError, match='PRIOR_LIVE_RUN'):
        trust.history(s.root, auth['question_ids'])  # Ordinary paths still cannot bypass history.


@pytest.mark.parametrize('failure', [False, True])
def test_actual_native_recovery_runs_once_and_stops_on_invalid_output(recovered, monkeypatch, failure):
    s = recovered
    parent = s.root / s.policy['native_recovery']['parent_manifest']['path']
    before = sha(parent)
    path, h = synthetic_approval(s, 'owned-native-recovery')
    calls = fake_pipeline(monkeypatch, s, failure=failure)
    run = run_synthetic(s, path, h)
    result = json.loads((run / 'RESULTS.json').read_bytes())
    assert result['selected'] == 3 and result['completed'] == (1 if failure else 3)
    assert len(calls) == result['completed'] and sha(parent) == before
    with pytest.raises(ArtifactError):
        run_synthetic(s, path, h)
    assert len(calls) == result['completed']
    assert list(s.root.rglob('LIVE_ATTEMPT.json'))  # Parent owned attempts retained.


@pytest.mark.parametrize('change', ['reorder', 'q17', 'other', 'request', 'retry-count', 'scope'])
def test_contract_must_match_exact_reviewed_scope(recovered, change):
    contract = copy.deepcopy(recovered.policy['native_recovery'])
    ids = list(contract['question_ids'])
    if change == 'reorder': ids.reverse()
    elif change == 'q17': ids[0] = contract['excluded_question_ids'][0]
    elif change == 'other': ids[0] = 'OWNED-OTHER'
    elif change == 'request': contract['requests'][ids[0]]['request_sha256'] = 'f' * 64
    elif change == 'retry-count': contract['maximum_additional_requests_per_question'] = 2
    else: contract['wildcard_history_waiver'] = True
    with pytest.raises(ArtifactError):
        recovery.validate_scope(contract, ids, trust.context(recovered.plan)['requests'])


@pytest.mark.parametrize('change', ['unknown-billing', 'valid-prior-answer', 'attempted-continuation',
                                  'parent-tamper', 'use-tamper', 'new-prior-run', 'unsealed-parent-file'])
def test_recovery_never_waives_other_integrity_or_history_failures(recovered, monkeypatch, change):
    s = recovered
    base = s.root / 'data/evals/generation-runner/owned-parent'
    qid = s.plan['questions'][0]['question_id']
    if change in {'unknown-billing', 'valid-prior-answer'}:
        result = json.loads((base / 'RESULTS.json').read_bytes())
        row = result['questions'][1]
        if change == 'unknown-billing': row['audit']['usage']['cost_status'] = 'COST_UNAVAILABLE'
        else: row['response'] = {'owned': True}
        write(base / 'RESULTS.json', result)
        write(base / f'questions/{qid}/RESULT.json', row)
        seal_parent(s)
        publish_policy(s, monkeypatch)
    elif change in {'attempted-continuation', 'unsealed-parent-file'}:
        name = f'questions/{s.plan["questions"][1]["question_id"]}/LIVE_ATTEMPT.json' if change == 'attempted-continuation' else 'UNSEALED.json'
        write(base / name, {})
    elif change == 'parent-tamper': write(base / 'START.json', {})
    elif change == 'use-tamper': write(s.root / s.policy['native_recovery']['parent_authorization_use']['path'], {})
    else:
        new = s.root / 'data/evals/generation-runner/another-run'
        write(new / 'PLAN.json', s.plan)
        write(new / 'START.json', {'mode': 'live'})
    with pytest.raises(ArtifactError):
        synthetic_approval(s, 'must-not-approve')
    assert not (s.root / 'workspace/must-not-approve').exists()


@pytest.mark.parametrize('change', ['individual', 'aggregate', 'rollout'])
def test_recovery_preserves_all_cost_caps(recovered, monkeypatch, change):
    s = recovered
    if change == 'individual': s.plan['questions'][0]['per_question_cap_usd'] = '0.04'
    elif change == 'aggregate': s.plan['aggregate_cap_usd'] = '0.13'
    else: s.policy['maximum_rollout_cap_usd'] = '0.10'
    rehash(s.plan)
    publish_policy(s, monkeypatch)
    with pytest.raises(ArtifactError): synthetic_approval(s, 'cost-blocked')
