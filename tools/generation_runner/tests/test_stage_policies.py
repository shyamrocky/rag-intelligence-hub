"""Two-stage native trust tests. Approvals exist ONLY in disposable synthetic roots.

Real benchmark policies are read-only. No provider boundary or real owner approval
is reachable; all source, prompt and service work in execution tests is synthetic.
"""
import copy
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_native_trust import owned as owned  # noqa: PLC0414 - pytest fixture re-export
from test_native_trust import write

from tools.generation_runner import runner, trust
from tools.preflight_suite.artifacts import now, save, sha
from tools.quality_dashboard.artifacts import ArtifactError, digest

ROOT = Path(__file__).resolve().parents[3]
RELEASE = 'data/evals/generation-runner-reviews/two-stage-preparation-v1'


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('PROVIDER_OR_CREDENTIAL_ACCESS_FORBIDDEN')
    for name in ('socket.socket.connect', 'socket.socket.connect_ex',
                 'socket.create_connection', 'socket.getaddrinfo',
                 'tools.preflight_suite.provider.load_key'):
        monkeypatch.setattr(name, denied)


def rehash(plan):
    plan['plan_sha256'] = digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
    return plan


@pytest.fixture
def stages(owned, monkeypatch):
    """Extend the existing native fixture, without accepting benchmark authorizations."""
    entries = {}
    plans = {}
    for stage, count, cap in [('pilot', 4, '0.12'), ('remaining', 28, '0.88')]:
        plan = copy.deepcopy(owned.plan)
        plan['questions'] = []
        for i in range(count):
            row = copy.deepcopy(owned.plan['questions'][0])
            row['question_id'] = f'OWNED-{stage.upper()}-{i:02d}'
            row['request_sha256'] = digest({'stage': stage, 'index': i})
            plan['questions'].append(row)
        plan['aggregate_cap_usd'] = cap
        plan['aggregate_maximum_estimated_cost_usd'] = str(Decimal('0.02') * count)
        plan['expected_future_calls'] = {'model_metadata': count, 'token_count': count,
                                        'generation_maximum': count, 'retries': 0}
        rehash(plan)
        policy = copy.deepcopy(owned.policy)
        policy.update(permitted_question_ids=[q['question_id'] for q in plan['questions']],
            request_bindings=trust.context(plan)['requests'], maximum_stage_cap_usd=cap,
            approved_plan_contract_sha256=digest({k: v for k, v in plan.items()
                if k not in {'plan_sha256', 'created_for_date'}}))
        folder = owned.root / f'data/{stage}-trust'
        parent = owned.root / owned.manifest
        manifest = json.loads(parent.read_bytes())
        for name in ('BASELINE_BINDINGS.json', 'CRITICAL_BINDINGS.json'):
            write(folder / name, json.loads((parent.parent / name).read_bytes()))
        write(folder / 'POLICY.json', policy)
        manifest['files'] = {p.name: sha(p) for p in folder.iterdir()}
        write(folder / 'MANIFEST.json', manifest)
        reference = (folder / 'MANIFEST.json').relative_to(owned.root).as_posix()
        entries[reference] = sha(folder / 'MANIFEST.json')
        plans[stage] = SimpleNamespace(root=owned.root, plan=plan, manifest=reference,
                                      sha=entries[reference], policy=policy)
    monkeypatch.setattr(trust, 'TRUSTED_BASELINES', entries)
    return plans


def synthetic_approval(stage, name):
    assert stage.root != ROOT
    assert all(q['question_id'].startswith('OWNED-') for q in stage.plan['questions'])
    folder = trust.prepare(stage.root, stage.plan, f'workspace/{name}',
                           trust_manifest=stage.manifest, trust_sha=stage.sha)
    auth = json.loads((folder / 'AUTHORIZATION_TEMPLATE.json').read_bytes())
    auth.update(owner_statement='SYNTHETIC FIXTURE; NO REAL OWNER CONSENT',
                allow_paid_inference=True, allow_source_transfer=True,
                expires_at=(datetime.fromisoformat(now()) + timedelta(minutes=10)).isoformat())
    path = f'workspace/{name}/SYNTHETIC_ATTESTATION.json'
    write(stage.root / path, auth)
    return path, sha(stage.root / path)


