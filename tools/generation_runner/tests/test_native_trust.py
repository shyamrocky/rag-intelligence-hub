"""Native authorization-to-execution controls, exclusively disposable owned roots.

Synthetic attestations are unusable for the real benchmark. No real credentials,
source payloads, live markers or provider calls are permitted by this test module.
"""
import copy
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.generation_runner import runner, trust
from tools.preflight_suite.artifacts import now, save, sha
from tools.quality_dashboard.artifacts import ArtifactError, digest

ROOT = Path(__file__).resolve().parents[3]
CHECKER = 'workspace/rag-implementation/v1/q04-preservation-policy-v2/checker.py'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*a, **kw):
        pytest.fail('EXTERNAL_ACCESS_FORBIDDEN')
    for name in ('socket.socket.connect', 'socket.socket.connect_ex',
                 'socket.create_connection', 'socket.getaddrinfo'):
        monkeypatch.setattr(name, denied)
    monkeypatch.setattr('tools.preflight_suite.provider.load_key', denied)


@pytest.fixture
def owned(tmp_path, monkeypatch):
    from tools.preflight_suite import runner as preparation
    monkeypatch.setattr(preparation, 'completed_questions', lambda _: {'M9-Q05'})
    quality_files = [p.relative_to(ROOT).as_posix() for p in (ROOT / 'tools/answer_quality').glob('*')
                     if p.is_file() and p.suffix in {'.py', '.json'}]
    for name in [*quality_files, 'tools/generation_runner/runner.py', 'tools/generation_runner/live.py',
                 'tools/generation_runner/trust.py', 'tools/generation_trust_anchor.py', CHECKER]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    for name in ['owned/source.json', 'owned/M8.json', 'owned/M7.json', 'owned/request.json', 'owned/prompt.json',
                 'owned/model.json', 'owned/preflight.json', 'owned/Q05.json', 'owned/recovery.json']:
        write(tmp_path / name, {'owned': name})
    exceptions = []
    for name in ['.git/refs/codex/turn-diffs/captures/owned/base',
                 '.git/refs/codex/turn-diffs/checkpoints/owned/checkpoint']:
        exceptions.append({'path': name, 'expected_sha256': 'e' * 64})
    bindings = {p.relative_to(tmp_path).as_posix(): sha(p) for p in tmp_path.rglob('*') if p.is_file()
                and p.name != 'generation_trust_anchor.py'}
    critical = dict(bindings)
    bindings |= {e['path']: e['expected_sha256'] for e in exceptions}
    row = {'question_id': 'OWNED-NOT-BENCHMARK', 'per_question_cap_usd': '0.03',
           'maximum_cost_usd': '0.02', 'request_sha256': digest({'owned': True}),
           'M7_result_sha256': 'a' * 64, 'M8_package_sha256': 'b' * 64,
           'question_sha256': 'c' * 64, 'input_tokens': 100}
    plan = {'schema': 'grounded-generation-runner-1.0', 'questions': [row],
            'created_for_date': date.today().isoformat(),
            'preflight_sha256': 'd' * 64, 'preflight_manifest': 'owned/PREFLIGHT.json',
            'aggregate_cap_usd': '0.03', 'aggregate_maximum_estimated_cost_usd': '0.02',
            'model': 'owned-model', 'prompt_version': 'owned-prompt', 'response_schema': 'owned-schema',
            'expected_future_calls': {'model_metadata': 1, 'token_count': 1,
                                      'generation_maximum': 1, 'retries': 0}}
    plan['plan_sha256'] = digest(plan)
    policy = {'schema': 'generation-preservation-policy-3.0', 'generation_authority': False,
              'absence_exceptions': exceptions, 'historical_transient_audit_only': {},
              'closed_code_configuration_scopes': ['tools/generation_runner', 'tools/answer_quality'],
              'permitted_question_ids': ['OWNED-NOT-BENCHMARK'], 'model': 'owned-model',
              'prompt_version': 'owned-prompt', 'response_schema': 'owned-schema',
              'maximum_stage_cap_usd': '0.03', 'maximum_question_cap_usd': '0.03',
              'maximum_rollout_cap_usd': '1.00', 'request_bindings': trust.context(plan)['requests'],
              'approved_plan_contract_sha256': digest({k: v for k, v in plan.items()
                  if k not in {'plan_sha256', 'created_for_date'}})}
    base = tmp_path / 'data/owned-trust'
    for name, value in [('POLICY.json', policy), ('BASELINE_BINDINGS.json', bindings),
                        ('CRITICAL_BINDINGS.json', critical)]:
        write(base / name, value)
    manifest = {'schema': 'generation-trust-baseline-1.0',
                'files': {p.name: sha(p) for p in base.iterdir()},
                'checker': {'path': CHECKER, 'sha256': sha(tmp_path / CHECKER)}}
    write(base / 'MANIFEST.json', manifest)
    rel = 'data/owned-trust/MANIFEST.json'
    fingerprint = sha(base / 'MANIFEST.json')
    monkeypatch.setattr(trust, 'TRUSTED_BASELINES', {rel: fingerprint})
    data = SimpleNamespace(root=tmp_path, plan=plan, manifest=rel, sha=fingerprint, policy=policy)
    return data


