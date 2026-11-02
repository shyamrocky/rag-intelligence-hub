"""Final UI/CLI integration controls; owned fixtures, never provider execution."""
from pathlib import Path
from uuid import uuid4

import pytest

AppTest = pytest.importorskip('streamlit.testing.v1').AppTest
pytest.importorskip('tools')
pytest.importorskip('httpx')

from streamlit.util import calc_hash

from apps.knowledge_preparation import bot_records, run_summary
from tools.bot_runtime import dispatch, projection, store
from tools.generation_runner import bot_runtime

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fixture_root(tmp_path, monkeypatch):
    monkeypatch.setattr('tools.bot_runtime.trust.verify_implementation', lambda root: {'path': 'OWNED', 'sha256': 'a' * 64, 'generation_authority': False})
    q = store.register(tmp_path, 'Explain synthetic retrieval.', uuid4().hex)
    bot_runtime.execute(tmp_path, q['question_id'], mode='mock', scenario='partial')
    monkeypatch.setattr(bot_records, 'ROOT', tmp_path)
    monkeypatch.setattr(run_summary, 'load_bots', lambda root: projection.discover(tmp_path))
    return tmp_path


@pytest.mark.parametrize('route', ['knowledge-retrieval', 'pre-generation', 'generation',
                                    'post-generation-evaluation-human-review', 'human-review'])
def test_actual_routes_render_bot_without_pipeline(fixture_root, monkeypatch, route):
    def denied(*a, **kw):
        raise AssertionError('NO_EXECUTION_ON_NAVIGATION')
    monkeypatch.setattr(bot_runtime, 'execute', denied)
    monkeypatch.setattr(dispatch, 'simulate', denied)
    app = AppTest.from_file(str(ROOT / 'apps/knowledge_preparation/app.py'), default_timeout=120)
    app._page_hash = calc_hash(route)
    app.session_state['workspace-question-source'] = 'Bot questions'
    app.run()
    assert not app.exception, app.exception
    assert any(s.label == 'Bot question' and s.value == 'BOT-000001' for s in app.selectbox)
    assert app.radio[0].value == 'Bot questions'
    app.run()
    assert not app.exception


def test_mode_switch_new_chat_and_reentry_preserve_existing_records(fixture_root, monkeypatch):
    def denied(*a, **kw):
        raise AssertionError('MODE_SELECTION_CANNOT_EXECUTE')
    monkeypatch.setattr(dispatch, 'simulate', denied)
    monkeypatch.setattr(dispatch, 'native', denied)
    monkeypatch.setattr(dispatch, 'completed', lambda root, qid: projection.discover(fixture_root)['records'][qid]['attempts'][-1])
    app = AppTest.from_file(str(ROOT / 'apps/knowledge_preparation/app.py'), default_timeout=120).run()
    next(r for r in app.radio if r.label == 'Request mode').set_value('Offline Simulation').run()
    assert not app.exception and app.chat_input[0].disabled
    app.session_state['bot-active-id'] = 'BOT-000001'
    app.run()
    assert not app.exception
    next(b for b in app.button if b.label == 'New chat').click().run()
    assert not app.exception
    assert 'bot-active-id' not in app.session_state
    assert app.chat_input[0].disabled
    next(r for r in app.radio if r.label == 'Request mode').set_value('Chat').run()
    assert not app.exception and not app.chat_input[0].disabled
    assert len(projection.discover(fixture_root)['records']) == 1