@pytest.mark.parametrize('stage', ['pilot', 'remaining'])
def test_native_stage_authorization_and_no_unsigned_permission(stages, stage):
    s = stages[stage]
    folder = trust.prepare(s.root, s.plan, 'workspace/unsigned',
                           trust_manifest=s.manifest, trust_sha=s.sha)
    with pytest.raises(ArtifactError, match='EXPLICIT_CURRENT_OWNER'):
        runner.authorize(s.root, s.plan, 'workspace/unsigned/AUTHORIZATION_TEMPLATE.json',
                         sha(folder / 'AUTHORIZATION_TEMPLATE.json'))
    path, h = synthetic_approval(s, 'explicit-fixture')
    auth = runner.authorize(s.root, s.plan, path, h)
    trust.execution_guard(s.root, s.plan, auth, path, h)
    assert len(auth['question_ids']) == (4 if stage == 'pilot' else 28)


@pytest.mark.parametrize('stage', ['pilot', 'remaining'])
@pytest.mark.parametrize('alter', ['Q04', 'Q05', 'other-stage', 'subset', 'reorder',
                                  'cap', 'request', 'source', 'retries', 'model'])
def test_exact_scope_request_and_budget_binding(stages, stage, alter):
    s = stages[stage]
    p = copy.deepcopy(s.plan)
    if alter in {'Q04', 'Q05'}:
        p['questions'][0]['question_id'] = 'M9-' + alter
    elif alter == 'other-stage':
        p['questions'][0] = stages['remaining' if stage == 'pilot' else 'pilot'].plan['questions'][0]
    elif alter == 'subset':
        p['questions'].pop()
    elif alter == 'reorder':
        p['questions'].reverse()
    elif alter == 'cap':
        p['aggregate_cap_usd'] = '0.13' if stage == 'pilot' else '0.89'
    elif alter == 'request':
        p['questions'][0]['request_sha256'] = 'f' * 64
    elif alter == 'source':
        p['questions'][0]['M8_package_sha256'] = 'f' * 64
    elif alter == 'retries':
        p['expected_future_calls']['retries'] = 1
    else:
        p['model'] = 'fallback-forbidden'
    with pytest.raises(ArtifactError):
        trust.preservation_receipt(s.root, rehash(p), s.manifest, s.sha)


def test_cross_stage_authorization_cannot_transfer(stages):
    p, r = stages['pilot'], stages['remaining']
    path, h = synthetic_approval(p, 'pilot-only')
    with pytest.raises(ArtifactError, match='EXPLICIT_CURRENT_OWNER'):
        runner.authorize(r.root, r.plan, path, h)
    with pytest.raises(ArtifactError, match='TRUST_POLICY_PLAN_SCOPE_MISMATCH'):
        trust.preservation_receipt(r.root, r.plan, p.manifest, p.sha)
    assert not list(r.root.rglob('START.json'))


@pytest.mark.parametrize('stage', ['pilot', 'remaining'])
@pytest.mark.parametrize('change', ['manifest', 'policy', 'source', 'request', 'runner'])
def test_tampering_blocks_actual_authorizer(stages, stage, change):
    s = stages[stage]
    path, h = synthetic_approval(s, 'before-tampering')
    target = {'manifest': s.manifest,
              'policy': s.manifest.rsplit('/', 1)[0] + '/POLICY.json',
              'source': 'owned/source.json', 'request': 'owned/request.json',
              'runner': 'tools/generation_runner/runner.py'}[change]
    (s.root / target).write_text('tampered')
    with pytest.raises(ArtifactError):
        runner.authorize(s.root, s.plan, path, h)