def approve_owned(data):
    """Fixture-only mock consent. Never called with the actual project root/Q04."""
    assert data.root != ROOT and data.plan['questions'][0]['question_id'] == 'OWNED-NOT-BENCHMARK'
    folder = trust.prepare(data.root, data.plan, 'workspace/owned-preparation',
                           trust_manifest=data.manifest, trust_sha=data.sha)
    auth = json.loads((folder / 'AUTHORIZATION_TEMPLATE.json').read_bytes())
    auth.update(owner_statement='SYNTHETIC CONTROL ONLY; NOT OWNER APPROVAL FOR ANY REAL REQUEST',
        allow_paid_inference=True, allow_source_transfer=True,
        expires_at=(datetime.fromisoformat(now()) + timedelta(minutes=10)).isoformat())
    path = data.root / 'workspace/owned-attestation.json'
    write(path, auth)
    return auth, path.relative_to(data.root).as_posix(), sha(path)


def test_valid_native_authorization_and_two_audit_absences(owned):
    auth, path, h = approve_owned(owned)
    assert runner.authorize(owned.root, owned.plan, path, h) == auth
    receipt = json.loads((owned.root / auth['preservation_receipt']['path']).read_bytes())
    assert receipt['preservation']['known_transient_absences'] == 2
    assert receipt['preservation']['blocking_findings'] == 0
    assert not list(owned.root.rglob('LIVE_ATTEMPT.json'))


@pytest.mark.parametrize('name', ['owned/source.json', 'owned/M8.json', 'owned/M7.json', 'owned/request.json',
    'owned/prompt.json', 'owned/model.json', 'owned/preflight.json', 'owned/Q05.json',
    'owned/recovery.json', 'tools/generation_runner/runner.py', 'tools/generation_runner/trust.py',
    'tools/answer_quality/validator.py', 'tools/answer_quality/fidelity.py',
    'tools/answer_quality/review.py', 'tools/answer_quality/POLICY.json'])
def test_critical_changes_block_native_gate(owned, name):
    _, path, h = approve_owned(owned)
    (owned.root / name).write_text('tampered')
    with pytest.raises((ArtifactError, ValueError)):
        runner.authorize(owned.root, owned.plan, path, h)


@pytest.mark.parametrize('name', ['owned/source.json', 'owned/recovery.json', 'owned/Q05.json'])
def test_third_missing_protected_file_blocks(owned, name):
    _, path, h = approve_owned(owned)
    (owned.root / name).unlink()
    with pytest.raises(ArtifactError, match='PRESERVATION_BLOCKED'):
        runner.authorize(owned.root, owned.plan, path, h)


def test_reappearing_exception_wrong_content_blocks(owned):
    _, path, h = approve_owned(owned)
    p = owned.root / owned.policy['absence_exceptions'][0]['path']
    p.parent.mkdir(parents=True); p.write_text('different reference')
    with pytest.raises(ArtifactError):
        runner.authorize(owned.root, owned.plan, path, h)


