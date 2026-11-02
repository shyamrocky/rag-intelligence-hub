"""Actual canonical Streamlit execution. Every pipeline/provider operation forbidden."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]


def test_canonical_runner_page_and_refresh_are_read_only(monkeypatch):
    import socket

    from tools.evidence.service import EvidenceService
    from tools.generation.current import GenerationService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.generation_runner import runner
    from tools.pre_generation_gate.current import PromptAssemblyGate
    from tools.quality_dashboard.post_generation import PostGenerationValidator
    from tools.retrieval.service import RetrievalService

    def denied(*args, **kwargs):
        raise AssertionError('UI_CANNOT_EXECUTE_PIPELINE_OR_PROVIDER')

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
    assert not app.exception
    assert len(app.session_state['expanded_data']['records']) == 34
    app.switch_page('views/generation_runner.py').run()
    assert not app.exception
    runs = app.session_state['generation_runner_telemetry']['runs']
    assert runs and not app.session_state['generation_runner_telemetry']['rejected']
    assert any(r['manifest']['mode'] == 'dry-run' and len(r['plan']['questions']) == 33 for r in runs)
    assert all(not q['generation_executed'] for r in runs for q in r['results']['questions'])
    representative = next(r for r in runs if r['manifest']['mode'] == 'mock'
                          and set(r['manifest']['question_ids']) == {'M9-Q01', 'M9-Q27', 'R03'})
    assert representative['results']['mock_invocations'] == 3
    next(s for s in app.selectbox if s.label == 'Generation runner run').select(runs.index(representative)).run()
    assert not app.exception
    assert len(next(s for s in app.selectbox if s.label == 'Generation runner question').options) == 3
    assert not any(b.label.lower() in {'run', 'execute', 'generate', 'live'} for b in app.button)
    next(b for b in app.button if b.label == 'Refresh verified telemetry').click().run()
    assert not app.exception
    app.switch_page('views/preflight_suite.py').run()
    assert not app.exception
    assert len(next(s for s in app.selectbox if s.label == 'Preflight question').options) == 33
    app.switch_page('views/preflight_quality.py').run()
    assert not app.exception
    row = app.session_state['expanded_data']['records']['M9-Q05']
    assert row['latest']['usage']['total_estimated_cost_usd'] == '0.011198925'
    assert app.session_state['expanded_data']['summary']['generation_completed'] == 1
    app.switch_page('views/explorer.py').run()
    assert not app.exception and app.get('iframe')
