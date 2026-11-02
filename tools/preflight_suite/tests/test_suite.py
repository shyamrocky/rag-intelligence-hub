"""Synthetic controls and existing sealed contracts; never live provider requests."""
import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from tools.generation.current import load_settings
from tools.generation.profiles import check_fit
from tools.generation.telemetry import estimate_max_cost, load_pricing
from tools.pre_generation_gate.contract import digest
from tools.preflight_suite import artifacts, runner
from tools.preflight_suite.__main__ import main
from tools.preflight_suite.artifacts import create_run, save
from tools.preflight_suite.provider import CountOnlyAdapter, CountOnlyTransport
from tools.quality_dashboard.artifacts import ArtifactError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def inputs():
    return artifacts.baseline(ROOT)


def test_frozen_inventory_and_pending(inputs):
    _, rows = inputs
    completed = runner.completed_questions(ROOT)
    selected = runner.select(rows, pending=True, completed=completed)
    assert completed == {'M9-Q05'}
    assert len(selected) == 33 and 'M9-Q05' not in selected
    assert {r['cohort_id'] for r in rows.values()} == set('ABCD')
    assert sum(r['cohort_id'] == 'D' for r in rows.values()) == 3


@pytest.mark.parametrize('cohort,count', [('A', 10), ('B', 5), ('C', 16), ('D', 3)])
def test_cohort_selection(inputs, cohort, count):
    assert len(runner.select(inputs[1], cohorts=[cohort])) == count


@pytest.mark.parametrize('ids', [['unknown'], ['R01', 'R01']])
def test_invalid_ids_fail_closed(inputs, ids):
    with pytest.raises(ValueError):
        runner.select(inputs[1], ids=ids)


def test_multiple_questions_are_canonical_order(inputs):
    assert runner.select(inputs[1], ids=['R02', 'M9-Q01', 'R01']) == ['M9-Q01', 'R01', 'R02']


def test_runs_distinct_and_exclusive_creation(tmp_path):
    a = create_run(tmp_path, 'local-check')
    b = create_run(tmp_path, 'local-check')
    assert a != b
    save(a / 'x.json', {'owned': 1})
    before = (a / 'x.json').read_bytes()
    with pytest.raises(FileExistsError):
        save(a / 'x.json', {'owned': 2})
    assert (a / 'x.json').read_bytes() == before
    assert (a.stat().st_mode & 0o777) == 0o700
    assert ((a / 'x.json').stat().st_mode & 0o777) == 0o600


@pytest.mark.parametrize('url,method', [
    ('https://api.openai.com/v1/responses', 'POST'),
    ('https://api.openai.com/v1/batches', 'POST'),
    ('https://example.org/v1/responses/input_tokens', 'POST'),
    ('http://api.openai.com/v1/responses/input_tokens', 'POST'),
    ('https://api.openai.com/v1/models/other', 'GET'),
    ('https://api.openai.com/v1/responses/input_tokens?unsafe=1', 'POST'),
])
def test_transport_forbids_generation_and_other_endpoints(tmp_path, url, method):
    inner = httpx.MockTransport(lambda _: pytest.fail('NETWORK_MUST_NOT_BE_REACHED'))
    transport = CountOnlyTransport(tmp_path, 'gpt-6-luna', digest({}), inner=inner)
    with pytest.raises(Exception, match='FORBIDDEN'):
        transport.handle_request(httpx.Request(method, url, json={}))
    assert not transport.receipts


def test_transport_count_exact_content_and_no_retries(tmp_path):
    args = {'owned': 'synthetic evidence'}
    inner = httpx.MockTransport(lambda _: httpx.Response(200, json={'input_tokens': 10}))
    transport = CountOnlyTransport(tmp_path, 'gpt-6-luna', digest(args), inner=inner)
    request = httpx.Request('POST', 'https://api.openai.com/v1/responses/input_tokens', json=args)
    assert transport.handle_request(request).status_code == 200
    with pytest.raises(Exception, match='NO_RETRY'):
        transport.handle_request(request)
    assert len(transport.receipts) == 1
    marker = (tmp_path / 'TOKEN_COUNT_ATTEMPT.json').read_text()
    assert 'synthetic evidence' not in marker


def test_transport_rejects_changed_count_payload(tmp_path):
    transport = CountOnlyTransport(tmp_path, 'gpt-6-luna', digest({'owned': 1}),
                                  inner=httpx.MockTransport(lambda _: pytest.fail('NO_SEND')))
    with pytest.raises(Exception, match='HASH_MISMATCH'):
        transport.handle_request(httpx.Request('POST', 'https://api.openai.com/v1/responses/input_tokens', json={'owned': 2}))


