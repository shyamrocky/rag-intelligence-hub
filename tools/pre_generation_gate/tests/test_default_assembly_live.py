"""Canonical default route through actual current M8, no inference or retrieval."""

import copy

import pytest

from tools.pre_generation_gate.assembly import PromptAssemblyGate
from tools.pre_generation_gate.prompt_v2 import EVIDENCE_PREFIX
from tools.pre_generation_gate.response_v1 import response_schema as schema_v1
from tools.pre_generation_gate.tests.test_live import package, question, sample, service

__all__ = ['package', 'question', 'sample', 'service']


@pytest.fixture(scope='session')
def gate(service):
    return PromptAssemblyGate(service)


def test_prepare_without_version_override_uses_v2_and_audits_configuration(gate, question, package, sample):
    value = gate.prepare(question, package, sample)
    a = value.audit
    assert a['template_version'] == 'grounded-generation-prompt-v2'
    assert a['response_schema_version'] == 'grounded-response-2.0'
    assert a['status'] == 'BLOCKED_CONFIGURATION'
    assert a['model_configuration_status'] == 'NOT_CONFIGURED'
    assert a['request_sha256'] and a['M8_package_sha256']
    assert value.payload['request']['messages'][2]['content'] == EVIDENCE_PREFIX + package['llm_evidence']
    assert gate.validate_preparation(value, question, package, sample).audit == a


def test_default_rejects_v1_schema_without_fallback(gate, question, package, sample):
    value = gate.prepare(question, package, sample, schema=schema_v1())
    assert value.payload is None
    assert value.audit['template_version'] == 'grounded-generation-prompt-v2'
    assert value.audit['response_schema_version'] == 'grounded-response-2.0'
    assert value.audit['blocking_reasons'] == ['RESPONSE_SCHEMA_UNVERIFIED']


def test_default_rejects_source_change(gate, question, package, sample):
    altered = copy.deepcopy(package)
    altered['llm_evidence'] += 'altered'
    assert gate.prepare(question, altered, sample).audit['status'] == 'BLOCKED_INTEGRITY'
