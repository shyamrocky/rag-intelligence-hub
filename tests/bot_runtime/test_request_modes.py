"""Actual 8516 mode/draft/status UI; all execution and approval boundaries owned."""
import socket
from pathlib import Path

import pytest

AppTest = pytest.importorskip('streamlit.testing.v1').AppTest
pytest.importorskip('tools')

from apps.knowledge_preparation import bot_chat, bot_live, bot_records
from tools.bot_runtime import chat_records, dispatch, store

ROOT = Path(__file__).resolve().parents[2]
QUESTION = 'How do keyword and vector search work together?'


@pytest.fixture
def ui(monkeypatch):
    state = {'enabled': True, 'calls': [], 'control': None, 'attempt': None}
    def denied(*a, **kw):
        raise AssertionError('NO_REAL_NETWORK_OR_EXECUTION')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr('tools.preflight_suite.provider.load_key', denied)
    monkeypatch.setattr('tools.generation_runner.bot_chat.enable', denied)
    monkeypatch.setattr('tools.generation_runner.bot_chat.execute', denied)
    monkeypatch.setattr('tools.human_review.local_poc.require_localhost', lambda: None)
    monkeypatch.setattr(bot_chat, 'state', lambda *a: {'enabled': state['enabled'], 'blocked': False,
        'settings': {'per_question_cap_usd': '0.03', 'total_bot_cap_usd': '1.00'},
        'budget': {'remaining_usd': '0.97'}})
    def approvals():
        import streamlit as st
        st.info('Owned existing approval controls')
        if st.button('Enable live chat'):
            state['enabled'] = True
            st.rerun()
    monkeypatch.setattr(bot_chat, 'controls', approvals)
    monkeypatch.setattr(bot_live, 'render', lambda **kw: None)
    monkeypatch.setattr(bot_live, 'prepare_next', lambda *a: state['calls'].append('prepare-next'))
    def register(root, text, nonce):
        state['calls'].append(('register', text, nonce))
        return {'question_id': 'BOT-999991'}
    monkeypatch.setattr(store, 'register', register)
    def execute(root, qid, mode, **kw):
        import streamlit as st
        assert st.session_state['bot-ui-request']['state'] == 'PROCESSING'
        state['calls'].append(mode)
        if mode == 'chat':
            if state['control'] is None:
                state['control'] = {'status': 'COMPLETED'}
            state['attempt'] = {'mode': 'live', 'execution_status': 'COMPLETED',
                'response': {'status': 'ANSWERED', 'answer': '**Owned synthetic answer.**'}}
        else:
            state['attempt'] = {'mode': 'local-check', 'execution_status': 'AWAITING_AUTHORIZATION',
                'application_outcome': 'LOCAL_ASSEMBLED_NOT_MODEL_QUALIFIED'}
        return {'question_id': qid, 'mode': mode}
    monkeypatch.setattr(dispatch, 'native', execute)
    def simulate(*a, **kw):
        state['calls'].append('mock')
        state['attempt'] = {'mode': 'mock', 'execution_status': 'COMPLETED'}
    monkeypatch.setattr(dispatch, 'simulate', simulate)
    monkeypatch.setattr(dispatch, 'completed', lambda *a: state['attempt'])
    monkeypatch.setattr(chat_records, 'record', lambda *a: state['control'])
    monkeypatch.setattr(bot_records, 'show_attempt', lambda *a: None)
    state['app'] = lambda: AppTest.from_file(str(ROOT/'apps/knowledge_preparation/app.py')).run()
    return state


def selector(app):
    return next(r for r in app.radio if r.label == 'Request mode')


def test_default_chat_has_no_approval_forms_or_mode_toggles(ui):
    app = ui['app']()
    assert not app.exception
    assert selector(app).value == 'Chat'
    assert not app.form and not app.toggle
    assert not any(b.label == 'Enable live chat' for b in app.button)
    assert not any(c.value.startswith('Mode:') for c in app.caption)
    assert not ui['calls']
    app.run()
    assert not ui['calls']


def test_chat_send_acknowledges_and_dispatches_exactly_once(ui):
    app = ui['app']()
    app.chat_input[0].set_value(QUESTION).run()
    assert not app.exception, app.exception
    assert [c if isinstance(c, str) else c[0] for c in ui['calls']] == ['register', 'chat']
    assert app.session_state['bot-ui-request']['state'] == 'COMPLETED'
    assert any('Answer received' in i.value for i in app.info)
    assert any('Owned synthetic answer' in m.value for m in app.markdown)
    assert any(m.value == QUESTION for m in app.markdown)
    assert app.session_state['bot-ui-request']['question'] == QUESTION
    assert app.chat_input[0].disabled
    app.run()
    assert len(ui['calls']) == 2


def test_unverified_readiness_send_records_stop_instead_of_asking_to_enable(ui):
    ui['enabled'] = False
    ui['control'] = {'status': 'BLOCKED', 'finding': {
        'message': 'This request stopped at a safety check.', 'generation_attempted': False,
        'cost_status': 'GENERATION_NOT_ATTEMPTED'}}
    app = ui['app']()
    assert not any('Live chat is off' in i.value for i in app.info)
    app.chat_input[0].set_value(QUESTION).run()
    assert not app.exception and ui['calls'][-1] == 'chat'
    assert app.session_state['bot-ui-request']['state'] == 'STOPPED'
    assert any('safety check' in w.value for w in app.warning)


