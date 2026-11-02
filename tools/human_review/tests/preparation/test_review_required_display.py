"""Source-bound display disposition never changes review approval or duplicate locks."""
import copy
import json

import pytest

from tools.human_review.review_state import recorded_review_required, status_label
from tools.preflight_suite.artifacts import save
from tools.quality_dashboard.artifacts import ArtifactError, sha


@pytest.fixture
def display_receipt(tmp_path):
    bindings={k:str(i)*64 for i,k in enumerate(['question_sha256','response_sha256','package_sha256','request_sha256'],1)}
    policy={'path':'policy','sha256':'a'*64}
    p={'question_id':'OWNED','bindings':bindings,'policy':policy,'supporting_artifacts':{}}
    record={'schema':'owner-decision-receipt-1.0','question_id':'OWNED',
        'context':dict(bindings,validation_policy=policy),
        'status':'OWNER_COMPLETENESS_RECORDED_GROUNDING_REVIEW_REQUIRED',
        'decisions':{'semantic_completeness':'ANSWERED','source_grounding':'NOT_APPROVED_PENDING_ORIGINAL_EVIDENCE_ASSESSMENT'},
        'not_a_generation_or_spending_authorization':True,'authenticated_human_review_accepted':False}
    name='data/owned/OWNER_DECISION_RECEIPT.json';save(tmp_path/name,record)
    p['supporting_artifacts'][name]=sha(tmp_path/name)
    checks={'overall_status':'REVIEW_REQUIRED','source_integrity':'LIVE_M8_VALIDATED','structural_validation':'PASS','citation_validity':'PASS',
        'question_sha256':bindings['question_sha256'],'response_sha256':bindings['response_sha256'],
        'M8_package_sha256':bindings['package_sha256'],'request_sha256':bindings['request_sha256']}
    return tmp_path,{'prepared':('fixture',p,{},'c'*64),'materials':{'fresh_technical_validation':checks}},record,name


def test_exact_bound_completeness_and_current_assessment_are_required(display_receipt):
    root,receipt,_,_=display_receipt
    before=copy.deepcopy(receipt)
    assert recorded_review_required(root,receipt)
    assert receipt==before
    assert status_label(receipt['prepared'][1],[],review_required=True)=='REVIEW_REQUIRED'


@pytest.mark.parametrize('key,value',[('overall_status','VALIDATION_FAILED'),('source_integrity','FAIL'),
    ('structural_validation','FAIL'),('citation_validity','FAIL'),('response_sha256','f'*64),
    ('M8_package_sha256','e'*64),('request_sha256','b'*64)])
def test_technical_failures_and_other_answers_cannot_get_disposition(display_receipt,key,value):
    root,receipt,_,_=display_receipt
    receipt['materials']['fresh_technical_validation'][key]=value
    assert not recorded_review_required(root,receipt)


@pytest.mark.parametrize('change',['response','policy','question','approval','auth'])
def test_bound_record_with_wrong_scope_is_not_an_owner_disposition(display_receipt,change):
    root,receipt,record,name=display_receipt
    if change=='response':record['context']['response_sha256']='f'*64
    elif change=='policy':record['context']['validation_policy']={'path':'different','sha256':'b'*64}
    elif change=='question':record['question_id']='OTHER'
    elif change=='approval':record['decisions']['source_grounding']='APPROVED'
    else:record['authenticated_human_review_accepted']=True
    (root/name).write_text(json.dumps(record));receipt['prepared'][1]['supporting_artifacts'][name]=sha(root/name)
    assert not recorded_review_required(root,receipt)


def test_tampered_record_fails_closed(display_receipt):
    root,receipt,_,name=display_receipt
    (root/name).write_text('{}')
    with pytest.raises(ArtifactError,match='HASH_MISMATCH'):
        recorded_review_required(root,receipt)


def test_accepted_owner_decisions_remain_authoritative(display_receipt):
    _,receipt,_,_=display_receipt;p=receipt['prepared'][1]
    for decision,status in [('APPROVE','OWNER_APPROVED_POC'),('REJECT','OWNER_REJECTED_POC'),('REQUEST_CHANGES','OWNER_REQUESTED_CHANGES_POC')]:
        row={'question_id':p['question_id'],'bindings':p['bindings'],'evidence_policy':p['policy'],
            'decision':decision,'status':status,'decided_at':'2026-10-29T12:00:00-07:00'}
        assert status_label(p,[(row,'sealed')],review_required=True)!='REVIEW_REQUIRED'
    row.update(status='BLOCKED_TECHNICAL')
    assert status_label(p,[(row,'sealed')],review_required=True)=='REVIEW_REQUIRED'
    assert 'Changes Requested' in status_label(p,[(row,'sealed')])
