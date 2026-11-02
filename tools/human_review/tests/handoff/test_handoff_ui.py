import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

from tools.human_review import handoff, local_poc, workflow
from tools.quality_dashboard.artifacts import sha

from .conftest import assessment_input, publish


def app_for(native):
    return AppTest.from_string('from pathlib import Path\n'
        'import streamlit as st\nfrom tools.human_review.poc_ui import render\n'
        f'render(st, Path({str(native["root"])!r}))', default_timeout=120).run()


@pytest.mark.parametrize('status', ['ANSWERED', 'PARTIAL', 'ABSTAINED'])
def test_pending_results_and_quotations_are_immediately_visible(native, status):
    publish(native, status=status, validation='VALIDATION_FAILED')
    before = {p: sha(p) for p in native['root'].rglob('*') if p.is_file()}
    app = app_for(native)
    assert not app.exception
    assert any(s.label == 'Completed generation for Human Review' for s in app.selectbox)
    assert all(b.disabled for b in app.button if b.label in {'Approve', 'Reject', 'Request Changes'})
    assert any(b.label == 'Prepare evidence & review materials' for b in app.button)
    assert any('required assessments are missing' in str(w.value) for w in app.warning)
    assert any('SUBSTANTIVE_MISQUOTATION' in str(w.value) for w in app.warning)
    assert any(status in str(c.value) for c in app.caption)
    app.run()
    assert not app.exception
    assert before == {p: sha(p) for p in native['root'].rglob('*') if p.is_file()}


@pytest.mark.parametrize('button,status', [('Approve', 'OWNER_APPROVED_POC'),
    ('Reject', 'OWNER_REJECTED_POC'), ('Request Changes', 'OWNER_REQUESTED_CHANGES_POC')])
def test_existing_assessment_prepares_on_confirmed_decision_without_manual_package(native, button, status):
    publish(native)
    entry = handoff.discover(native['root'])['entries'][0]
    assessment_input(native, entry)
    count = len(list((native['root'] / workflow.PACKAGE_BASE).glob('*/MANIFEST.json')))
    app = app_for(native)
    assert not app.exception
    assert all(not b.disabled for b in app.button)
    assert len(list((native['root'] / workflow.PACKAGE_BASE).glob('*/MANIFEST.json'))) == count
    app.text_input(key='poc_reviewer_label').input('Synthetic review owner')
    app.checkbox(key='poc_confirmed').check()
    next(b for b in app.button if b.label == button).click().run()
    assert not app.exception
    records, rejected = local_poc.discover(native['root'])
    assert not rejected and len(records) == 1 and records[0][0]['status'] == status
    assert not records[0][0]['authenticated'] and not records[0][0]['fully_validated']
    assert len(list((native['root'] / workflow.PACKAGE_BASE).glob('*/MANIFEST.json'))) == count + 1


def test_candidate_without_confirmation_does_not_prepare_or_decide(native):
    publish(native)
    entry = handoff.discover(native['root'])['entries'][0]
    assessment_input(native, entry)
    app = app_for(native)
    app.text_input(key='poc_reviewer_label').input('Synthetic owner')
    next(b for b in app.button if b.label == 'Approve').click().run()
    assert not app.exception and not local_poc.discover(native['root'])[0]
    assert not (native['root'] / handoff.BASE).exists()


def test_pending_rerender_never_reconstructs_or_approves(native, monkeypatch):
    publish(native)
    def denied(*a, **kw):
        pytest.fail('READ_ONLY_REFRESH')
    monkeypatch.setattr(workflow, 'prepare', denied)
    monkeypatch.setattr(workflow, 'live_context', denied)
    monkeypatch.setattr(local_poc, 'decide', denied)
    app = app_for(native)
    app.run()
    assert not app.exception


def test_historical_structured_diagnoses_remain_visible(native, monkeypatch):
    publish(native)
    original = handoff.discover
    def historical(*a, **kw):
        data = original(*a, **kw)
        data['entries'][0]['row']['post_validation']['diagnoses'] = [{'category': 'INVALID_CITATION'}]
        return data
    monkeypatch.setattr('tools.human_review.handoff_ui.discover', historical)
    app = app_for(native)
    assert not app.exception
    assert any('INVALID_CITATION' in str(x.value) for x in app.warning)
