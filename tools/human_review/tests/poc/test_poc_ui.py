"""Real Streamlit form callbacks on owned evidence; no signing or provider operations."""
import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

from tools.human_review import local_poc


def app_for(c):
    code = ("from pathlib import Path\nimport streamlit as st\n"
            "from tools.human_review.poc_ui import render\n"
            f"render(st, Path({str(c['root'])!r}))")
    return AppTest.from_string(code, default_timeout=120).run()


@pytest.mark.parametrize('label,status', [('Approve', 'OWNER_APPROVED_POC'), ('Reject', 'OWNER_REJECTED_POC'),
                                        ('Request Changes', 'OWNER_REQUESTED_CHANGES_POC')])
def test_visible_functional_controls_without_registration(poc_context, label, status):
    c = poc_context
    app = app_for(c)
    assert not app.exception
    assert app.radio[0].value == 'LOCAL_POC_REVIEW'
    assert all(not b.disabled for b in app.button)
    assert not any('passphrase' in i.label.lower() or 'registered' in i.label.lower() for i in app.text_input)
    app.text_input(key='poc_reviewer_label').input('Synthetic UI owner')
    app.text_area(key='poc_owner_notes').input('Owned UI test')
    app.checkbox(key='poc_confirmed').check()
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception
    history, rejected = local_poc.discover(c['root'])
    assert not rejected and len(history) == 1 and history[0][0]['status'] == status
    assert any(status in str(m.value) for m in app.subheader)
    assert all(b.disabled for b in app.button)
    assert any('Review already completed' in str(m.value) for m in app.info)
    assert app.checkbox(key='poc_confirmed').value is False


@pytest.mark.parametrize('missing', ['label', 'confirmation'])
def test_ui_requires_owner_input_and_explicit_confirmation(poc_context, missing):
    app = app_for(poc_context)
    if missing != 'label':
        app.text_input(key='poc_reviewer_label').input('Synthetic UI owner')
    if missing != 'confirmation':
        app.checkbox(key='poc_confirmed').check()
    next(b for b in app.button if b.label == 'Approve').click().run()
    assert not app.exception and not local_poc.discover(poc_context['root'])[0]
    assert not poc_context['calls']


def test_refresh_read_only_and_signed_advanced_unchanged(poc_context, monkeypatch):
    from tools.human_review import workflow
    def denied(*a, **kw):
        pytest.fail('REFRESH_MUST_NOT_ASSEMBLE')
    monkeypatch.setattr(workflow, 'live_context', denied)
    app = app_for(poc_context)
    app.run()
    assert not app.exception
    app.radio[0].set_value('SIGNED_HUMAN_REVIEW (advanced)').run()
    assert not app.exception
    assert any(i.label == 'Signing-key passphrase' for i in app.text_input)
    assert any('NOT_REGISTERED' in str(w.value) for w in app.warning)
    assert all(b.disabled for b in app.button)


def test_non_localhost_ui_blocks_buttons(poc_context, monkeypatch):
    monkeypatch.setattr(local_poc, 'local_access', lambda: {'bind': '0.0.0.0', 'headers': {}, 'peer': None})
    app = app_for(poc_context)
    assert not app.exception and all(b.disabled for b in app.button)
    assert any('localhost' in str(w.value) for w in app.warning)


def test_confirmation_does_not_transfer_to_another_package(poc_context):
    import copy
    import hashlib

    from tools.human_review import workflow
    from tools.preflight_suite.artifacts import save
    from tools.quality_dashboard.artifacts import sha

    c = poc_context
    row = copy.deepcopy(c['row'])
    question = 'Second owned question: which search methods exist?'
    row.update(question_id='SYNTHETIC-Q2', question_sha256=hashlib.sha256(question.encode()).hexdigest())
    folder = c['root'] / 'data/evals/generation-runner/second-owned-control'
    save(folder / 'RESULT.json', row)
    save(folder / 'MANIFEST.json', {'schema': 'SYNTHETIC_ONLY', 'mode': 'live',
                                   'files': {'RESULT.json': sha(folder / 'RESULT.json')}})
    source = {'manifest_path': (folder / 'MANIFEST.json').relative_to(c['root']).as_posix(),
        'manifest_sha256': sha(folder / 'MANIFEST.json'),
        'result_path': (folder / 'RESULT.json').relative_to(c['root']).as_posix(),
        'result_sha256': sha(folder / 'RESULT.json')}
    assessment = copy.deepcopy(c['package']['assessment_draft'])
    assessment['question_sha256'] = row['question_sha256']
    workflow.prepare(c['root'], source=source, question=question, assessment=assessment, trust=c['package']['trust'])
    app = app_for(c)
    app.checkbox(key='poc_confirmed').check().run()
    next(s for s in app.selectbox if s.label == 'Local POC review package').select(0).run()
    assert not app.exception and not app.checkbox(key='poc_confirmed').value

