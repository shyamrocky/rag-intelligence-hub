"""Owned timing controls: no corpus reconstruction, credentials or provider calls."""
import copy
import json
from types import SimpleNamespace

import pytest

from tools.generation_runner.timing import STAGES, StageTimer, validate_timing


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1_000_000
        return self.value


def timer(mode='mock'):
    return StageTimer('M9-Q01', 'owned-run', mode, clock=Clock())


def finish(t):
    return t.finish(request_sha256='a' * 64, package_sha256='b' * 64)


def test_nested_exclusive_accounting_and_wall_elapsed():
    t = timer()
    with t.span('MODEL_PREFLIGHT'):
        with t.span('M8_SOURCE_VALIDATION'), t.span('M8_EVIDENCE_ASSEMBLY'):
            pass
        with t.span('MODEL_TOKEN_COUNT'):
            pass
    value = finish(t)
    assert value['end_to_end_ms'] == 9
    summary = {s['stage']: s for s in value['stages']}
    assert summary['MODEL_PREFLIGHT']['inclusive_ms'] == 7
    assert summary['MODEL_PREFLIGHT']['duration_ms'] == 3
    assert summary['M8_SOURCE_VALIDATION']['duration_ms'] == 2
    assert sum(s['duration_ms'] or 0 for s in value['stages']) + value['unattributed_overhead_ms'] == 9
    assert value['preflight_observation'] == 'REUSED_HISTORICAL'
    assert value['provider_reported_latency_ms'] is None


@pytest.mark.parametrize('stage', STAGES)
def test_stage_failure_retains_partial_observation_and_redacts_exception(stage):
    t = timer()
    with pytest.raises(RuntimeError), t.span(stage):
        raise RuntimeError('PROTECTED_PUBLISHER_TEXT_OR_SECRET')
    value = finish(t)
    assert value['error_stage'] == stage
    assert next(s for s in value['stages'] if s['stage'] == stage)['status'] == 'FAILED'
    assert 'PROTECTED_PUBLISHER_TEXT_OR_SECRET' not in json.dumps(value)
    assert all(s['duration_ms'] is None for s in value['stages'] if s['status'] == 'SKIPPED')


def test_observer_preserves_identity_operation_count_order_and_restores():
    calls = []
    result = object()
    class Owned:
        def run(self, question, *, flag):
            calls.append((question, flag))
            return result
    owner = Owned()
    t = timer()
    with t.observe(owner, 'run', 'PROMPT_ASSEMBLY'):
        assert owner.run('owned', flag=True) is result
    assert 'run' not in vars(owner)
    assert calls == [('owned', True)]
    assert len(finish(t)['spans']) == 1


def test_function_observer_restores_on_error():
    def fail():
        raise ValueError('private')
    owner = SimpleNamespace(run=fail)
    t = timer()
    with pytest.raises(ValueError), t.observe(owner, 'run', 'M8_EVIDENCE_ASSEMBLY'):
        owner.run()
    assert owner.run is fail
    assert finish(t)['error_stage'] == 'M8_EVIDENCE_ASSEMBLY'


@pytest.mark.parametrize('mode,label', [('mock', 'MOCK_ADAPTER_DURATION'),
    ('live', 'LOCAL_PROVIDER_REQUEST_DURATION')])
def test_same_infrastructure_mock_and_future_live(mode, label):
    t = timer(mode)
    calls = []
    owned = SimpleNamespace(invoke=lambda: calls.append('owned-only'))
    with t.observe(owned, 'invoke', 'LLM_GENERATION'):
        owned.invoke()
    value = t.finish(request_sha256='a' * 64, package_sha256='b' * 64, usage={'latency_ms': 37})
    assert value['generation_label'] == label and calls == ['owned-only']
    assert value['existing_usage_latency_ms'] == 37
    assert value['provider_reported_latency_status'] == 'UNAVAILABLE'


@pytest.mark.parametrize('field,changed', [('end_to_end_ms', -1),
    ('mode', 'INVALID'), ('schema', 'bad'), ('generation_label', 'LIVE_RETRIEVAL'),
    ('unattributed_overhead_ms', float('nan'))])
def test_invalid_receipts_rejected(field, changed):
    value = finish(timer())
    value[field] = changed
    with pytest.raises(ValueError):
        validate_timing(value)


def test_receipt_identity_and_span_accounting_tampering():
    t = timer()
    with t.span('M8_EVIDENCE_ASSEMBLY'):
        pass
    value = finish(t)
    for kwargs in [{'question_id': 'R01'}, {'run_id': 'other'},
                   {'mode': 'live'}, {'request_sha256': 'c' * 64}]:
        with pytest.raises(ValueError):
            validate_timing(value, **kwargs)
    for field in ['duration_ms', 'exclusive_ms', 'end_ns']:
        changed = copy.deepcopy(value)
        changed['spans'][0][field] += 100
        with pytest.raises(ValueError):
            validate_timing(changed)


