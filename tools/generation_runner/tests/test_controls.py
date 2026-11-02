"""Owned synthetic controls. Never provider access or live-generation markers."""
import copy
import json
from decimal import Decimal

import httpx
import pytest

from tools.generation.current import load_settings
from tools.generation.openai_adapter import ProviderError
from tools.generation.telemetry import load_pricing
from tools.generation_runner.controls import Budget, OfflineAdapter
from tools.generation_runner.live import LimitedTransport
from tools.generation_runner.plan import money
from tools.quality_dashboard.artifacts import digest


def owned_plan():
    return {'aggregate_cap_usd': '0.04', 'questions': [
        {'question_id': q, 'per_question_cap_usd': '0.03',
         'maximum_cost_usd': '0.025', 'request_sha256': digest({'owned': 1})}
        for q in ['R01', 'R02']]}


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '0', '', None, 1, True])
def test_invalid_costs_rejected(value):
    with pytest.raises((ValueError, TypeError, ArithmeticError)):
        money(value)


def test_decimal_cost_exact():
    assert money('0.76430900') + money('0.23569100') == Decimal('1.00000000')


def test_exclusive_attempt_and_no_release_on_failure(tmp_path):
    budget = Budget(tmp_path, owned_plan())
    budget.admit('R01', '0.025', digest({'owned': 1}), mode='mock')
    assert budget.reserved == Decimal('0.025')
    with pytest.raises(ProviderError):
        budget.admit('R01', '0.025', digest({'owned': 1}), mode='mock')
    # Creating a new in-memory budget cannot bypass a durable existing attempt.
    with pytest.raises(FileExistsError):
        Budget(tmp_path, owned_plan()).admit('R01', '0.025', digest({'owned': 1}), mode='mock')
    assert not list(tmp_path.rglob('LIVE*'))
    marker = tmp_path / 'questions/R01/MOCK_ATTEMPT.json'
    assert (marker.stat().st_mode & 0o777) == 0o600


@pytest.mark.parametrize('cost', ['0.026', '0.031', 'NaN', '-0.01'])
def test_per_question_ceiling_no_attempt(tmp_path, cost):
    with pytest.raises((ProviderError, ArithmeticError)):
        Budget(tmp_path, owned_plan()).admit('R01', cost, digest({'owned': 1}), mode='mock')
    assert not list(tmp_path.rglob('*ATTEMPT*'))


def test_aggregate_cap_retains_failed_reservation(tmp_path):
    budget = Budget(tmp_path, owned_plan())
    budget.admit('R01', '0.025', digest({'owned': 1}), mode='mock')
    with pytest.raises(ProviderError, match='COST_CAP'):
        budget.admit('R02', '0.025', digest({'owned': 1}), mode='mock')
    assert not (tmp_path / 'questions/R02/MOCK_ATTEMPT.json').exists()


def test_request_change_no_attempt(tmp_path):
    with pytest.raises(ProviderError):
        Budget(tmp_path, owned_plan()).admit('R01', '.01', '0' * 64, mode='mock')
    assert not list(tmp_path.rglob('*ATTEMPT*'))


@pytest.mark.parametrize('operation', ['metadata', 'count', 'generation'])
def test_dry_adapter_denies_all_provider_operations(operation):
    adapter = OfflineAdapter({}, mode='dry-run')
    with pytest.raises(ProviderError, match='DENIED'):
        {'metadata': adapter.verify_model, 'count': adapter.count, 'generation': adapter.invoke}[operation]({})
    assert not adapter.calls


@pytest.mark.parametrize('method,url', [
    ('POST', 'https://api.openai.com/v1/responses'),
    ('POST', 'https://api.openai.com/v1/responses/input_tokens'),
    ('POST', 'https://example.com/v1/responses'),
    ('GET', 'https://api.openai.com/v1/models/other'),
    ('POST', 'https://api.openai.com/v1/batches'),
    ('POST', 'http://api.openai.com/v1/responses'),
    ('POST', 'https://api.openai.com/v1/responses?x=1'),
])
def test_future_transport_negative_controls_never_reach_network(tmp_path, method, url):
    transport = LimitedTransport(tmp_path, {'model': 'gpt-6-luna'},
        inner=httpx.MockTransport(lambda _: pytest.fail('NO_NETWORK')))
    with pytest.raises((ProviderError, KeyError)):
        transport.handle_request(httpx.Request(method, url, json={}))
    assert not transport.calls
    assert not list(tmp_path.rglob('*ATTEMPT*'))


