import copy

import pytest

from tools.answer_quality.review import Assessment
from tools.human_review import handoff, local_poc, preparation, workflow
from tools.human_review.tests.handoff.conftest import assessment_input, publish
from tools.quality_dashboard.artifacts import ArtifactError


def prepared(c, *, candidate=False, status='ANSWERED'):
    publish(c, status=status)
    e = handoff.discover(c['root'])['entries'][0]
    if candidate:
        a = copy.deepcopy(c['package']['assessment_draft'])
        a['response_sha256'] = preparation.bindings(e['row'])['response_sha256']
        if status == 'ABSTAINED':
            a['response_sha256'] = preparation.bindings(e['row'])['response_sha256']
            a['claims'] = []
            for r in a['requirements']:
                r['claim_indices'] = []
        assessment_input(c, e, assessment=a)
    result = preparation.run(c['root'], question_ids=[c['row']['question_id']])
    assert result[0]['status'] in {'ASSESSMENT_READY', 'OWNER_REVIEW_NEEDED'}, result
    receipt = preparation.read(c['root'], result[0]['manifest'])
    return receipt


def test_unassessed_materials_are_actionable_without_fake_semantics(native):
    r = prepared(native)
    a = r['prepared'][1]['assessment_draft']
    assert r['status'] == 'OWNER_REVIEW_NEEDED'
    assert not a['answer_claim_inventory_complete'] and not a['question_requirements_reviewed']
    assert all(c['outcome'] == 'INDETERMINATE' for c in a['claims'])
    assert a['qualifications']['outcome'] == a['conflicts']['outcome'] == 'INDETERMINATE'
    assert not preparation.approval_ready(a, native['row']['response'])
    assert not local_poc.discover(native['root'])[0]
    assert preparation.source_context(native['root'], r)['parents']


@pytest.mark.parametrize('status', ['ANSWERED','PARTIAL','ABSTAINED'])
def test_supported_partial_and_abstention_materials(native, status):
    r = prepared(native, candidate=True, status=status)
    assert r['status'] == 'ASSESSMENT_READY'
    assert r['materials']['fresh_technical_validation']['source_integrity'] == 'LIVE_M8_VALIDATED'
    assert r['prepared'][2]['response']['status'] == status
    assert not r['owner_approval_created']


def test_repeated_preparation_is_idempotent_and_refresh_does_not_reconstruct(native, monkeypatch):
    first = prepared(native)
    calls = len(native['calls'])
    again = preparation.run(native['root'])
    assert again[0]['manifest'] == first['manifest'] and len(native['calls']) == calls
    monkeypatch.setattr(workflow,'live_context',lambda *a: pytest.fail('REFRESH_MUST_NOT_RECONSTRUCT'))
    rows,bad = preparation.discover(native['root'], handoff.discover(native['root'])['entries'][0])
    assert len(rows)==1 and not bad


@pytest.mark.parametrize('fault', ['source','private','manifest'])
def test_tampering_fails_closed(native, fault):
    r=prepared(native)
    path={'source':r['prepared'][1]['response_source']['result_path'],
          'private':r['protected_evidence']['path'], 'manifest':r['manifest']}[fault]
    (native['root']/path).write_text('{}')
    with pytest.raises((ArtifactError,KeyError)):
        preparation.read(native['root'],r['manifest'])


def test_source_failure_has_receipt_and_bounded_retry(native, monkeypatch):
    publish(native)
    original=workflow.live_context
    monkeypatch.setattr(workflow,'live_context',lambda *a: (_ for _ in ()).throw(ArtifactError('SOURCE_CHANGED_CONTROL')))
    result=preparation.run(native['root'])
    assert result[0]['status']=='ASSESSMENT_UNAVAILABLE' and result[0]['reason']=='SOURCE_CHANGED_CONTROL'
    monkeypatch.setattr(workflow,'live_context',original)
    result=preparation.run(native['root'])
    assert result[0]['status']=='OWNER_REVIEW_NEEDED'
    assert not local_poc.discover(native['root'])[0]


def test_interrupted_unsealed_preparation_can_retry_without_acceptance(native, monkeypatch):
    publish(native)
    original=workflow.prepare
    monkeypatch.setattr(workflow,'prepare',lambda *a,**k: (_ for _ in ()).throw(OSError('fixture')))
    assert preparation.run(native['root'])[0]['status']=='ASSESSMENT_UNAVAILABLE'
    assert not list(native['root'].glob(local_poc.BASE+'/*/MANIFEST.json'))
    monkeypatch.setattr(workflow,'prepare',original)
    assert preparation.run(native['root'])[0]['status']=='OWNER_REVIEW_NEEDED'


def test_complete_owner_judgments_can_use_poc_without_signing(native):
    r=prepared(native)
    a=copy.deepcopy(native['package']['assessment_draft'])
    path=preparation.owner_decide(native['root'],r['manifest'],expected_sha=r['manifest_sha256'],
        reviewer_label='Synthetic reviewer',decision='APPROVE',confirmed=True,assessment=a,
        additional_assertions=[],notes='Owned offline decision test')
    value=local_poc.read_record(native['root'],path)
    assert value['status']=='OWNER_APPROVED_POC' and not value['authenticated'] and not value['fully_validated']
    assert preparation.run(native['root'])[0]['status']=='REVIEW_ALREADY_COMPLETED'


@pytest.mark.parametrize('fault',['unconfirmed','unresolved','unauthorized-passage','bad-extra'])
def test_owner_approval_does_not_override_missing_judgments(native,fault):
    r=prepared(native)
    a=copy.deepcopy(native['package']['assessment_draft']); extra=[]; confirmed=True
    if fault=='unconfirmed':confirmed=False
    if fault=='unresolved':a['qualifications']['outcome']='INDETERMINATE'
    if fault=='unauthorized-passage':a['claims'][0]['passages'][0]['unit_id']='FABRICATED'
    if fault=='bad-extra':extra=[{'assertion':'Unverified addition','outcome':'SUPPORTED','rationale':'No evidence','passages':[]}]
    with pytest.raises(ArtifactError):
        preparation.owner_decide(native['root'],r['manifest'],expected_sha=r['manifest_sha256'],
            reviewer_label='Synthetic',decision='APPROVE',confirmed=confirmed,assessment=a,additional_assertions=extra)
    assert not local_poc.discover(native['root'])[0]


def test_missing_semantics_cannot_bypass_owner_form_via_backend(native):
    r=prepared(native)
    with pytest.raises(ArtifactError,match='UNRESOLVED_OWNER'):
        local_poc.decide(native['root'],r['package_manifest'],expected_sha=r['package_manifest_sha256'],
            reviewer_label='Synthetic',decision='APPROVE',confirmed=True)


def test_no_private_source_text_in_public_materials(native):
    r=prepared(native)
    private=preparation.source_context(native['root'],r)
    public=''.join(p.read_text() for p in (native['root']/r['manifest']).parent.iterdir())
    for parent in private['parents']:
        for text in parent['source_fields'].values():
            assert text not in public
    assert (native['root']/r['protected_evidence']['path']).stat().st_mode & 0o077 == 0


def test_normal_post_generation_hook_prepares_new_results(native):
    run,_=publish(native)
    rows=handoff.after_generation(native['root'],(run/'MANIFEST.json').relative_to(native['root']).as_posix())
    assert rows[0]['status']=='OWNER_REVIEW_NEEDED'
    assert not local_poc.discover(native['root'])[0]
    assert Assessment.model_validate(preparation.read(native['root'],rows[0]['manifest'])['prepared'][1]['assessment_draft'])
