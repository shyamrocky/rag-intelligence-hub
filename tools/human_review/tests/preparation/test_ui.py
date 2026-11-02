
import pytest

from tools.human_review import local_poc, preparation, workflow
from tools.human_review.tests.handoff.conftest import publish
from tools.human_review.tests.handoff.test_handoff_ui import app_for
from tools.quality_dashboard.artifacts import sha

from .test_preparation import prepared


def test_missing_ai_assessment_exposes_evidence_and_owner_judgments(native):
    receipt=prepared(native)
    app=app_for(native)
    assert not app.exception
    assert any('OWNER_REVIEW_NEEDED' in str(s.value) for s in app.subheader)
    assert any(s.label=='Claim 1 support' for s in app.selectbox)
    assert any(s.value=='INDETERMINATE' for s in app.selectbox if s.label=='Claim 1 support')
    assert any(e.label=='Inspect authentic supplied evidence and source-use metadata' for e in app.expander)
    assert all(not b.disabled for b in app.button if b.label in {'Approve','Reject','Request Changes'})
    before={p:sha(p) for p in native['root'].rglob('*') if p.is_file()}
    app.run()
    assert not app.exception and before=={p:sha(p) for p in native['root'].rglob('*') if p.is_file()}
    assert receipt['materials']['semantic_assessor_executed'] is False


def test_reject_can_record_owner_judgments_without_fake_supported_values(native):
    prepared(native)
    app=app_for(native)
    app.text_input(key='assessment_reviewer').input('Synthetic owner')
    app.checkbox(key='assessment_confirmed').check()
    next(b for b in app.button if b.label=='Reject').click().run()
    assert not app.exception
    history,bad=local_poc.discover(native['root'])
    assert not bad and history[0][0]['status']=='OWNER_REJECTED_POC'
    assert all(b.disabled for b in app.button if b.label in {'Approve','Reject','Request Changes'})


def test_approve_requires_explicit_inventory_and_resolved_judgments(native):
    prepared(native,candidate=True)
    app=app_for(native)
    app.text_input(key='assessment_reviewer').input('Synthetic owner')
    app.checkbox(key='assessment_confirmed').check()
    next(b for b in app.button if b.label=='Approve').click().run()
    assert not app.exception and not local_poc.discover(native['root'])[0]
    assert app.error
    next(c for c in app.checkbox if c.label.startswith('I checked all factual')).check()
    next(c for c in app.checkbox if c.label.startswith('I checked every requested')).check()
    next(b for b in app.button if b.label=='Approve').click().run()
    assert not app.exception
    assert local_poc.discover(native['root'])[0][0][0]['status']=='OWNER_APPROVED_POC'


def test_technical_failure_blocks_approve_but_remains_inspectable(native,monkeypatch):
    from tools.answer_quality.validator import PostGenerationValidator
    original=PostGenerationValidator.validate
    def fail(self,*a,**k):
        value=original(self,*a,**k)
        return value|{'overall_status':'VALIDATION_FAILED','diagnoses':['SUBSTANTIVE_MISQUOTATION']}
    monkeypatch.setattr(PostGenerationValidator,'validate',fail)
    prepared(native,candidate=True)
    app=app_for(native)
    assert not app.exception
    assert next(b for b in app.button if b.label=='Approve').disabled
    assert any('Approval blocked by technical validation' in str(e.value) for e in app.error)


def test_explicit_bounded_preparation_action_and_readonly_restart(native,monkeypatch):
    publish(native)
    app=app_for(native)
    assert not app.exception
    next(b for b in app.button if b.label=='Prepare evidence & review materials').click().run()
    assert not app.exception
    assert any('OWNER_REVIEW_NEEDED' in str(s.value) for s in app.subheader)
    monkeypatch.setattr(workflow,'live_context',lambda *a: pytest.fail('REFRESH_ASSEMBLY'))
    monkeypatch.setattr(preparation,'run',lambda *a,**k: pytest.fail('REFRESH_PREPARATION'))
    app=app_for(native)
    assert not app.exception


def test_private_context_not_visible_over_nonlocal_session(native,monkeypatch):
    prepared(native)
    monkeypatch.setattr(local_poc,'local_access',lambda:{'bind':'0.0.0.0','headers':{},'peer':None})
    app=app_for(native)
    assert not app.exception
    assert all(b.disabled for b in app.button if b.label in {'Approve','Reject','Request Changes'})
    assert not any(e.label=='Inspect authentic supplied evidence and source-use metadata' for e in app.expander)
