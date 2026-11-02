"""Synthetic owner triage: exact bindings, confirmation, duplicates, no approval bypass."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.human_review import observation_review as review
from tools.human_review.tests.test_response_diagnostics import publication
from tools.quality_dashboard.artifacts import ArtifactError, sha


@pytest.fixture
def target(tmp_path, monkeypatch):
    run = publication(tmp_path)
    row = json.loads((run / 'questions/OWNED-Q/RESULT.json').read_bytes())
    policy = {'path': 'owned-policy', 'sha256': 'c'*64}
    monkeypatch.setattr('tools.answer_quality.current.policy_reference', lambda root: policy)
    monkeypatch.setattr('tools.human_review.local_poc.require_localhost', lambda: None)
    monkeypatch.setattr('tools.human_review.workflow.trust_check', lambda *a: None)
    a = {'question_id': 'OWNED-Q', 'response': None, 'row': row, 'review_policy': policy,
        'response_file_sha256': sha(run / 'questions/OWNED-Q/RESULT.json'), 'audit': row['audit'] | {
            'request_sha256': row['request_sha256'], 'M8_package_sha256': row['M8_package_sha256']},
        'run': {'manifest_path': (run/'MANIFEST.json').relative_to(tmp_path).as_posix(),
                'manifest': json.loads((run/'MANIFEST.json').read_bytes())},
        'source': {'manifest_path': (run/'MANIFEST.json').relative_to(tmp_path).as_posix(),
                   'manifest_sha256': sha(run/'MANIFEST.json'),
                   'result_path': (run/'questions/OWNED-Q/RESULT.json').relative_to(tmp_path).as_posix(),
                   'result_sha256': sha(run/'questions/OWNED-Q/RESULT.json')}}
    return tmp_path, a


@pytest.mark.parametrize('decision', ['ANSWERED','PARTIAL','UNANSWERED','UNASSESSABLE'])
def test_triage_preserves_original_and_never_certifies_contract(target, decision):
    root, a = target
    before = sha(root/a['source']['result_path'])
    value = review.decide(root,a,decision=decision,label='Synthetic owner',notes='Fixture',confirmed=True)
    assert not value['formal_validation'] and not value['technical_findings_overridden']
    assert review.read_decision(root,a)['decision']==decision
    assert sha(root/a['source']['result_path'])==before
    with pytest.raises(ArtifactError,match='ALREADY_COMPLETED'):
        review.decide(root,a,decision=decision,label='Synthetic owner',notes='',confirmed=True)


@pytest.mark.parametrize('label,confirmed', [('',True),('Owned',False),(' ',True)])
def test_missing_confirmation_or_label_does_not_write(target,label,confirmed):
    root,a=target
    with pytest.raises(ArtifactError):
        review.decide(root,a,decision='ANSWERED',label=label,notes='',confirmed=confirmed)
    assert not list((root/review.BASE).glob('*/MANIFEST.json'))


def test_changed_source_or_policy_cannot_reuse_decision(target):
    root,a=target
    review.decide(root,a,decision='ANSWERED',label='Synthetic owner',notes='',confirmed=True)
    altered=copy.deepcopy(a);altered['review_policy']['sha256']='d'*64
    assert review.read_decision(root,altered)['status']=='PREVIOUS_POLICY_REVIEW_LOCKED'
    (root/a['source']['result_path']).write_text('{}')
    with pytest.raises(ArtifactError):review.read_decision(root,a)


def test_tampered_raw_cannot_be_reviewed(target):
    root,a=target
    capture=a['row']['audit']['raw_response_capture']
    (root/capture['artifact']['path']).write_text('tampered')
    with pytest.raises(ArtifactError):
        review.decide(root,a,decision='PARTIAL',label='Synthetic owner',notes='',confirmed=True)


def test_concurrent_decisions_have_one_winner(target):
    root,a=target
    def submit(_):
        try:
            review.decide(root,a,decision='UNASSESSABLE',label='Synthetic owner',notes='',confirmed=True)
            return 'recorded'
        except ArtifactError:return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit,range(2)))==['blocked','recorded']


def test_interrupted_write_never_becomes_accepted_review(target):
    root,a=target
    original=review.save
    def save(path,value):
        if Path(path).name=='MANIFEST.json':raise OSError('Synthetic storage failure')
        return original(path,value)
    with patch.object(review,'save',save),pytest.raises(OSError):
        review.decide(root,a,decision='ANSWERED',label='Synthetic owner',notes='',confirmed=True)
    with pytest.raises(ArtifactError):review.read_decision(root,a)
    with pytest.raises(ArtifactError):
        review.decide(root,a,decision='ANSWERED',label='Synthetic owner',notes='',confirmed=True)