def fake_pipeline(monkeypatch, s, failure=False):
    """Keep native authorize/guard/admission/history intact; replace data and provider."""
    from tools.evidence import service as evidence_module
    from tools.generation_runner import live
    from tools.preflight_suite import runner as preparation

    calls = []
    store = SimpleNamespace(verified={}, json=lambda _: {})
    inventory = {q['question_id']: {'question': 'Synthetic control?'} for q in s.plan['questions']}
    monkeypatch.setattr(runner, 'build_plan', lambda *a, **kw: (s.plan, store, inventory))
    monkeypatch.setattr(runner, 'verify_bindings', lambda *a: None)
    monkeypatch.setattr(preparation, 'configuration', lambda *a, **kw:
                        (SimpleNamespace(max_output_tokens=4096, model=s.plan['model']), None, None))

    class Evidence:
        def __init__(self, *a, **kw): self.files = {}
        def assemble(self, *a): return {}
        def validate(self, *a): pass
        def check(self): pass

    monkeypatch.setattr(evidence_module, 'EvidenceService', Evidence)
    monkeypatch.setattr('tools.pre_generation_gate.current.PromptAssemblyGate', lambda *a:
        SimpleNamespace(prepare=lambda *a: None, validate_preparation=lambda *a: None))
    monkeypatch.setattr('tools.answer_quality.validator_abstention.PostGenerationValidator', lambda *a:
        SimpleNamespace(validate=lambda *a, **kw: {'status': 'REVIEW_REQUIRED'}))
    monkeypatch.setattr(preparation, 'assemble', lambda *a: (
        {'counts': {'selected_parents': 1}, 'budget': {'exact_llm_evidence_tokens': 10}},
        SimpleNamespace(audit={})))
    monkeypatch.setattr(preparation, 'recipe', lambda *a: ({}, {}))
    monkeypatch.setattr(preparation, 'equivalence', lambda *a: None)
    monkeypatch.setattr(preparation, 'source_transfer_check', lambda *a: None)

    class Adapter:
        def verify_model(self): pass
        def count(self): pass
        def invoke(self): pass

    def create(*a, trust_guard, **kw):
        trust_guard()
        from tools.generation.response_capture import ResponseCapture
        root, qdir, _request, row = a[:4]
        adapter = Adapter()
        adapter.row = row
        adapter.capture = ResponseCapture(root, qdir, question_id=row['question_id'], run_id=qdir.parent.parent.name,
            request_sha256=row['request_sha256'], package_sha256=row['M8_package_sha256'], mode='live')
        return adapter, None, None

    class Service:
        def __init__(self, gate, adapter, **kw): self.adapter = adapter
        def dry_run(self): pass
        def generate(self, *a, **kw):
            calls.append('SYNTHETIC_SERVICE_NO_PROVIDER')
            row = self.adapter.row
            capture = self.adapter.capture.capture(b'Owned fixture provider body', http_status=200)
            return SimpleNamespace(response=None if failure else {'synthetic': True},
                audit={'status': 'SYNTHETIC_CONTROL', 'generation_executed': not failure,
                       'model': s.plan['model'], 'response_status': 'completed',
                       'request_sha256': row['request_sha256'], 'M8_package_sha256': row['M8_package_sha256'],
                       'raw_response_capture': capture,
                       'usage': {'cost_status': 'COST_UNAVAILABLE' if failure else 'ESTIMATED_API_COST',
                                 'input_tokens': 100, 'output_tokens': 10, 'total_tokens': 110,
                                 'total_estimated_cost_usd': '0.001'}})

    monkeypatch.setattr(live, 'create', create)
    monkeypatch.setattr('tools.generation.current.GenerationService', Service)
    return calls


def run_synthetic(s, path, h):
    assert s.root != ROOT
    return runner.execute(s.root, mode='live', selected=[q['question_id'] for q in s.plan['questions']],
        owner_authorization=path, authorization_sha=h, execute_approved_live=True,
        progress=lambda *a, **kw: None)


