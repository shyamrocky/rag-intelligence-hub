"""Real Streamlit rendering, no generation, source reconstruction or owner decisions."""
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

from tools.answer_quality.abstention import LABEL


@pytest.mark.parametrize('status,answer,reasons,label', [
    ('ABSTAINED', '', ['No production measurement was supplied.'], True),
    ('ABSTAINED', '', [], True),
    ('ANSWERED', '**Supported answer**', [], False),
    ('PARTIAL', '**Supported part**', ['Second aspect unavailable.'], False),
])
def test_response_rendering(status, answer, reasons, label):
    response = {'status': status, 'answer': answer, 'missing_information': reasons}
    value = AppTest.from_string('import streamlit as st\n'
        'from tools.answer_quality.abstention import render_response\n'
        f'render_response(st, {response!r})').run()
    assert not value.exception
    assert any(s.value == LABEL for s in value.subheader) == label
    if status == 'ABSTAINED':
        if reasons:
            assert any(m.value == reasons[0] for m in value.markdown)
        else:
            assert any('ABSTENTION_EXPLANATION_MISSING_OR_INVALID' in w.value for w in value.warning)
        assert any('ABSTAINED' in c.value and 'model-reported' in c.value for c in value.caption)
    else:
        assert any(m.value == answer for m in value.markdown)


def test_canonical_q27_human_review_and_runner_are_read_only():
    from tools.evidence.service import EvidenceService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.generation_runner import runner
    from tools.human_review import handoff, local_poc, preparation, workflow
    from tools.quality_dashboard.artifacts import sha

    root = Path(__file__).resolve().parents[3]
    pilot = root / 'data/evals/generation-runner/20261029T154158-live-a83ec5c6833f'
    if not pilot.exists():
        pytest.skip('Private sealed pilot absent.')
    paths = [p for parent in ['data/evals/generation-runner', 'data/evals/human-review',
                             'data/evals/generation'] for p in (root / parent).rglob('*.json')]
    before = {p: sha(p) for p in paths}
    def denied(*args, **kwargs):
        pytest.fail('READ_ONLY_OFFLINE_UI_BOUNDARY')
    with ExitStack() as stack:
        for obj, names in [(EvidenceService, ['assemble', 'validate']),
                           (OpenAIAdapter, ['invoke', 'count', 'verify_model']),
                           (runner, ['execute']), (workflow, ['prepare', 'live_context']),
                           (preparation, ['run', 'owner_decide']), (local_poc, ['decide'])]:
            for name in names:
                stack.enter_context(patch.object(obj, name, denied))
        for name in ['socket.socket.connect', 'socket.create_connection',
                     'tools.preflight_suite.provider.load_key']:
            stack.enter_context(patch(name, denied))
        stack.enter_context(patch.object(local_poc, 'local_access', lambda: {
            'bind': '127.0.0.1', 'headers': {'Host': '127.0.0.1:8514'}, 'peer': None}))
        app = AppTest.from_file(str(root / 'apps/master_dashboard/canonical.py'), default_timeout=120).run()
        app.switch_page('views/generation_runner.py').run()
        assert not app.exception
        entries = handoff.discover(root)['entries']
        q27 = next(i for i, e in enumerate(entries) if e['question_id'] == 'M9-Q27')
        reason = entries[q27]['row']['response']['missing_information']
        app.selectbox(key='handoff_entry').select(q27).run()
        assert not app.exception
        assert any(s.value == LABEL for s in app.subheader)
        assert all(any(m.value == r for m in app.markdown) for r in reason)
        assert 'Approved (Local POC)' in app.selectbox(key='handoff_entry').options[q27]
        assert all(b.disabled for b in app.button if b.label in {'Approve', 'Reject', 'Request Changes'})
        selected = next(s for s in app.selectbox if s.label == 'Generation runner run')
        pilot_index = next(i for i, run in enumerate(app.session_state['generation_runner_telemetry']['runs'])
                           if run['manifest']['run_id'] == pilot.name)
        selected.select(pilot_index).run()
        next(s for s in app.selectbox if s.label == 'Generation runner question').select('M9-Q27').run()
        assert not app.exception
        assert sum(s.value == LABEL for s in app.subheader) == 2
        app.run()
        assert not app.exception
    assert before == {p: sha(p) for p in paths}
