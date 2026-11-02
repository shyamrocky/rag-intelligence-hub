"""Status derives from verified decisions and cross-policy revisions are explicit."""
import copy

import pytest

from tools.human_review import local_poc, workflow
from tools.human_review.review_state import current_decision, latest_answer_decision, status_label
from tools.human_review.tests.handoff.test_handoff_ui import app_for
from tools.quality_dashboard.artifacts import ArtifactError, sha

from .test_preparation import prepared


@pytest.mark.parametrize('decision,label', [('APPROVE','Approved (Local POC)'),
    ('REJECT','Rejected'),('REQUEST_CHANGES','Changes Requested')])
def test_verified_dropdown_status_and_lock(native,decision,label):
    receipt=prepared(native,candidate=True)
    path,_p,_,ph=receipt['prepared']
    local_poc.decide(native['root'],path,expected_sha=ph,reviewer_label='Synthetic owner',
        decision=decision,confirmed=True)
    app=app_for(native)
    assert not app.exception
    selector=next(s for s in app.selectbox if s.label=='Completed generation for Human Review')
    assert label in selector.options[0]
    assert all(b.disabled for b in app.button if b.label in {'Approve','Reject','Request Changes'})
    assert any(e.label=='Advanced Review / Edit Findings' and not e.proto.expanded for e in app.expander)
    app.run()
    assert not app.exception


def test_policy_version_cannot_transfer_or_duplicate_decision(native):
    receipt=prepared(native,candidate=True)
    path,p,_row,ph=receipt['prepared']
    first=local_poc.decide(native['root'],path,expected_sha=ph,reviewer_label='Synthetic owner',decision='APPROVE',confirmed=True)
    legacy={'path':'tools/answer_quality/POLICY.json','sha256':sha(native['root']/'tools/answer_quality/POLICY.json')}
    newer=workflow.prepare(native['root'],source=p['response_source'],question=p['question'],
        assessment=p['assessment_draft'],trust=p['trust'],validation_policy=legacy)
    q,_,qh=workflow.load_package(native['root'],newer)
    history,bad=local_poc.discover(native['root'])
    assert not bad and current_decision(q,history) is None
    assert latest_answer_decision(q,history)[1]==first
    assert 'previous policy' in status_label(q,history)
    with pytest.raises(ArtifactError,match='REVIEW_ALREADY_COMPLETED'):
        local_poc.decide(native['root'],newer,expected_sha=qh,reviewer_label='Other owner',decision='APPROVE',confirmed=True)
    ref={'path':first,'sha256':sha(native['root']/first)}
    second=local_poc.decide(native['root'],newer,expected_sha=qh,reviewer_label='Synthetic owner',decision='REJECT',
        confirmed=True,revision_of=ref,revision_reason='Explicit policy migration review')
    assert local_poc.read_record(native['root'],second)['previous_decision']==ref
    assert local_poc.discover(native['root'])[1]==0


def test_blocked_negative_intent_remains_visible_and_locked(native,monkeypatch):
    r=prepared(native,candidate=True);path,p,_,ph=r['prepared']
    monkeypatch.setattr(local_poc,'technical_check',lambda *a:{'overall_status':'VALIDATION_FAILED'})
    first=local_poc.decide(native['root'],path,expected_sha=ph,reviewer_label='Synthetic owner',
        decision='REQUEST_CHANGES',confirmed=True)
    history,bad=local_poc.discover(native['root'])
    assert not bad and 'Changes Requested' in status_label(p,history)
    assert 'Technical Block' in status_label(p,history)
    with pytest.raises(ArtifactError,match='REVIEW_ALREADY_COMPLETED'):
        local_poc.decide(native['root'],path,expected_sha=ph,reviewer_label='Synthetic owner',
            decision='REJECT',confirmed=True)
    assert latest_answer_decision(p,history)[1]==first


def test_new_response_or_evidence_never_inherits_old_status(native):
    r=prepared(native,candidate=True);path,p,_,ph=r['prepared']
    local_poc.decide(native['root'],path,expected_sha=ph,reviewer_label='Synthetic owner',decision='APPROVE',confirmed=True)
    history,_=local_poc.discover(native['root'])
    for field in ['response_sha256','package_sha256','request_sha256']:
        q=copy.deepcopy(p);q['bindings'][field]='e'*64
        assert status_label(q,history)=='Pending Review'
