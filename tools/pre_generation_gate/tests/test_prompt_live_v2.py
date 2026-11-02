"""Actual source gateway controls; no provider, inference, retrieval or source rewriting."""

import copy
import importlib.util
import json

import pytest

from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.prompt_v2 import EVIDENCE_PREFIX, PromptAssemblyGate
from tools.pre_generation_gate.tests.test_live import ROOT, package, question, sample, service
from tools.pre_generation_gate.tests.test_prompt_v2 import fixture_configuration

__all__ = ["package", "question", "sample", "service"]


@pytest.fixture(scope="session")
def gate(service):
    return PromptAssemblyGate(service)


def test_verified_complete_draft_without_semantic_block(gate, question, package, sample):
    before = digest(package), digest(sample)
    value = gate.prepare(question, package, sample)
    assert value.audit['status'] == 'BLOCKED_CONFIGURATION'
    assert value.audit['blocking_reasons'] == ['NO_OWNER_AUTHORIZED_GENERATOR_CONFIGURATION']
    assert value.audit['prompt_complete'] and value.audit['response_schema_validated']
    assert value.payload['m8_package'] == package
    assert value.payload['request']['messages'][2]['content'][len(EVIDENCE_PREFIX):] == package['llm_evidence']
    assert not value.audit['semantic_sufficiency_evaluated']
    assert not any('SEMANTIC' in reason for reason in value.audit['blocking_reasons'])
    assert before == (digest(package), digest(sample))
    assert gate.validate_preparation(value, question, package, sample).audit == value.audit


@pytest.mark.parametrize('kind', ['source', 'qualification', 'citation', 'publication',
    'context', 'membership', 'warning', 'llm_text', 'budget'])
def test_tampered_evidence_is_integrity_block(gate, question, package, sample, kind):
    p = copy.deepcopy(package)
    parent = p['parents'][0]['evidence']['verified_parent']
    context = parent['consumer']['llm_context']
    if kind == 'source':
        context['source_content'] = ['invented']
    elif kind == 'qualification':
        context['qualification'] = {}
    elif kind == 'citation':
        parent['citation_locators'] = []
    elif kind == 'publication':
        parent['publication_identity'] = {'version': 'forged'}
    elif kind == 'context':
        context['required_context'] = ['invented']
    elif kind == 'membership':
        parent['memberships'] = []
    elif kind == 'warning':
        context['qa_observations'] = ['changed']
    elif kind == 'llm_text':
        p['llm_evidence'] = 'detached fragment'
    else:
        p['budget']['exact_llm_evidence_tokens'] = 0
    result = gate.prepare(question, p, sample)
    assert result.audit['status'] == 'BLOCKED_INTEGRITY'
    assert result.payload is None


@pytest.mark.parametrize('question', [None, '', 'mismatched request', 'bad\ud800'])
def test_bad_question_is_input_block(gate, package, sample, question):
    result = gate.prepare(question, package, sample)
    assert result.audit['status'] == 'BLOCKED_INPUT'
    assert result.payload is None


def test_original_question_preserved_after_binding_normalization(gate, package, sample, question):
    original = '  ' + question + '\n'
    result = gate.prepare(original, package, sample)
    assert result.audit['source_integrity'] == 'LIVE_M8_VALIDATED'
    assert result.payload['request']['messages'][1]['content'] == original


@pytest.mark.parametrize('schema', [None, {}, {'type': 'object'}])
def test_response_schema_invalid_is_configuration_block(gate, question, package, sample, schema):
    result = gate.prepare(question, package, sample, schema=schema)
    assert result.audit['status'] == 'BLOCKED_CONFIGURATION'
    assert result.audit['source_integrity'] == 'LIVE_M8_VALIDATED'
    assert not result.audit['prompt_complete']


@pytest.mark.parametrize('cfg', [{}, {'model_id': 'unapproved'}, {'verified': True}])
def test_invalid_or_self_verified_model_cannot_be_ready(gate, question, package, sample, cfg):
    result = gate.prepare(question, package, sample, model_configuration=cfg)
    assert result.audit['status'] == 'BLOCKED_CONFIGURATION'
    assert result.payload is None


def test_complete_declaration_does_not_qualify_model_or_tokenizer(gate, question, package, sample):
    result = gate.prepare(question, package, sample, model_configuration=fixture_configuration())
    assert result.audit['status'] == 'BLOCKED_CONFIGURATION'
    assert result.audit['prompt_complete']
    assert result.audit['generator_token_accounting']['full_request_input'] is None
    assert result.audit['available_context_margin'] is None
    assert result.audit['output_token_reserve'] == 100


def test_no_evidence_explicitly_blocks_grounded_prompt(gate, service, sample, question):
    empty = copy.deepcopy(sample)
    empty['candidates'] = []
    package = service.assemble(empty, token_budget=128000)
    result = gate.prepare(question, package, empty)
    assert result.audit['status'] == 'BLOCKED_INPUT'
    assert result.audit['blocking_reasons'] == ['NO_INCLUDED_AUTHORIZED_EVIDENCE']
    assert result.audit['source_integrity'] == 'LIVE_M8_VALIDATED'
    assert result.payload is None


def test_atomic_budget_empty_is_not_semantic_abstention(gate, service, sample, question):
    package = service.assemble(sample, token_budget=1)
    assert package['diagnostics']['omitted']
    assert not package['llm_evidence']
    result = gate.prepare(question, package, sample)
    assert result.audit['status'] == 'BLOCKED_INPUT'
    assert 'decision' not in result.audit


def test_multiple_chunks_same_parent_not_duplicated_by_builder(gate, service, question):
    ranking = json.loads((ROOT/'data/evals/ranking/phase3-experiment-v1/rankings/R01-rrf.json').read_bytes())
    mapping = {r['chunk_id']: r['unit_id'] for r in service.catalog.list_chunks(limit=1000)['items']}
    groups = {}
    for hit in ranking['candidates']:
        groups.setdefault(mapping[hit['chunk_id']], []).append(hit['chunk_id'])
    chosen = next(ids[:2] for ids in groups.values() if len(ids) >= 2)
    path = ROOT/'data/evals/m8-delivery/experiment-v1/common.py'
    spec = importlib.util.spec_from_file_location('prompt_dedup_control', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    value = mod.replay(ranking, chosen, service.m7, service.inventory)
    package = service.assemble(value, token_budget=128000)
    assert package['counts']['candidates'] == 2
    assert package['counts']['selected_parents'] == 1
    assert len(package['diagnostics']['deduplicated']) == 1
    result = gate.prepare(question, package, value)
    assert result.payload['request']['messages'][2]['content'] == EVIDENCE_PREFIX + package['llm_evidence']
    assert len(result.audit['included_parent_ids']) == 1


def test_payload_tampering_rejected_and_audit_has_no_publisher_body(gate, question, package, sample):
    value = gate.prepare(question, package, sample)
    assert all(name not in value.audit for name in ['messages', 'm8_package', 'llm_evidence'])
    assert package['llm_evidence'] not in json.dumps(value.audit)
    value.payload['request']['messages'][2]['content'] += 'forged addition'
    with pytest.raises(ValueError, match='altered_or_stale'):
        gate.validate_preparation(value, question, package, sample)


def test_forged_READY_receipt_is_not_accepted(gate, question, package, sample):
    value = gate.prepare(question, package, sample)
    value.audit['status'] = 'READY'
    with pytest.raises(ValueError, match='altered_or_stale'):
        gate.validate_preparation(value, question, package, sample)