def test_adapter_invoke_always_denied():
    with pytest.raises(Exception, match='GENERATION_FORBIDDEN'):
        CountOnlyAdapter().invoke({})


def test_cli_requires_specific_transfer_authorization_before_execution():
    with pytest.raises(SystemExit):
        main(['model-preflight', '--question', 'R01'])


def test_reconstruction_hash_equivalence_and_tamper():
    value = {'request_sha256': digest({'owned': 'complete input'})}
    runner.equivalence(value, copy.deepcopy(value))
    with pytest.raises(ValueError, match='CHANGED'):
        runner.equivalence(value, value | {'request_sha256': '0' * 64})


def test_pricing_stale_and_context_overflow_controls():
    settings = load_settings()
    profile = runner.resolve(settings, as_of=date(2026, 10, 28))
    assert not check_fit(profile, settings, 1050000)['fits']
    price = estimate_max_cost(settings.model, 1000, 4096, load_pricing(), tier='default', as_of=date(2030, 1, 1))
    assert price['status'] == 'COST_UNAVAILABLE'


@pytest.mark.parametrize('failure', ['model', 'schema', 'prompt', 'reserve', 'margin'])
def test_fixed_configuration_guards(monkeypatch, failure):
    key, val = {'model': ('model', 'other'), 'schema': ('response_schema', 'grounded-response-1.0'),
                'prompt': ('prompt_version', 'grounded-generation-prompt-v2'),
                'reserve': ('max_output_tokens', 2048), 'margin': ('safety_margin_tokens', 0)}[failure]
    monkeypatch.setattr(runner, 'load_settings', lambda: load_settings().model_copy(update={key: val}))
    with pytest.raises(ValueError, match='CONFIGURATION_MISMATCH'):
        runner.configuration(ROOT, day=date(2026, 10, 28))


def test_stale_pricing_prevents_network(monkeypatch):
    monkeypatch.setattr(runner, 'load_pricing', dict)
    with pytest.raises(ValueError, match='PRICING_UNAVAILABLE'):
        runner.configuration(ROOT, day=date(2026, 10, 28))


@pytest.mark.parametrize('kind', ['question', 'candidates', 'budget'])
def test_m7_tampering_before_parent_reader(inputs, kind, monkeypatch):
    store, rows = inputs
    result = store.json(artifacts.COMPLETION + '/m7/R01.json')
    if kind == 'question':
        result['query_sha256'] = '0' * 64
    elif kind == 'candidates':
        result['candidates'].pop()
    else:
        result['parameters']['top_k'] = 10
    with pytest.raises(ValueError, match='M7_QUESTION_OR_CONFIGURATION'):
        runner.assemble(object(), object(), rows['R01'], result)


def test_source_tampering_fails_assembly(inputs, monkeypatch):
    store, rows = inputs
    result = store.json(artifacts.COMPLETION + '/m7/R01.json')
    monkeypatch.setattr(runner, 'validate_candidates', lambda *a: None)
    fake = SimpleNamespace(m7={}, inventory={}, assemble=lambda *a, **k: (_ for _ in ()).throw(ValueError('SOURCE_CHANGED')))
    with pytest.raises(ValueError, match='SOURCE_CHANGED'):
        runner.assemble(fake, object(), rows['R01'], result)


def test_metadata_and_source_transfer_policy():
    parent = {'admission_status': 'ADMITTED', 'consumer': {'llm_context': {'source_content': 'OWNED'}}}
    package = {'parents': [{'evidence': {'verified_parent': parent}}]}
    runner.source_transfer_check(package)
    parent['consumer']['external_transfer_allowed'] = False
    with pytest.raises(ValueError, match='TRANSFER_FORBIDDEN'):
        runner.source_transfer_check(package)


