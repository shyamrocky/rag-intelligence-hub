"""Native authorization/admission flow, disposable fixtures, no real provider or keys."""
import json
from types import SimpleNamespace

import pytest
from test_stage_policies import fake_pipeline, run_synthetic, synthetic_approval
from test_stage_policies import owned as owned  # noqa: PLC0414
from test_stage_policies import stages as stages  # noqa: PLC0414

from tools.generation.observation import observe
from tools.generation.response_capture import ResponseCapture


@pytest.mark.parametrize('failure', [None, 'unknown_billing', 'capture', 'source', 'model', 'persistence'])
def test_native_quality_failures_continue_but_safety_stops(stages, monkeypatch, failure):
    from tools.generation_runner import live
    from tools.preflight_suite import runner as prep
    s = stages['pilot']
    path, h = synthetic_approval(s, 'owned-continuation-fixture')
    fake_pipeline(monkeypatch, s)
    monkeypatch.setattr(prep, 'configuration', lambda *a, **kw:
        (SimpleNamespace(max_output_tokens=4096, model='owned-model'), None, None))
    package = {'parents': [], 'counts': {'selected_parents': 0}, 'budget': {'exact_llm_evidence_tokens': 0}}
    monkeypatch.setattr(prep, 'assemble', lambda *a: (package, SimpleNamespace(audit={})))
    calls = []
    class Adapter:
        def __init__(self, root, qdir, row):
            self.row, self.qdir = row, qdir
            self.capture = ResponseCapture(root, qdir, question_id=row['question_id'], run_id=qdir.parent.parent.name,
                request_sha256=row['request_sha256'], package_sha256=row['M8_package_sha256'], mode='live')
        def verify_model(self): pass
        def count(self): pass
        def invoke(self): pass
    def create(root, qdir, request, row, budget, *a, trust_guard, **kw):
        trust_guard()
        return Adapter(root, qdir, row), None, None
    class Service:
        def __init__(self, gate, adapter, **kw): self.adapter = adapter
        def dry_run(self): pass
        def generate(self, *a, **kw):
            adapter = self.adapter; row = adapter.row
            calls.append(row['question_id'])
            raw = {'model': 'owned-model', 'status': 'completed', 'output': [{'type': 'message',
                'content': [{'type': 'output_text', 'text': '{"status":"ANSWERED","answer":"Owned candidate","claims":[]}'}]}]}
            self.last_observation = observe(raw)
            receipt = adapter.capture.capture(json.dumps(raw).encode(), http_status=200)
            if failure == 'capture': receipt['status'] = 'RAW_RESPONSE_CAPTURE_FAILED'; receipt['artifact'] = None
            usage = {'cost_status': 'ESTIMATED_API_COST', 'input_tokens': row['input_tokens'],
                'output_tokens': 10, 'total_tokens': row['input_tokens'] + 10, 'total_estimated_cost_usd': '0.001'}
            if failure == 'unknown_billing': usage['cost_status'] = 'COST_UNAVAILABLE'
            return SimpleNamespace(response=None, audit={'status': 'BLOCKED_INTEGRITY' if failure == 'source'
                else 'INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE', 'generation_executed': True,
                'model': 'other' if failure == 'model' else 'owned-model', 'response_status': 'completed',
                'request_sha256': row['request_sha256'], 'M8_package_sha256': row['M8_package_sha256'],
                'raw_response_capture': receipt, 'usage': usage,
                'response_diagnostics': [{'code': 'SCHEMA_OR_RELATIONSHIP_INVALID', 'path': []}]})
    monkeypatch.setattr(live, 'create', create)
    monkeypatch.setattr('tools.generation.current.GenerationService', Service)
    if failure == 'persistence':
        monkeypatch.setattr('tools.generation_runner.review_material.retain',
                            lambda *a, **kw: (_ for _ in ()).throw(OSError('Owned failure')))
    run = run_synthetic(s, path, h)
    result = json.loads((run / 'RESULTS.json').read_bytes())
    assert len(calls) == (1 if failure else 4)
    assert result['completed'] == len(calls)
    assert len(result['planned_outcomes']) == 4
    if failure:
        assert result['planned_outcomes'][1]['status'] == 'NOT_RUN_SAFETY_STOP'
    else:
        assert all(q['post_validation']['structural_validation'] == 'FAIL' for q in result['questions'])
        assert all(q['response'] is None for q in result['questions'])
        assert all((run / 'questions' / q['question_id'] / 'BATCH_DISPOSITION.json').is_file()
                   for q in result['questions'])
    with pytest.raises(ValueError):
        run_synthetic(s, path, h)