@pytest.mark.parametrize('fail_at', ['RESULT.json', 'QUESTION_RESULT_MANIFEST.json'])
def test_persistence_failure_preserves_partial_timings_without_retry(tmp_path, monkeypatch, fail_at):
    from tools.generation_runner import runner
    from tools.preflight_suite.artifacts import save
    t = timer()
    calls = []
    def writing(path, value):
        calls.append(path.name)
        if path.name == fail_at:
            raise OSError('source material must not enter receipt')
        return save(path, value)
    monkeypatch.setattr(runner, 'save', writing)
    row = {'question_id': 'M9-Q01', 'request_sha256': 'a' * 64, 'M8_package_sha256': 'b' * 64}
    with pytest.raises(OSError):
        runner.persist_question(tmp_path / 'q', row, t)
    receipt = json.loads((tmp_path / 'q/STAGE_TIMINGS.json').read_bytes())
    assert receipt['error_stage'] == 'ARTIFACT_PERSISTENCE'
    assert calls.count(fail_at) == 1 and calls[-1] == 'STAGE_TIMINGS.json'
    assert 'source material' not in json.dumps(receipt)


def test_successful_persistence_seals_result_before_end_to_end(tmp_path):
    from tools.generation_runner.runner import persist_question
    from tools.preflight_suite.artifacts import sha
    row = {'question_id': 'M9-Q01', 'request_sha256': 'a' * 64, 'M8_package_sha256': 'b' * 64}
    persist_question(tmp_path / 'q', row, timer())
    seal = json.loads((tmp_path / 'q/QUESTION_RESULT_MANIFEST.json').read_bytes())
    assert seal['files']['RESULT.json'] == sha(tmp_path / 'q/RESULT.json')
    value = json.loads((tmp_path / 'q/STAGE_TIMINGS.json').read_bytes())
    assert next(s for s in value['stages'] if s['stage'] == 'ARTIFACT_PERSISTENCE')['status'] == 'MEASURED'


@pytest.mark.parametrize('failure,expected,calls_expected', [
    (None, 'GENERATED_QUALIFICATIONS_VALID', ['metadata', 'count', 'generation']),
    ('metadata', 'BLOCKED_CONFIGURATION', ['metadata']),
    ('generation', 'PROVIDER_ERROR', ['metadata', 'count', 'generation']),
])
def test_actual_generation_service_future_live_timing_with_owned_provider_only(
    failure, expected, calls_expected,
):
    from contextlib import ExitStack
    from datetime import date
    from unittest.mock import Mock

    from tools.generation.current import GenerationService, load_settings, resolve
    from tools.generation.openai_adapter import ProviderError
    from tools.generation.telemetry import capture_usage, load_pricing
    from tools.generation.tests.test_adapter import sdk_response
    from tools.quality_dashboard.artifacts import digest

    # Deliberately bypass source construction for this isolated control-flow test.
    # It is NOT source qualification or an execution of runner live mode.
    service = object.__new__(GenerationService)
    service.settings, service.pricing, service.as_of = load_settings(), load_pricing(), date(2026, 10, 28)
    profile = resolve(service.settings, as_of=service.as_of)
    request = {'model': service.settings.model}
    current = SimpleNamespace(payload={}, audit={'request_sha256': 'a' * 64})
    service._request = Mock(return_value=(current, profile, request))
    service.gate = SimpleNamespace(validate_preparation=Mock())
    service.assess_response = Mock(return_value={'status': 'QUALIFICATIONS_VALID', 'fully_validated': False})
    calls = []
    def operation(name, result):
        calls.append(name)
        if failure == name:
            raise ProviderError('OWNED_FAILURE', latency_ms=7)
        return result
    raw = sdk_response()
    adapter = SimpleNamespace(configuration_error=lambda: None,
        verify_model=lambda _: operation('metadata', {'status': 'ACCOUNT_MODEL_ACCESS_VERIFIED'}),
        count=lambda _: operation('count', {'input_tokens': 100, 'request_sha256': digest(request)}),
        invoke=lambda _: operation('generation', (raw, capture_usage(raw, service.settings.model, 3))))
    service.adapter = adapter
    t = timer('live')
    with ExitStack() as scopes:
        for owner, method, stage in [(service, 'dry_run', 'MODEL_PREFLIGHT'),
            (adapter, 'verify_model', 'MODEL_METADATA'), (adapter, 'count', 'MODEL_TOKEN_COUNT'),
            (adapter, 'invoke', 'LLM_GENERATION')]:
            scopes.enter_context(t.observe(owner, method, stage))
        outcome = service.generate(None, 'Owned control only', {'parents': []}, {},
            allow_paid_inference=True, allow_source_transfer=True)
    assert outcome.audit['status'] == expected and calls == calls_expected
    value = t.finish(request_sha256=digest(request), package_sha256='b' * 64,
                     usage=outcome.audit.get('usage'))
    assert value['generation_label'] == 'LOCAL_PROVIDER_REQUEST_DURATION'
    assert value['provider_reported_latency_ms'] is None
    if failure is not None:
        assert value['error_stage'] == ('MODEL_METADATA' if failure == 'metadata' else 'LLM_GENERATION')
