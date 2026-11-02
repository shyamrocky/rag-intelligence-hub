"""Synthetic runner-boundary failures; no real M8, provider, auth or attempt markers."""
import json
from types import SimpleNamespace

import pytest

from tools.generation_runner import runner
from tools.preflight_suite.artifacts import save
from tools.quality_dashboard.artifacts import digest


@pytest.mark.parametrize('failure,expected', [
    (None, None), ('m8', 'M8_EVIDENCE_ASSEMBLY'), ('prompt', 'PROMPT_ASSEMBLY'),
    ('preflight', 'MODEL_METADATA'), ('generation', 'LLM_GENERATION'),
    ('post', 'POST_GENERATION_VALIDATION'),
])
def test_runner_partial_timings_and_operation_order(tmp_path, monkeypatch, failure, expected):
    from tools.answer_quality import validator_abstention as post_module
    from tools.evidence import service as evidence_module
    from tools.generation import current as generation_module
    from tools.pre_generation_gate import current as gate_module
    from tools.preflight_suite import runner as preparation

    calls = []
    def step(name):
        calls.append(name)
        if name == failure:
            raise ValueError('PRIVATE_ARGUMENTS_NEVER_PERSISTED')

    class Evidence:
        def __init__(self, *args, **kwargs):
            self.files = {}
        def assemble(self, *args, **kwargs):
            step('m8')
            return {'counts': {'selected_parents': 1}, 'budget': {'exact_llm_evidence_tokens': 10}}
        def validate(self, *args):
            step('source-validation')
        def check(self):
            step('check')

    class Gate:
        def __init__(self, evidence):
            self.evidence = evidence
        def prepare(self, *args, **kwargs):
            self.evidence.validate(*args)
            step('prompt')
            return SimpleNamespace(audit={'source_integrity': 'LIVE_M8_VALIDATED'})
        def validate_preparation(self, *args):
            return self.prepare(*args)

    class Adapter:
        def __init__(self, *args, **kwargs):
            self.calls = []
        def verify_model(self, *args):
            step('preflight')
        def count(self, *args):
            step('count')
        def invoke(self, *args):
            step('generation')
            self.calls.append('generation')

    class Service:
        def __init__(self, gate, adapter, **kwargs):
            self.gate, self.adapter = gate, adapter
        def dry_run(self):
            self.gate.validate_preparation()
            self.adapter.verify_model()
            self.adapter.count()
        def generate(self, *args, **kwargs):
            self.dry_run()
            self.adapter.invoke()
            return SimpleNamespace(audit={'status': 'GENERATED_STRUCTURE_VALID',
                'generation_executed': True, 'usage': {'latency_ms': 0}}, response={'owned': True})

    class Validator:
        def __init__(self, *args):
            pass
        def validate(self, *args, **kwargs):
            step('post')
            return {'semantic_status': 'PENDING_REVIEW'}

    result = {'owned': True}
    qrow = {'question_id': 'M9-Q01', 'request_sha256': 'a' * 64, 'M8_package_sha256': 'b' * 64,
            'per_question_cap_usd': '.03', 'M7_result_sha256': 'd' * 64}
    plan = {'questions': [qrow], 'preflight_manifest': 'owned/MANIFEST.json',
            'aggregate_cap_usd': '1.00', 'plan_sha256': 'c' * 64}
    store = SimpleNamespace(verified={}, json=lambda _: result)
    monkeypatch.setattr(runner, 'build_plan', lambda *a, **kw: (plan, store, {'M9-Q01': {'question': 'Owned?'}}))
    monkeypatch.setattr(runner, 'verify_bindings', lambda *a: None)
    monkeypatch.setattr(preparation, 'configuration', lambda *a, **kw: (None, None, None))
    monkeypatch.setattr(preparation, 'validate_candidates', lambda *a: step('candidate-validation'))
    def assembling(evidence, gate, *args):
        preparation.validate_candidates()
        package = evidence.assemble()
        return package, gate.prepare()
    monkeypatch.setattr(preparation, 'assemble', assembling)
    monkeypatch.setattr(preparation, 'recipe', lambda *a: (result, result))
    monkeypatch.setattr(preparation, 'equivalence', lambda *a: None)
    monkeypatch.setattr(preparation, 'source_transfer_check', lambda *a: None)
    monkeypatch.setattr(evidence_module, 'EvidenceService', Evidence)
    monkeypatch.setattr(generation_module, 'GenerationService', Service)
    monkeypatch.setattr(gate_module, 'PromptAssemblyGate', Gate)
    monkeypatch.setattr(post_module, 'PostGenerationValidator', Validator)
    monkeypatch.setattr(runner, 'OfflineAdapter', Adapter)
    run = runner.execute(tmp_path, mode='mock', selected=['M9-Q01'], progress=lambda *a, **kw: None)
    timing = json.loads((run / 'questions/M9-Q01/STAGE_TIMINGS.json').read_bytes())
    assert timing['error_stage'] == expected
    assert 'PRIVATE_ARGUMENTS' not in json.dumps(timing)
    assert not list(tmp_path.rglob('*ATTEMPT.json'))
    manifest = json.loads((run / 'MANIFEST.json').read_bytes())
    assert 'questions/M9-Q01/STAGE_TIMINGS.json' in manifest['files']
    if failure is None:
        assert calls == ['candidate-validation', 'm8', 'source-validation', 'prompt',
                         'source-validation', 'prompt', 'preflight', 'count', 'generation', 'post', 'check']
        stages = {s['stage']: s for s in timing['stages']}
        assert all(stages[s]['status'] == 'MEASURED' for s in (
            'SAVED_INPUT_VERIFICATION', 'M8_EVIDENCE_ASSEMBLY', 'M8_SOURCE_VALIDATION',
            'PROMPT_ASSEMBLY', 'MODEL_PREFLIGHT', 'MODEL_METADATA', 'MODEL_TOKEN_COUNT',
            'LLM_GENERATION', 'POST_GENERATION_VALIDATION', 'ARTIFACT_PERSISTENCE'))


