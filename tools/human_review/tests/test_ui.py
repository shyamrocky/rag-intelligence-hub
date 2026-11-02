"""Actual Streamlit forms using disposable synthetic reviewers, never the owner."""

import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

from tools.human_review.workflow import confirmation_text, verify_decision

from .conftest import PASSWORD, REVIEWER


def app_for(c):
    script = ("from pathlib import Path\nimport streamlit as st\n"
              "from tools.human_review.ui import render\n"
              f"render(st, Path({str(c['root'])!r}), credential_store=Path({str(c['store'])!r}))\n")
    return AppTest.from_string(script, default_timeout=120).run()


@pytest.mark.parametrize('label,outcome,expected', [('Approve', 'APPROVE', 'VALIDATED'),
    ('Reject', 'REJECT', 'VALIDATION_FAILED'), ('Request Changes', 'REQUEST_CHANGES', 'REVIEW_REQUIRED')])
def test_buttons_authenticate_and_publish_separate_evaluation(context, label, outcome, expected):
    c = context
    app = app_for(c)
    assert not app.exception
    assert {b.label for b in app.button} == {'Approve', 'Reject', 'Request Changes'}
    app.text_input(key='human_review_reviewer').input(REVIEWER)
    app.text_input(key='human_review_secret').input(PASSWORD)
    app.text_input(key='human_review_confirmation').input(confirmation_text(outcome, c['row']['question_id'], c['sha']))
    app.checkbox(key='human_review_confirmed').check()
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception
    files = list(c['root'].glob('data/evals/answer-quality/human-review-*/MANIFEST.json'))
    assert len(files) == 1
    body, result = verify_decision(c['root'], c['store'], files[0].relative_to(c['root']).as_posix())
    assert body['outcome'] == outcome and result['overall_status'] == expected
    assert not app.session_state['human_review_secret']
    assert all(b.disabled for b in app.button)
    app.run()
    assert not app.exception and len(files) == 1


@pytest.mark.parametrize('missing', ['password', 'confirmation', 'checkbox'])
def test_name_or_button_alone_cannot_authenticate(context, missing):
    c = context
    app = app_for(c)
    app.text_input(key='human_review_reviewer').input(REVIEWER)
    app.text_input(key='human_review_secret').input('' if missing == 'password' else PASSWORD)
    app.text_input(key='human_review_confirmation').input('' if missing == 'confirmation' else
        confirmation_text('APPROVE', c['row']['question_id'], c['sha']))
    if missing != 'checkbox':
        app.checkbox(key='human_review_confirmed').check()
    next(b for b in app.button if b.label == 'Approve').click().run()
    assert not app.exception
    assert not list(c['root'].glob('data/evals/answer-quality/human-review-*'))
    assert any('not accepted' in str(i.value) for i in app.info)


def test_navigation_and_refresh_never_execute_context_or_read_key(context, monkeypatch):
    from tools.human_review import identity, workflow
    def denied(*a, **kw):
        pytest.fail('REFRESH_MUST_NOT_EXECUTE_OR_SIGN')
    monkeypatch.setattr(workflow, 'live_context', denied)
    monkeypatch.setattr(identity, 'sign', denied)
    app = app_for(context)
    app.run()
    assert not app.exception
    assert not list(context['root'].glob('data/evals/answer-quality/human-review-*'))


def test_no_registration_ui_or_generation_control(context):
    app = app_for(context)
    assert not app.exception
    assert not any(b.label.lower() in {'register', 'generate', 'run live'} for b in app.button)


def test_missing_registration_disables_decisions(context):
    from tools.human_review.identity import default_store
    c = context
    script = ("from pathlib import Path\nimport streamlit as st\n"
              "from tools.human_review.ui import render\n"
              f"render(st, Path({str(c['root'])!r}), credential_store=Path({str(c['store'].parent / 'absent')!r}))")
    app = AppTest.from_string(script).run()
    assert not app.exception and all(b.disabled for b in app.button)
    assert any('NOT_REGISTERED' in str(w.value) for w in app.warning)
    assert not default_store().exists()  # This task must not enroll the real owner.

