"""Opt-in successor through real M8 validation; no semantic/inference claim."""

import copy

import pytest

from tools.pre_generation_gate.prompt_v3 import PromptAssemblyGate
from tools.pre_generation_gate.tests.test_live import package, question, sample, service

__all__ = ['package', 'question', 'sample', 'service']


@pytest.fixture(scope='session')
def gate(service):
    return PromptAssemblyGate(service)


@pytest.mark.parametrize('kind', ['qualification', 'citation', 'warning', 'llm_text', 'publication'])
def test_live_tampering_rejected(gate, question, package, sample, kind):
    p = copy.deepcopy(package)
    parent = p['parents'][0]['evidence']['verified_parent']
    if kind == 'qualification':
        parent['consumer']['llm_context']['qualification'] = {}
    elif kind == 'citation':
        parent['citation_locators'] = []
    elif kind == 'warning':
        parent['consumer']['llm_context']['qa_observations'] = []
    elif kind == 'publication':
        parent['publication_identity'] = {'version': 'forged'}
    else:
        p['llm_evidence'] += 'forged addition'
    if p == package:  # Ensure the removal control actually mutates the fixture.
        parent['consumer']['llm_context']['qa_observations'] = ['forged warning']
    out = gate.prepare(question, p, sample)
    assert out.audit['status'] == 'BLOCKED_INTEGRITY'
    assert out.payload is None


def test_rebuild_rejects_mutated_request(gate, question, package, sample):
    prepared = gate.prepare(question, package, sample)
    assert prepared.audit['template_version'] == 'grounded-generation-prompt-v2'
    prepared.payload['request']['messages'][2]['content'] += 'mutated'
    with pytest.raises(ValueError, match='altered_or_stale'):
        gate.validate_preparation(prepared, question, package, sample)


def test_wrong_question_rejected(gate, question, package, sample):
    assert gate.prepare(question+' wrong', package, sample).audit['status'] == 'BLOCKED_INPUT'


@pytest.mark.parametrize('schema', [None, {'type': 'object'}, object()])
def test_invalid_schema_fails_closed(gate, question, package, sample, schema):
    value = gate.prepare(question, package, sample, schema=schema)
    assert value.audit['status'] == 'BLOCKED_CONFIGURATION'
    assert value.audit['blocking_reasons'] == ['RESPONSE_SCHEMA_UNVERIFIED']
    assert value.payload is None


def test_final_source_success_path(gate, question, package, sample):
    value = gate.prepare(question, package, sample)
    assert value.audit['source_integrity'] == 'LIVE_M8_VALIDATED'
    assert value.audit['status'] == 'BLOCKED_CONFIGURATION'
    assert value.payload['m8_package'] == package
    assert value.audit['template_version'] == 'grounded-generation-prompt-v2'