def test_historical_absence_and_tampered_timing_fail_closed(tmp_path):
    from tools.generation_runner.dashboard import discover
    from tools.generation_runner.plan import VERSION
    from tools.generation_runner.tests.test_history import publish
    from tools.generation_runner.timing import StageTimer
    from tools.preflight_suite.artifacts import sha
    run = publish(tmp_path)
    assert discover(tmp_path)['runs'][0]['timings'] == {}
    # New independent publication; no rewrite of the historical one.
    new = run.parent / 'owned-timed'
    plan = {'owned': True}
    plan['plan_sha256'] = digest(plan)
    row = {'question_id': 'R01', 'mode': 'mock', 'provider_calls': 0, 'generation_executed': False,
           'request_sha256': 'a' * 64, 'M8_package_sha256': 'b' * 64,
           'stage_timings': 'questions/R01/STAGE_TIMINGS.json'}
    save(new / 'PLAN.json', plan)
    timer = StageTimer('R01', new.name, 'mock')
    runner.persist_question(new / 'questions/R01', row, timer)
    save(new / 'RESULTS.json', {'mode': 'mock', 'questions': [row]})
    save(new / 'MANIFEST.json', {'schema': VERSION, 'run_id': new.name, 'mode': 'mock',
        'status': 'SEALED_PENDING_OWNER_REVIEW', 'plan_sha256': plan['plan_sha256'],
        'question_ids': ['R01'], 'files': {p.relative_to(new).as_posix(): sha(p) for p in new.rglob('*') if p.is_file()}})
    assert len(discover(tmp_path)['runs']) == 2
    (new / 'questions/R01/STAGE_TIMINGS.json').write_text('{}')
    found = discover(tmp_path)
    assert len(found['runs']) == 1 and found['rejected'][0]['run_id'] == new.name
