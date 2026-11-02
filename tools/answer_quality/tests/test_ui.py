"""Real Streamlit rendering with every execution/provider boundary denied."""
from pathlib import Path

import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]


def test_q04_v2_quality_view_and_refresh_are_read_only(monkeypatch):
    from tools.answer_quality.validator import PostGenerationValidator
    from tools.evidence.service import EvidenceService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.generation_runner import runner

    def denied(*a, **kw):
        pytest.fail('DASHBOARD_MUST_NOT_EXECUTE_PIPELINE')
    for cls, methods in [(PostGenerationValidator, ['validate']), (EvidenceService, ['assemble', 'validate']),
                         (OpenAIAdapter, ['verify_model', 'count', 'invoke'])]:
        for method in methods:
            monkeypatch.setattr(cls, method, denied)
    for name in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo',
                 'tools.preflight_suite.provider.load_key'):
        monkeypatch.setattr(name, denied)
    monkeypatch.setattr(runner, 'execute', denied)
    app = AppTest.from_file(str(ROOT / 'apps/master_dashboard/canonical.py'), default_timeout=120).run()
    assert not app.exception
    app.switch_page('views/generation_runner.py').run()
    assert not app.exception
    runs = app.session_state['generation_runner_telemetry']['runs']
    native = next(i for i, r in enumerate(runs) if r['manifest']['run_id'] == '20261029T080808-live-143c62d120f7')
    next(s for s in app.selectbox if s.label == 'Generation runner run').select(native).run()
    assert not app.exception
    assert any(s.value == 'Answer quality — validation v2' for s in app.subheader)
    assert any('REVIEW_REQUIRED' in str(s.value) for s in app.markdown)
    assert len(app.session_state['expanded_data']['records']) == 34
    next(b for b in app.button if b.label == 'Refresh verified telemetry').click().run()
    assert not app.exception
    assert not any(b.label.lower() in {'generate', 'execute', 'run live'} for b in app.button)
    # Historical Q05 and preflight remain visible with unchanged legacy counters.
    assert app.session_state['expanded_data']['records']['M9-Q05']['latest']['usage']['total_estimated_cost_usd'] == '0.011198925'