def test_untrusted_self_consistent_policy_rejected(owned):
    folder = owned.root / 'data/evil'
    folder.mkdir(parents=True)
    write(folder / 'MANIFEST.json', {'schema': 'generation-trust-baseline-1.0', 'files': {}})
    with pytest.raises(ArtifactError, match='UNTRUSTED_BASELINE'):
        trust.preservation_receipt(owned.root, owned.plan, 'data/evil/MANIFEST.json', sha(folder / 'MANIFEST.json'))


@pytest.mark.parametrize('problem', ['missing', 'stale', 'future', 'wrong-plan', 'receipt-hash', 'auth-hash'])
def test_invalid_receipt_or_attestation(owned, problem):
    auth, path, h = approve_owned(owned)
    p = owned.root / auth['preservation_receipt']['path']
    r = json.loads(p.read_bytes())
    if problem == 'missing':
        p.unlink()
    elif problem == 'receipt-hash':
        p.write_text('{}')
    elif problem == 'auth-hash':
        (owned.root / path).write_text('{}')
    else:
        if problem == 'wrong-plan':
            r['context']['plan_sha256'] = 'f' * 64
        else:
            delta = timedelta(days=-1 if problem == 'stale' else 1)
            r['created_at'] = (datetime.fromisoformat(now()) + delta).isoformat()
        write(p, r); auth['preservation_receipt']['sha256'] = sha(p)
        write(owned.root / path, auth); h = sha(owned.root / path)
    with pytest.raises((ArtifactError, ValueError)):
        runner.authorize(owned.root, owned.plan, path, h)


@pytest.mark.parametrize('change', ['question', 'legacy', 'transfer', 'paid', 'single-use', 'implementation'])
def test_authorization_scope_and_legacy_bypass(owned, change):
    auth, path, _ = approve_owned(owned)
    if change == 'question': auth['question_ids'] = ['another']
    if change == 'legacy': auth['schema'] = 'grounded-generation-authorization-1.0'
    if change == 'transfer': auth['allow_source_transfer'] = False
    if change == 'paid': auth['allow_paid_inference'] = False
    if change == 'single-use': auth['maximum_generation_requests_per_question'] = 2
    if change == 'implementation': auth['implementation_bindings'] = {}
    write(owned.root / path, auth)
    with pytest.raises(ArtifactError):
        runner.authorize(owned.root, owned.plan, path, sha(owned.root / path))


@pytest.mark.parametrize('problem', ['start', 'orphan-attempt', 'consumed-approval'])
def test_prior_attempt_blocks_even_unsealed(owned, problem):
    _, path, h = approve_owned(owned)
    base = owned.root / 'data/evals/generation-runner'
    if problem == 'start':
        save(base / 'prior/PLAN.json', owned.plan)
        save(base / 'prior/START.json', {'mode': 'live'})
    elif problem == 'orphan-attempt':
        save(base / 'prior/questions/OWNED-NOT-BENCHMARK/LIVE_ATTEMPT.json', {})
    else:
        save(base / 'authorization-use/owned.json', {'run_id': 'prior', 'question_ids': ['OWNED-NOT-BENCHMARK']})
    with pytest.raises(ArtifactError):
        runner.authorize(owned.root, owned.plan, path, h)


@pytest.mark.parametrize('field,value', [('aggregate_cap_usd', '1.01'),
    ('aggregate_maximum_estimated_cost_usd', '.04'), ('per_question_cap_usd', '.04')])
def test_policy_cost_cap_blocks(owned, field, value):
    plan = copy.deepcopy(owned.plan)
    if field == 'per_question_cap_usd': plan['questions'][0][field] = value
    else: plan[field] = value
    plan['plan_sha256'] = digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
    with pytest.raises(ArtifactError):
        trust.preservation_receipt(owned.root, plan, owned.manifest, owned.sha)