def test_future_transport_owned_metadata_once(tmp_path):
    calls = []
    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(503)
    transport = LimitedTransport(tmp_path, {'model': 'gpt-6-luna'}, inner=httpx.MockTransport(handler))
    req = httpx.Request('GET', 'https://api.openai.com/v1/models/gpt-6-luna')
    assert transport.handle_request(req).status_code == 503
    with pytest.raises(ProviderError, match='NO_RETRY'):
        transport.handle_request(req)
    assert len(calls) == 1 and not list(tmp_path.rglob('LIVE_ATTEMPT.json'))


def test_live_requires_approval_before_any_record(tmp_path):
    from tools.generation_runner.runner import execute
    with pytest.raises(ValueError, match='NOT_AUTHORIZED'):
        execute(tmp_path, mode='live')
    assert not list(tmp_path.iterdir())


def test_cli_live_not_enabled_without_all_optins():
    from tools.generation_runner.__main__ import main
    with pytest.raises(SystemExit):
        main(['live', '--pending-generation'])


def test_schema_and_provider_failure_mock_controls(tmp_path):
    from datetime import date

    from tools.generation.service import parse_response

    settings = load_settings()
    p = owned_plan()
    request = {'owned': 1}
    row = p['questions'][0] | {'input_tokens': 1000}
    for scenario in ['success', 'schema-error', 'api-failure']:
        b = Budget(tmp_path / scenario, p)
        a = OfflineAdapter(row, mode='mock', scenario=scenario, request=request,
            settings=settings, pricing=load_pricing(), day=date(2026, 10, 28), budget=b)
        if scenario == 'api-failure':
            with pytest.raises(ProviderError):
                a.invoke(request)
        else:
            raw, usage = a.invoke(request)
            assert usage['total_tokens'] == 1010
            if scenario == 'schema-error':
                with pytest.raises(ValueError):
                    parse_response(raw, set())
            else:
                assert parse_response(raw, set())['status'] == 'ABSTAINED'
        with pytest.raises(ProviderError, match='NO_RETRY'):
            a.invoke(request)
    assert not list(tmp_path.rglob('LIVE_ATTEMPT.json'))


def test_success_partial_and_unsupported_synthetic_responses():
    from tools.pre_generation_gate.response_v2 import synthetic_example, validate_response_shape
    example = synthetic_example()
    # Definition's actual structure is deliberately verified instead of invented here.
    assert example
    answered = {'status': 'ANSWERED', 'answer': 'Owned source supports X.',
        'claims': [{'claim_text': 'Owned source supports X.', 'evidence_unit_ids': ['owned-unit'],
                    'supporting_quotes': [{'evidence_unit_id': 'owned-unit', 'quote': 'X'}]}],
        'missing_information': [], 'relevant_qualifications': [],
        'requirement_coverage': [{'requirement': 'X', 'status': 'SUPPORTED', 'evidence_unit_ids': ['owned-unit']}],
        'conflicts_detected': []}
    assert validate_response_shape(answered, authorized_unit_ids={'owned-unit'}).status == 'ANSWERED'
    partial = copy.deepcopy(answered)
    partial.update(status='PARTIAL', missing_information=['Y not provided'])
    partial['requirement_coverage'].append({'requirement': 'Y', 'status': 'UNSUPPORTED', 'evidence_unit_ids': []})
    assert validate_response_shape(partial, authorized_unit_ids={'owned-unit'}).status == 'PARTIAL'
    # This is structural correctness, not independently judged appropriate abstention.
    abstained = {'status': 'ABSTAINED', 'answer': '', 'claims': [], 'missing_information': ['No evidence'],
                 'relevant_qualifications': [], 'requirement_coverage': [], 'conflicts_detected': []}
    assert validate_response_shape(abstained, authorized_unit_ids=set()).status == 'ABSTAINED'


def test_durable_marker_contains_no_request_payload(tmp_path):
    b = Budget(tmp_path, owned_plan())
    b.admit('R01', '.01', digest({'owned': 1}), mode='mock')
    data = json.loads((tmp_path / 'questions/R01/MOCK_ATTEMPT.json').read_bytes())
    assert 'input' not in data and 'response' not in data
