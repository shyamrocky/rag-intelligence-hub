"""Actual one-parent M8 path, no retrieval/inference or benchmark-wide execution."""
import copy

import pytest

from tools.pre_generation_gate import current, prompt_v21
from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.response_v2 import response_schema, validate_synthetic_example
from tools.pre_generation_gate.tests.test_live import package, question, sample, service

__all__ = ['package', 'question', 'sample', 'service']


def test_sections_and_schema_unchanged_except_abstention_instructions():
    for start, end in [('ROLE\n', 'GOAL / TASK'), ('GOAL / TASK\n', 'CONTEXT'),
                       ('CONTEXT\n', 'INSTRUCTIONS'), ('EXAMPLE —', 'OUTPUT FORMAT')]:
        assert current.TEMPLATE.split(start)[1].split(end)[0] == prompt_v21.TEMPLATE.split(start)[1].split(end)[0]
    assert current.DEFAULT_RESPONSE_SCHEMA_VERSION == 'grounded-response-2.0'
    assert response_schema()['$id'] == 'urn:rag-hub:grounded-response-2.0'
    assert validate_synthetic_example().status == 'ANSWERED'
    assert 'Absence of evidence is not proof that something does not exist.' in current.SYSTEM
    assert 'specific, user-understandable' in current.SYSTEM
    assert current.HistoricalV21PromptAssemblyGate is prompt_v21.PromptAssemblyGate


def test_live_current_and_explicit_v21_request_preservation(service, package, question, sample):
    original = copy.deepcopy((package, sample))
    old_gate = prompt_v21.PromptAssemblyGate(service)
    gate = current.PromptAssemblyGate(service)
    old = old_gate.prepare(question, package, sample)
    new = gate.prepare(question, package, sample)
    assert old.audit['template_version'] == 'grounded-generation-prompt-v2.1'
    assert new.audit['template_version'] == 'grounded-generation-prompt-v2.2'
    assert new.audit['source_integrity'] == 'LIVE_M8_VALIDATED'
    assert new.audit['status'] == 'BLOCKED_CONFIGURATION'
    assert new.audit['generator_token_accounting']['full_request_input'] is None
    assert new.audit['provider_requalification_required']
    assert new.audit['historical_token_receipts_reusable'] is False
    assert new.payload['request']['messages'][1:] == old.payload['request']['messages'][1:]
    assert new.payload['request']['response_format'] == old.payload['request']['response_format']
    assert new.payload['m8_package'] == old.payload['m8_package'] == package
    assert new.audit['request_sha256'] != old.audit['request_sha256']
    assert old_gate.prepare(question, package, sample).payload == old.payload
    assert gate.validate_preparation(new, question, package, sample).payload == new.payload
    new.payload['request']['messages'][2]['content'] += 'tamper'
    with pytest.raises(ValueError, match='altered_or_stale'):
        gate.validate_preparation(new, question, package, sample)
    assert (package, sample) == original


def test_old_prompt_hash_is_stable():
    assert digest(prompt_v21.SYSTEM) == '796288c3c646904e68a8214031f4d68e563dee2874ce9e92adb361061aba979c'