def test_developer_mode_change_preserves_draft_never_auto_sends(ui):
    app = ui['app']()
    app.chat_input[0].set_value(QUESTION)
    selector(app).set_value('Request Approvals / Triage').run()
    assert not app.exception and not ui['calls'] and app.chat_input[0].disabled
    assert app.session_state['bot-question-draft'] == QUESTION
    selector(app).set_value('Chat').run()
    assert not app.exception and not ui['calls']
    app.chat_input[0].set_value(QUESTION).run()
    assert not app.exception and ui['calls'][-1] == 'chat' and len(ui['calls']) == 2


def test_mode_and_pending_send_cannot_silently_change_execution_mode(ui):
    app = ui['app']()
    app.chat_input[0].set_value(QUESTION)
    selector(app).set_value('Offline Simulation').run()
    assert not app.exception and not ui['calls']
    assert app.chat_input[0].disabled
    assert app.session_state['bot-question-draft'] == QUESTION
    from streamlit.testing.v1.errors import AppTestError
    with pytest.raises(AppTestError, match='disabled'):
        app.chat_input[0].set_value(QUESTION)
    assert not app.exception and not ui['calls']
    selector(app).set_value('Chat').run()
    assert not app.exception and not app.chat_input[0].disabled and not ui['calls']
    app.chat_input[0].set_value(QUESTION).run()
    assert not app.exception and ui['calls'][-1] == 'chat'


@pytest.mark.parametrize('mode', ['Request Approvals / Triage', 'Offline Simulation'])
def test_developer_modes_are_exclusive_and_chat_composer_is_disabled(ui, mode):
    app = ui['app']()
    selector(app).set_value(mode).run()
    assert not app.exception
    assert selector(app).value == mode and len(app.radio) == 1 and not app.toggle
    assert app.chat_input[0].disabled
    assert not ui['calls']
    app.run()
    assert not ui['calls']


@pytest.mark.parametrize('status', ['BLOCKED', 'FAILED', 'REVIEW_REQUIRED'])
def test_stop_or_review_status_is_visible_without_resubmission(ui, status):
    ui['control'] = {'status': status, 'finding': {'message': 'Owned saved stop reason.',
        'generation_attempted': False, 'cost_status': 'GENERATION_NOT_ATTEMPTED'}}
    app = ui['app']()
    app.chat_input[0].set_value(QUESTION).run()
    assert not app.exception, app.exception
    assert app.session_state['bot-ui-request']['state'] == ('REVIEW_REQUIRED' if status == 'REVIEW_REQUIRED' else 'STOPPED')
    assert any('Owned saved stop reason' in w.value for w in app.warning)
    app.run()
    assert len(ui['calls']) == 2


def test_new_chat_clears_only_display_and_draft(ui):
    app = ui['app']()
    app.chat_input[0].set_value(QUESTION).run()
    next(b for b in app.button if b.label == 'New chat').click().run()
    assert not app.exception
    assert 'bot-active-id' not in app.session_state
    assert 'bot-question-draft' not in app.session_state
    assert not app.chat_input[0].disabled
    assert ui['enabled'] and len(ui['calls']) == 2


def test_guidance_holds_details_and_controls_follow_requested_order(ui):
    app = ui['app']()
    assert not app.exception
    panels = app.main.expander
    assert [p.label for p in panels[:2]] == ['Guidance & limits', 'Developer settings']
    assert not panels[0].proto.expanded and not panels[1].proto.expanded
    labels = [getattr(e, 'label', None) for e in app.main]
    assert labels.index('Guidance & limits') < labels.index('Developer settings') < labels.index('New chat')
    guidance = panels[0]
    for fragment in ['Chat ready', 'Available after existing reservations', 'Send authorizes',
                     'Execution records are retained', 'Preparing a grounded answer can take a couple of minutes']:
        assert any(fragment in c.value for c in guidance.caption)
        assert sum(fragment in c.value for c in app.caption) == 1
    assert any('To ask another question after receiving an answer, click New chat.' in c.value for c in app.caption)
    assert not any('A fresh start every time' in c.value for c in app.caption)
    assert sum('Ask a question about RAG.' in m.value for m in app.markdown) == 1
    assert not any('A simpler way to explore' in m.value for m in app.markdown)
    assert not ui['calls']


def test_question_is_visible_above_processing_and_persists_after_completion(ui, monkeypatch):
    import streamlit as st

    from tools.bot_runtime import dispatch
    def process(root, qid, mode, **kw):
        # Observe the actual render order before the runner boundary is called.
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        assert ctx is not None
        assert st.session_state['bot-ui-request']['question'] == QUESTION
        assert st.session_state['bot-ui-request']['state'] == 'PROCESSING'
        ui['calls'].append('chat')
        ui['control'] = {'status': 'COMPLETED'}
        ui['attempt'] = {'mode': 'live', 'execution_status': 'COMPLETED',
            'response': {'status': 'ANSWERED', 'answer': 'Synthetic answer below the question.'}}
        return {'mode': mode}
    monkeypatch.setattr(dispatch, 'native', process)
    app = ui['app']()
    app.chat_input[0].set_value(QUESTION).run()
    assert not app.exception
    assert sum(c.value == 'Your question' for c in app.caption) == 1
    # Main-tree iteration follows display order, including nested question block.
    text = [getattr(e, 'value', '') for e in app.main]
    question_index = text.index(QUESTION, text.index('Your question'))
    assert question_index < next(i for i,v in enumerate(text) if isinstance(v,str) and v.startswith('Answer received'))
    assert question_index < text.index('Synthetic answer below the question.')
    app.run()
    assert not app.exception and len(ui['calls']) == 2
    assert any(m.value == QUESTION for m in app.markdown)
    next(b for b in app.button if b.label == 'New chat').click().run()
    assert not app.exception
    assert not any(c.value == 'Your question' for c in app.caption)
    assert 'bot-ui-request' not in app.session_state
