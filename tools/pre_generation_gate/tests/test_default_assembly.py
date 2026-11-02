"""Default route controls plus preserved explicit historical v1 selection."""

import inspect

import pytest

from tools.pre_generation_gate import assembly
from tools.pre_generation_gate.prompt_v2 import PromptAssemblyGate as GateV1
from tools.pre_generation_gate.prompt_v3 import SYSTEM, build_request
from tools.pre_generation_gate.prompt_v3 import PromptAssemblyGate as GateV2
from tools.pre_generation_gate.response_v1 import response_schema as schema_v1
from tools.pre_generation_gate.response_v2 import response_schema, validate_synthetic_example


def test_default_pair_and_class_are_v2():
    assert assembly.DEFAULT_TEMPLATE_VERSION == 'grounded-generation-prompt-v2'
    assert assembly.DEFAULT_RESPONSE_SCHEMA_VERSION == 'grounded-response-2.0'
    assert issubclass(assembly.PromptAssemblyGate, GateV2)
    assert assembly.PromptAssemblyGate is not GateV1
    assert 'template_version' not in inspect.signature(assembly.PromptAssemblyGate).parameters


def test_explicit_v1_replay_selection_is_preserved():
    assert assembly.HistoricalV1PromptAssemblyGate is GateV1


def test_default_schema_requires_both_new_fields_and_example_valid():
    assert {'requirement_coverage', 'conflicts_detected'} <= set(response_schema()['required'])
    assert validate_synthetic_example().status == 'ANSWERED'
    for section in ['ROLE', 'GOAL / TASK', 'CONTEXT', 'INSTRUCTIONS', 'CONSTRAINTS',
                    'EXAMPLE', 'OUTPUT FORMAT']:
        assert section in SYSTEM


def test_v1_schema_cannot_pair_with_default_v2_request():
    with pytest.raises(ValueError, match='cross_version'):
        build_request('Owned question', {'llm_evidence': 'Owned evidence'}, schema_v1(), None)


def test_default_route_has_no_other_pipeline_or_runtime_selection():
    source = inspect.getsource(assembly)
    assert 'token_budget=' not in source and 'top_k=' not in source
    assert '.search(' not in source and '.assemble(' not in source
    assert '.forward(' not in source and '.predict(' not in source
