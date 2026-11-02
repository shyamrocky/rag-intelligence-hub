"""Actual Streamlit execution, with all pipeline/provider entry points forbidden."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'apps/master_dashboard/preflight.py'


def forbidden(*args, **kwargs):
    raise AssertionError('DASHBOARD_MUST_NOT_EXECUTE_PIPELINE_OR_NETWORK')


def test_navigation_refresh_and_question_history(monkeypatch):
    import socket

    from tools.evidence.service import EvidenceService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.pre_generation_gate.current import PromptAssemblyGate
    from tools.preflight_suite import runner
    from tools.retrieval.service import RetrievalService

    for cls, name in [(EvidenceService, 'assemble'), (EvidenceService, 'validate'),
                      (OpenAIAdapter, 'verify_model'), (OpenAIAdapter, 'count'),
                      (OpenAIAdapter, 'invoke'), (PromptAssemblyGate, 'prepare'),
                      (RetrievalService, 'search')]:
        monkeypatch.setattr(cls, name, forbidden)
    monkeypatch.setattr(runner, 'execute', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    app = AppTest.from_file(str(APP), default_timeout=90).run()
    assert not app.exception
    assert len(app.session_state['expanded_data']['records']) == 34
    assert app.session_state['expanded_data']['summary']['pending_generation'] == 33
    app.switch_page('views/preflight_suite.py').run()
    assert not app.exception
    if app.session_state['preflight_telemetry']['runs']:
        select = next(x for x in app.selectbox if x.label == 'Preflight question')
        assert len(select.options) == 33
        select.select('R03').run()
        assert not app.exception and app.session_state['expanded_question'] == 'R03'
        assert not any(b.label in {'Run', 'Execute', 'Model preflight'} for b in app.button)
    app.switch_page('views/preflight_quality.py').run()
    assert not app.exception
    assert len(next(x for x in app.selectbox if x.label == 'Shared question').options) == 34
    assert any('INSUFFICIENT RELEVANCE LABELS' in x.value for x in app.warning)
    app.switch_page('views/explorer.py').run()
    assert not app.exception and 'RAG Retrieval Pipeline Explorer' in str(app.get('iframe')[0].proto)