@pytest.mark.parametrize('failure', [False, True])
def test_two_stage_native_execution_and_partial_stop(stages, monkeypatch, failure):
    p, r = stages['pilot'], stages['remaining']
    path, h = synthetic_approval(p, 'pilot-fixture')
    calls = fake_pipeline(monkeypatch, p, failure=failure)
    result = run_synthetic(p, path, h)
    values = json.loads((result / 'RESULTS.json').read_bytes())
    assert values['completed'] == (1 if failure else 4)
    assert len(calls) == values['completed']
    assert not list(p.root.rglob('LIVE_ATTEMPT.json'))
    assert trust.history(r.root, [q['question_id'] for q in r.plan['questions']])['reserved_native_usd'] == '0.08'
    with pytest.raises(ArtifactError):
        run_synthetic(p, path, h)
    fake_pipeline(monkeypatch, r)
    # Even a completed pilot cannot confer permission for the remaining stage.
    with pytest.raises(ArtifactError):
        run_synthetic(r, path, h)
    assert len(list(p.root.glob('data/evals/generation-runner/*/START.json'))) == 1
    if not failure:
        path2, h2 = synthetic_approval(r, 'separate-remaining-fixture')
        result2 = run_synthetic(r, path2, h2)
        assert json.loads((result2 / 'RESULTS.json').read_bytes())['completed'] == 28
        assert len(list(p.root.glob('data/evals/generation-runner/authorization-use/*.json'))) == 2


def test_cumulative_cap_retains_full_prior_reservations(stages):
    s = stages['remaining']
    prior = copy.deepcopy(stages['pilot'].plan)
    prior['aggregate_maximum_estimated_cost_usd'] = '0.90'
    rehash(prior)
    base = s.root / 'data/evals/generation-runner/prior'
    save(base / 'PLAN.json', prior)
    save(base / 'START.json', {'mode': 'live'})
    with pytest.raises(ArtifactError, match='CROSS_RUN_COST_CAP_EXCEEDED'):
        trust.preservation_receipt(s.root, s.plan, s.manifest, s.sha)


def test_real_sealed_successors_are_disjoint_and_preserved():
    plans = {}
    for stage, version, count, cap in [('pilot', 25, 4, '0.12'), ('remaining', 26, 28, '0.88')]:
        reference = f'data/evals/generation-trust/v{version}/MANIFEST.json'
        m, policy, result = trust.load_trust(ROOT, reference, trust.TRUSTED_BASELINES[reference])
        plan = json.loads((ROOT / RELEASE / stage / 'PLAN_NOT_AUTHORIZED.json').read_bytes())
        plan['created_for_date'] = date.today().isoformat()
        rehash(plan)
        ctx = trust.verify_plan_policy(plan, policy)
        assert len(ctx['question_ids']) == count
        assert policy['maximum_stage_cap_usd'] == cap
        assert policy['maximum_rollout_cap_usd'] == '1.00'
        assert result['blocking_findings'] == 0 and result['known_transient_absences'] == 2
        assert m['generation_authority'] is False
        if stage == 'pilot':
            with pytest.raises(ArtifactError, match='PRIOR_LIVE_RUN_OR_UNRESOLVED_ATTEMPT'):
                trust.history(ROOT, ctx['question_ids'])
        else:
            trust.history(ROOT, ctx['question_ids'])
        plans[stage] = plan
    a, b = ({q['question_id'] for q in p['questions']} for p in plans.values())
    assert not a & b and not (a | b) & {'M9-Q04', 'M9-Q05'}
    assert len(a | b | {'M9-Q04', 'M9-Q05'}) == 34
    projected = sum(Decimal(p['aggregate_maximum_estimated_cost_usd']) for p in plans.values())
    assert projected + Decimal('0.02355575') == Decimal('0.76430900')
