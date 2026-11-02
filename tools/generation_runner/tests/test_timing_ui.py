"""Actual canonical AppTest; read-only page navigation must not execute stages."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]


def test_canonical_latency_and_historical_absence(monkeypatch):
    import socket

    from tools.evidence.service import EvidenceService
    from tools.generation.current import GenerationService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.generation_runner import runner
    from tools.pre_generation_gate.current import PromptAssemblyGate
    from tools.quality_dashboard.post_generation import PostGenerationValidator
    from tools.retrieval.service import RetrievalService

    def denied(*args, **kwargs):
        raise AssertionError('TIMING_UI_MUST_NOT_EXECUTE_STAGES')

    for cls, methods in [(EvidenceService, ['assemble', 'validate']),
        (GenerationService, ['dry_run', 'generate']),
        (OpenAIAdapter, ['configuration_error', '_sdk', 'verify_model', 'count', 'invoke']),
        (PromptAssemblyGate, ['prepare']), (PostGenerationValidator, ['validate']),
        (RetrievalService, ['search'])]:
        for method in methods:
            monkeypatch.setattr(cls, method, denied)
    monkeypatch.setattr(runner, 'execute', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    app = AppTest.from_file(str(ROOT / 'apps/master_dashboard/canonical.py'), default_timeout=120).run()
    app.switch_page('views/generation_runner.py').run()
    assert not app.exception
    runs = app.session_state['generation_runner_telemetry']['runs']
    timed = [r for r in runs if r.get('timings', {}).get('M9-Q01')]
    assert timed and timed[-1]['manifest']['question_ids'] == ['M9-Q01']
    run = timed[-1]
    select = next(s for s in app.selectbox if s.label == 'Generation runner run')
    select.select(runs.index(run)).run()
    assert not app.exception
    assert any(m.label == 'Question end-to-end elapsed' for m in app.metric)
    assert any('MOCK_ADAPTER_DURATION' in c.value for c in app.caption)
    assert any('Slowest measured stage: M8_EVIDENCE_ASSEMBLY' in c.value for c in app.caption)
    tables = [d.value for d in app.dataframe]
    assert any('Exclusive ms' in t.columns for t in tables)
    next(b for b in app.button if b.label == 'Refresh verified telemetry').click().run()
    assert not app.exception
    app.switch_page('views/preflight_quality.py').run()
    assert not app.exception
    assert app.session_state['expanded_data']['summary']['generation_completed'] == 1
    assert app.session_state['expanded_data']['summary']['pending_generation'] == 33
    selector = next(s for s in app.selectbox if s.label == 'Shared question')
    selector.select('M9-Q01').run()
    assert not app.exception
    assert app.title[0].value == 'End-to-End Quality & Telemetry'
    assert app.tabs[0].label == 'Retrieval Pipeline Telemetry'
    assert any(m.label == 'Question end-to-end elapsed' for m in app.tabs[0].metric)
    assert app.tabs[0].subheader[0].value == 'Execution Latency Breakdown'
    assert not any(e.label.startswith('Stage-level latency —') for e in app.expander)
    next(s for s in app.selectbox if s.label == 'Shared question').select('M9-Q05').run()
    assert not app.exception
    assert any('NOT_MEASURED' in i.value for i in app.info)
    assert app.session_state['expanded_data']['records']['M9-Q05']['latest']['usage']['total_estimated_cost_usd'] == '0.011198925'
    next(s for s in app.selectbox if s.label == 'Generation status').select('COMPLETED').run()
    assert app.session_state['expanded_question'] == 'M9-Q05'
    next(b for b in app.button if b.label == 'Show measured stage timings: M9-Q01').click().run()
    assert not app.exception
    assert app.session_state['expanded_question'] == 'M9-Q01'
    assert app.session_state['expanded_generation_filter'] == 'All'
    assert any(m.label == 'Question end-to-end elapsed' for m in app.tabs[0].metric)
    app.switch_page('views/explorer.py').run()
    assert not app.exception and app.get('iframe')


def test_incomplete_timing_display_has_null_skipped_stages():
    # Explicit owned UI control, not a real retrieval/LLM result.
    code = """
from tools.generation_runner.dashboard import render_latency
from tools.generation_runner.timing import StageTimer
import streamlit as st
t = StageTimer('owned', 'owned-run', 'mock')
with t.span('SAVED_INPUT_VERIFICATION'):
    pass
v = t.finish(request_sha256='a'*64, package_sha256='b'*64)
render_latency(st, {'timings': {'owned': v},
    'manifest_path': 'data/owned/MANIFEST.json',
    'manifest': {'files': {'questions/owned/STAGE_TIMINGS.json': 'c'*64}}}, 'owned')
"""
    app = AppTest.from_string(code).run()
    assert not app.exception
    table = app.dataframe[0].value
    skipped = table[table['Status'] == 'SKIPPED']
    assert not skipped.empty and skipped['Exclusive ms'].isna().all()
    assert any('MOCK_ADAPTER_DURATION' in c.value for c in app.caption)