def test_preparation_failure_never_emits_approval(owned, monkeypatch):
    def fail(*a, **kw):
        raise OSError('owned storage failure')
    monkeypatch.setattr(trust, 'save', fail)
    with pytest.raises(OSError):
        trust.prepare(owned.root, owned.plan, 'workspace/failure',
                      trust_manifest=owned.manifest, trust_sha=owned.sha)
    assert not list(owned.root.rglob('AUTHORIZATION_TEMPLATE.json'))
    assert not list(owned.root.rglob('*ATTEMPT.json'))


def test_runtime_guard_rechecks_integrity_after_admission(owned):
    auth, path, h = approve_owned(owned)
    runner.authorize(owned.root, owned.plan, path, h)
    trust.execution_guard(owned.root, owned.plan, auth, path, h)
    (owned.root / 'owned/M8.json').write_text('changed after admission')
    with pytest.raises(ArtifactError):
        trust.execution_guard(owned.root, owned.plan, auth, path, h)


@pytest.mark.parametrize('provider_failure', [False, True])
def test_native_execute_consumes_once_in_disposable_root(owned, monkeypatch, provider_failure):
    """Real _execute/authorize/locks/durable admission, mocked local boundaries only."""
    from tools.evidence import service as evidence_module
    from tools.generation_runner import live
    from tools.preflight_suite import runner as preparation
    _auth, path, h = approve_owned(owned)
    store = SimpleNamespace(verified={}, json=lambda _: {'owned': True})
    monkeypatch.setattr(runner, 'build_plan', lambda *a, **kw:
        (owned.plan, store, {'OWNED-NOT-BENCHMARK': {'question': 'Owned test?'}}))
    monkeypatch.setattr(runner, 'verify_bindings', lambda *a: None)
    monkeypatch.setattr(preparation, 'configuration', lambda *a, **kw: (SimpleNamespace(max_output_tokens=4096), None, None))
    class Evidence:
        def __init__(self, *a, **kw): self.files = {}
        def assemble(self, *a): return {'counts': {'selected_parents': 1}}
        def validate(self, *a): pass
        def check(self): pass
    monkeypatch.setattr(evidence_module, 'EvidenceService', Evidence)
    monkeypatch.setattr('tools.pre_generation_gate.current.PromptAssemblyGate', lambda *a: SimpleNamespace(prepare=lambda *a: None, validate_preparation=lambda *a: None))
    monkeypatch.setattr('tools.answer_quality.validator_abstention.PostGenerationValidator',
                        lambda *a: SimpleNamespace(validate=lambda *a, **kw: {'owned': True}))
    monkeypatch.setattr(preparation, 'assemble', lambda *a: ({'owned': True, 'counts': {'selected_parents': 1},
        'budget': {'exact_llm_evidence_tokens': 10}}, SimpleNamespace(audit={})))
    monkeypatch.setattr(preparation, 'recipe', lambda *a: ({'owned': True}, {'owned': True}))
    monkeypatch.setattr(preparation, 'equivalence', lambda *a: None)
    monkeypatch.setattr(preparation, 'source_transfer_check', lambda *a: None)
    calls = []
    class Adapter:
        def verify_model(self): pass
        def count(self): pass
        def invoke(self):
            calls.append('SYNTHETIC_GENERATION_ONLY')
    class Service:
        def __init__(self, gate, adapter, **kw): self.adapter = adapter
        def dry_run(self): pass
        def generate(self, *a, **kw):
            self.adapter.verify_model(); self.adapter.count(); self.adapter.invoke()
            return SimpleNamespace(response={'owned': True}, audit={'status': 'SYNTHETIC_VALID',
                'generation_executed': True, 'usage': {'cost_status': 'ESTIMATED_API_COST',
                'input_tokens': 100, 'output_tokens': 10, 'total_estimated_cost_usd': '0.001'}})
    monkeypatch.setattr('tools.generation.current.GenerationService', Service)
    def synthetic_create(*a, trust_guard, **kw):
        trust_guard()
        calls.append('MOCKED_PROVIDER_BOUNDARY_ONLY')
        if provider_failure:
            raise ValueError('SYNTHETIC_PROVIDER_FAILURE_NO_NETWORK')
        return Adapter(), None, None
    monkeypatch.setattr(live, 'create', synthetic_create)
    args = {'mode': 'live', 'selected': ['OWNED-NOT-BENCHMARK'], 'owner_authorization': path,
            'authorization_sha': h, 'execute_approved_live': True, 'progress': lambda *a, **kw: None}
    result = runner.execute(owned.root, **args)
    expected = ['MOCKED_PROVIDER_BOUNDARY_ONLY'] + ([] if provider_failure else ['SYNTHETIC_GENERATION_ONLY'])
    assert calls == expected
    row = json.loads((result / 'questions/OWNED-NOT-BENCHMARK/RESULT.json').read_bytes())
    assert row['status'] == ('BLOCKED_OR_FAILED' if provider_failure else 'SYNTHETIC_VALID')
    assert row['provider_calls'] == 0
    assert not list(owned.root.rglob('LIVE_ATTEMPT.json'))
    with pytest.raises(ArtifactError): runner.execute(owned.root, **args)
    assert calls == expected


