"""Real canonical Streamlit readback, with all pipeline operations denied."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]


def test_rollout_page_readonly(monkeypatch):
    import socket

    from tools.evidence.service import EvidenceService
    from tools.generation.current import GenerationService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.generation_runner import runner
    from tools.pre_generation_gate.current import PromptAssemblyGate

    def denied(*args, **kwargs):
        raise AssertionError('ROLLOUT_UI_CANNOT_EXECUTE')

    for owner, names in [(EvidenceService, ['assemble', 'validate']),
        (GenerationService, ['dry_run', 'generate']),
        (OpenAIAdapter, ['_sdk', 'verify_model', 'count', 'invoke']),
        (PromptAssemblyGate, ['prepare'])]:
        for name in names:
            monkeypatch.setattr(owner, name, denied)
    monkeypatch.setattr(runner, 'execute', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    app = AppTest.from_file(str(ROOT / 'apps/master_dashboard/canonical.py'), default_timeout=120).run()
    app.switch_page('views/generation_runner.py').run()
    assert not app.exception
    assert any('Controlled generation rollout' in x.value for x in app.subheader)
    stage_table = next(t.value for t in app.dataframe
                       if {'Stage', 'Questions', 'Maximum projected USD'} <= set(t.value.columns))
    assert list(stage_table['Questions']) == [1, 4, 28]
    assert set(stage_table['Status']) == {'PENDING_OWNER_APPROVAL'}
    details = next(t.value for t in app.dataframe if 'actual_output_tokens' in t.value.columns)
    assert len(details) == 33
    assert details['actual_output_tokens'].isna().all()
    assert set(details['generation']) == {'NOT_RUN'}
    assert not any(b.label.lower() in {'generate', 'execute', 'live'} for b in app.button)
    next(b for b in app.button if b.label == 'Refresh verified telemetry').click().run()
    assert not app.exception
    app.switch_page('views/preflight_quality.py').run()
    assert not app.exception
    data = app.session_state['expanded_data']
    assert data['summary']['generation_completed'] == 1
    assert data['records']['M9-Q05']['latest']['usage']['total_estimated_cost_usd'] == '0.011198925'
