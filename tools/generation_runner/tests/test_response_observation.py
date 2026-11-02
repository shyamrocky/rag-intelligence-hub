"""Offline output intake and execution-safety controls. No real provider operations."""
import copy
import json
from types import SimpleNamespace

import pytest

from tools.generation.observation import field_checks, observe
from tools.generation_runner.disposition import disposition


def raw(text, status='completed'):
    return {'model': 'owned-model', 'status': status,
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}


@pytest.mark.parametrize('text,state', [('{}', 'JSON_CANDIDATE_UNTRUSTED'),
    ('{"status":"ANSWERED","status":"PARTIAL"}', 'AMBIGUOUS_DUPLICATE_KEYS'),
    ('not-json', 'MALFORMED_JSON_TEXT_PRESERVED'), ('[1]', 'JSON_CANDIDATE_UNTRUSTED'),
    ('{"value":NaN}', 'MALFORMED_JSON_TEXT_PRESERVED')])
def test_all_output_is_observed_without_contract_coercion(text, state):
    value = observe(raw(text))
    assert value['state'] == state and value['text_parts'] == [text]
    assert value['accepted_contract'] is False and value['semantic_status'] == 'NOT_ASSESSED'
    if 'AMBIGUOUS' in state:
        assert value['candidate'] is None


def test_refusal_and_incomplete_preserved():
    r = raw('part', 'incomplete')
    r['output'][0]['content'].append({'type': 'refusal', 'refusal': 'Owned refusal'})
    assert observe(r)['refusals'] == ['Owned refusal']
    assert observe(r)['provider_status'] == 'incomplete'


def test_partial_field_checks_do_not_accept_contract_or_fabricated_ids():
    candidate = {'status': 'ANSWERED', 'claims': [{'claim_text': 'Owned', 'evidence_unit_ids': ['invented'],
        'supporting_quotes': [{'quote': 'Invented', 'evidence_unit_id': 'invented'}]}],
        'requirement_coverage': [{'evidence_unit_ids': ['EXAMPLE-UNIT-001']}], 'conflicts_detected': []}
    value = field_checks(observe(raw(json.dumps(candidate))), {'parents': []})
    assert len(value['citations']) == 3 and all(c['status'] == 'INVALID_CITATION' for c in value['citations'])
    assert value['quotations'][0]['outcome'] == 'SOURCE_NOT_FOUND'
    assert value['semantic_status'] == 'PENDING_REVIEW' and not value['fully_validated']


def safe_record():
    row = {'status': 'INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE', 'response': None,
        'post_validation': {'overall_status': 'VALIDATION_FAILED'},
        'audit': {'generation_executed': True, 'response_status': 'completed', 'model': 'owned-model',
            'request_sha256': 'a'*64, 'M8_package_sha256': 'b'*64,
            'usage': {'cost_status': 'ESTIMATED_API_COST', 'input_tokens': 100, 'output_tokens': 10,
                      'total_tokens': 110, 'total_estimated_cost_usd': '0.001'}}}
    plan = {'request_sha256': 'a'*64, 'M8_package_sha256': 'b'*64, 'input_tokens': 100,
            'maximum_cost_usd': '0.02', 'per_question_cap_usd': '0.03'}
    return row, plan, SimpleNamespace(model='owned-model', max_output_tokens=4096)


def test_noncompliant_output_continues_without_accepting_answer():
    row, plan, settings = safe_record()
    value = disposition(row, plan, settings, capture_verified=True)
    assert value['action'] == 'CONTINUE_INDEPENDENT_QUESTIONS'
    assert not value['answer_accepted'] and not value['automatic_retry']


@pytest.mark.parametrize('mutation', ['model', 'request', 'source', 'billing', 'usage', 'output',
                                     'cost', 'capture', 'provider', 'exception', 'post_source'])
def test_safety_failures_always_stop(mutation):
    row, plan, settings = safe_record()
    verified = True
    if mutation == 'model': row['audit']['model'] = 'other'
    elif mutation == 'request': row['audit']['request_sha256'] = 'c'*64
    elif mutation == 'source': row['audit']['M8_package_sha256'] = 'c'*64
    elif mutation == 'billing': row['audit']['usage']['cost_status'] = 'COST_UNAVAILABLE'
    elif mutation == 'usage': row['audit']['usage']['total_tokens'] = 111
    elif mutation == 'output': row['audit']['usage']['output_tokens'] = 5000
    elif mutation == 'cost': row['audit']['usage']['total_estimated_cost_usd'] = '0.031'
    elif mutation == 'capture': verified = False
    elif mutation == 'provider': row['audit']['response_status'] = 'failed'
    elif mutation == 'exception': row['status'] = 'BLOCKED_OR_FAILED'
    elif mutation == 'post_source': row['post_validation']['source_integrity'] = 'FAIL'
    assert disposition(row, plan, settings, capture_verified=verified)['action'] == 'STOP_SAFETY'


def test_observation_does_not_mutate_request_or_source():
    value = raw('{"answer":"Owned"}'); before = copy.deepcopy(value)
    field_checks(observe(value), {'parents': []})
    assert value == before


@pytest.mark.parametrize('kind', ['observation', 'material'])
def test_unsafe_private_directory_prevents_publisher_persistence(tmp_path, kind):
    from tools.generation.observation import persist
    from tools.generation_runner.review_material import retain
    from tools.quality_dashboard.artifacts import ArtifactError
    base = tmp_path / 'workspace' / ('generation-observations' if kind == 'observation' else 'generation-review-material')
    base.mkdir(parents=True); base.chmod(0o755)
    qdir = tmp_path / 'data/evals/generation-runner/owned-run/questions/OWNED-Q'
    row = {'question_id': 'OWNED-Q', 'request_sha256': 'a'*64, 'M8_package_sha256': 'b'*64,
           'M7_result_sha256': 'c'*64}
    with pytest.raises(ArtifactError, match='UNSAFE_'):
        if kind == 'observation': persist(tmp_path,qdir,observe(raw('{}')),row,{'parents':[]})
        else: retain(tmp_path,qdir,row,{'parents':[]},{})
    assert not list(base.rglob('*.json'))


def test_excessively_nested_json_is_preserved_without_losing_the_attempt():
    from tools.generation.service import parse_response
    text = '['*1500 + ']'*1500
    assert observe(raw(text))['text_parts'] == [text]
    with pytest.raises(ValueError): parse_response(raw(text),set())