def test_native_execution_rejects_legacy_before_consumption(owned, monkeypatch):
    _auth, path, _h = approve_owned(owned)
    auth = read_json_for_test(owned.root / path)
    auth['schema'] = 'grounded-generation-authorization-1.0'
    write(owned.root / path, auth)
    monkeypatch.setattr(runner, 'build_plan', lambda *a, **kw: (owned.plan, SimpleNamespace(verified={}), {}))
    with pytest.raises(ArtifactError):
        runner.execute(owned.root, mode='live', selected=['OWNED-NOT-BENCHMARK'],
            owner_authorization=path, authorization_sha=sha(owned.root / path), execute_approved_live=True)
    assert not list(owned.root.rglob('START.json'))
    assert not (owned.root / 'data/evals/generation-runner/authorization-use').exists()


def read_json_for_test(path):
    return json.loads(path.read_bytes())


def test_unsigned_preparation_is_rejected_by_actual_authorizer(owned):
    folder = trust.prepare(owned.root, owned.plan, 'workspace/unsigned',
                          trust_manifest=owned.manifest, trust_sha=owned.sha)
    with pytest.raises(ArtifactError):
        runner.authorize(owned.root, owned.plan, 'workspace/unsigned/AUTHORIZATION_TEMPLATE.json',
                         sha(folder / 'AUTHORIZATION_TEMPLATE.json'))
    assert not list(owned.root.rglob('*ATTEMPT.json'))


def test_legacy_unresolved_attempt_rejected(owned):
    _, path, h = approve_owned(owned)
    save(owned.root / 'data/evals/generation/old/GENERATION_ATTEMPT.json',
         {'question_id': 'OWNED-NOT-BENCHMARK', 'status': 'UNKNOWN'})
    with pytest.raises(ArtifactError, match='LEGACY_PRIOR_ATTEMPT'):
        runner.authorize(owned.root, owned.plan, path, h)


def test_cumulative_spending_reconciliation(owned):
    # Owned prior run on another fake question consumes a conservative .99 reservation.
    prior = copy.deepcopy(owned.plan)
    prior['questions'][0]['question_id'] = 'OWNED-PREVIOUS'
    prior['aggregate_maximum_estimated_cost_usd'] = '0.99'
    prior['plan_sha256'] = digest({k: v for k, v in prior.items() if k != 'plan_sha256'})
    folder = owned.root / 'data/evals/generation-runner/prior'
    save(folder / 'PLAN.json', prior)
    save(folder / 'START.json', {'mode': 'live'})
    with pytest.raises(ArtifactError, match='CROSS_RUN_COST_CAP'):
        trust.preservation_receipt(owned.root, owned.plan, owned.manifest, owned.sha)


def test_same_authorization_hash_change_blocked_at_inference_boundary(owned):
    auth, path, h = approve_owned(owned)
    runner.authorize(owned.root, owned.plan, path, h)
    (owned.root / path).write_text('{}')
    with pytest.raises(ArtifactError, match='OWNER_AUTHORIZATION_CHANGED'):
        trust.execution_guard(owned.root, owned.plan, auth, path, h)