def test_local_only_orchestration_has_no_provider_path(tmp_path, inputs, monkeypatch):
    """Owned fixture exercises dispatch/storage, not real source authorization."""
    store, inventory = inputs
    real_bind = dict(store.verified)
    original_json = store.json
    synthetic_package = {'counts': {'selected_parents': 1, 'omitted_parents': 2},
        'budget': {'exact_llm_evidence_tokens': 100}, 'parents': []}
    monkeypatch.setattr(store, 'json', lambda name: {'M8_package_sha256': digest(synthetic_package)}
                        if '/m8/' in name else original_json(name))
    monkeypatch.setattr(runner, 'baseline', lambda root: (store, inventory))
    monkeypatch.setattr(runner, 'dependencies', lambda *a: real_bind)
    monkeypatch.setattr(runner, 'verify_bindings', lambda *a: None)
    monkeypatch.setattr(runner, 'EvidenceService', lambda *a, **k: SimpleNamespace(files={}, check=lambda: None))
    monkeypatch.setattr(runner, 'PromptAssemblyGate', lambda evidence: None)
    monkeypatch.setattr(runner, 'assemble', lambda *a: ({'counts': {'selected_parents': 1, 'omitted_parents': 2},
        'budget': {'exact_llm_evidence_tokens': 100}, 'parents': []},
        SimpleNamespace(audit={'source_integrity': 'OWNED_FIXTURE'})))
    monkeypatch.setattr(runner, 'recipe', lambda *a: ({'request_sha256': 'a' * 64}, {}))
    monkeypatch.setattr(runner, 'GenerationService', lambda *a, **k: pytest.fail('LOCAL_MUST_NOT_CALL_PROVIDER_SERVICE'))
    run, manifest = runner.execute(tmp_path, mode='local-check', selected=['R01'], progress=lambda *a, **k: None)
    data = json.loads((run / 'RESULTS.json').read_text())
    assert data['questions'][0]['status'] == 'LOCAL_VALIDATED'
    assert data['questions'][0]['omitted_parents'] == 2  # partial evidence is not integrity failure
    assert not data['questions'][0]['provider_calls']
    assert not manifest['generation_authorized']


def test_runtime_never_reads_gold_or_expected_abstention():
    text = (ROOT / 'tools/preflight_suite/runner.py').read_text()
    assert "row['answerability']" not in text and "row['group" not in text
    assert '.generate(' not in text and '.invoke(' not in text
    assert "['llm_evidence'] =" not in text
    assert 'gold' not in runner.assemble.__code__.co_names


def test_prior_q05_and_frozen_artifacts_unchanged():
    baseline = json.loads((ROOT / 'workspace/rag-implementation/v1/preflight-suite-v1/PRESERVATION_BEFORE.json').read_text())
    names = ['data/evals/generation/live-q05-funded-v1/MANIFEST.json',
             'data/evals/ranking/dataset-v1/FREEZE_MANIFEST.json',
             'tools/pre_generation_gate/grounded-generation-prompt-v2.1.txt',
             'tools/generation/pricing-v1.json']
    for name in names:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == baseline['files'][name]


def qualification_fixture():
    settings = load_settings()
    profile = runner.resolve(settings, as_of=date(2026, 10, 28))
    fit = check_fit(profile, settings, 1000)
    price = estimate_max_cost(settings.model, 1000, 4096, load_pricing(), tier='default', as_of=date(2026, 10, 28))
    row = {'question_id': 'R01', 'input_tokens': 1000, 'request_sha256': 'a' * 64,
           'M8_package_sha256': 'b' * 64, 'context_fit': fit,
           'maximum_cost_usd': price['estimated_max_cost_usd']}
    audit = {'status': 'READY', 'generation_executed': False, 'generator_input_tokens': 1000,
             'model_access': 'ACCOUNT_MODEL_ACCESS_VERIFIED', 'request_sha256': 'a' * 64,
             'M8_package_sha256': 'b' * 64, 'token_count_receipt': {'request_sha256': 'a' * 64},
             'settings': settings.model_dump(), 'model_profile': profile, 'context_fit': fit,
             'cost_estimate': price}
    manifest = {'mode': 'model-preflight', 'question_ids': ['R01'], 'created_at': '2026-10-28',
                'authorization': {'owner_statement': 'OWNED_FIXTURE', 'question_ids': ['R01'],
                                  'complete_verified_evidence_transfer': True}}
    return row, audit, manifest


def test_qualified_receipt_independent_arithmetic():
    artifacts.validate_qualification(*qualification_fixture())


@pytest.mark.parametrize('kind', ['model', 'count', 'request', 'cost', 'fit', 'generation', 'permission'])
def test_qualified_receipt_tampering_rejected(kind):
    row, audit, manifest = qualification_fixture()
    if kind == 'model':
        audit['model_access'] = 'UNVERIFIED'
    elif kind == 'count':
        audit['generator_input_tokens'] += 1
    elif kind == 'request':
        audit['token_count_receipt']['request_sha256'] = 'c' * 64
    elif kind == 'cost':
        row['maximum_cost_usd'] = '0'
    elif kind == 'fit':
        row['context_fit']['remaining_context_margin'] -= 1
    elif kind == 'generation':
        audit['generation_executed'] = True
    else:
        manifest['authorization']['complete_verified_evidence_transfer'] = False
    with pytest.raises(ArtifactError):
        artifacts.validate_qualification(row, audit, manifest)
