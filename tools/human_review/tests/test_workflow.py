"""Real signatures and existing HumanReview/validator on owned synthetic evidence."""
import copy
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from tools.answer_quality.review import HumanReview
from tools.human_review import identity, workflow
from tools.quality_dashboard.artifacts import ArtifactError, read_json, sha

from .conftest import PASSWORD, REVIEWER


def submit(c, outcome='APPROVE', **updates):
    args = {'expected_sha': c['sha'], 'reviewer_id': REVIEWER, 'passphrase': PASSWORD,
        'decision': outcome, 'confirmation': workflow.confirmation_text(outcome, c['row']['question_id'], c['sha'])}
    return workflow.decide(c['root'], c['store'], c['manifest'], **(args | updates))


def test_registration_reuse_and_no_private_key_in_project(context):
    c = context
    r = identity.registry(c['store'])
    assert r['reviewer_id'] == REVIEWER and not r['revoked']
    assert 'ENCRYPTED PRIVATE KEY' in (c['store'] / r['key_file']).read_text()
    assert not list(c['root'].rglob('*.pem'))
    identity.authenticate(c['store'], REVIEWER, PASSWORD, {'challenge': 1})
    with pytest.raises(ArtifactError):
        identity.register(c['store'], REVIEWER, 'Synthetic Reviewer', PASSWORD,
                          'REGISTER synthetic-reviewer AS Synthetic Reviewer')


@pytest.mark.parametrize('update', [{'passphrase': 'wrong-password'}, {'reviewer_id': 'someone-else'},
    {'confirmation': ''}, {'confirmation': 'APPROVE DIFFERENT-QUESTION ' + '0' * 64}, {'expected_sha': 'f' * 64}])
def test_missing_or_wrong_authentication_confirmation_blocks(context, update):
    with pytest.raises(ArtifactError):
        submit(context, **update)
    assert not list(context['root'].glob('data/evals/answer-quality/human-review-*'))


def test_explicit_enrollment_required(tmp_path):
    for name, confirm in [('Owner', ''), ('', 'REGISTER owner AS ')]:
        with pytest.raises(ArtifactError):
            identity.register(tmp_path.resolve() / 'no-key', 'owner', name, PASSWORD, confirm)
    assert not (tmp_path / 'no-key').exists()


@pytest.mark.parametrize('outcome,expected', [('APPROVE', 'VALIDATED'), ('REJECT', 'VALIDATION_FAILED'),
                                           ('REQUEST_CHANGES', 'REVIEW_REQUIRED')])
def test_authentic_decisions_existing_importer_and_separate_outcomes(context, outcome, expected):
    c = context
    before = copy.deepcopy(c['row'])
    result = submit(c, outcome)
    body, evaluation = workflow.verify_decision(c['root'], c['store'], result)
    assert body['outcome'] == outcome and evaluation['overall_status'] == expected
    assert not body['generation_authorized']
    if outcome == 'APPROVE':
        file = result.rsplit('/', 1)[0] + '/HUMAN_ASSESSMENT.json'
        human = HumanReview(c['root'], file, body['assessment_sha256'], approved_reviewers={REVIEWER})
        assert human.value.reviewer == REVIEWER
        assert evaluation['semantic_status'] == 'HUMAN_REVIEWED'
    assert c['row'] == before
    assert c['calls'].count('source-validate') >= 2
    with pytest.raises(ArtifactError, match='DUPLICATE'):
        submit(c, outcome)


@pytest.mark.parametrize('field', ['response', 'M8_package_sha256', 'question_id', 'request_sha256'])
def test_response_evidence_question_request_tampering(context, field):
    c = context
    result = submit(c)
    path = c['root'] / c['package']['response_source']['result_path']
    row = read_json(path)
    if field == 'response':
        row[field]['answer'] = 'Tampered answer.'
    else:
        row[field] = 'different'
    path.write_text(json.dumps(row))
    with pytest.raises(ArtifactError):
        workflow.verify_decision(c['root'], c['store'], result)


@pytest.mark.parametrize('field', ['signature', 'evaluation', 'human_assessment', 'package'])
def test_tampered_signed_artifacts_even_with_resealed_manifest(context, field):
    c = context
    result = submit(c)
    folder = (c['root'] / result).parent
    if field == 'package':
        path = c['root'] / c['manifest']
        path.write_text('{}')
    else:
        file = {'signature': 'APPROVAL.json', 'evaluation': 'ASSESSMENT.json',
                'human_assessment': 'HUMAN_ASSESSMENT.json'}[field]
        path = folder / file
        value = read_json(path)
        if field == 'signature':
            value['signature'] = 'AA=='
        elif field == 'evaluation':
            value['overall_status'] = 'BOGUS'
        else:
            value['qualifications']['rationale'] = 'Substituted rationale.'
        path.write_text(json.dumps(value))
        manifest = read_json(folder / 'MANIFEST.json')
        manifest['files'][file] = sha(path)
        (folder / 'MANIFEST.json').write_text(json.dumps(manifest))
    with pytest.raises((ArtifactError, KeyError)):
        workflow.verify_decision(c['root'], c['store'], result)


def test_wrong_package_and_revoked_reviewer(context):
    c = context
    result = submit(c)
    with pytest.raises(ArtifactError, match='DIFFERENT_PACKAGE'):
        workflow.verify_decision(c['root'], c['store'], result, package_manifest='another-package')
    identity.change_key(c['store'], REVIEWER, PASSWORD, operation='REVOKE',
                        confirmation='REVOKE ' + REVIEWER)
    with pytest.raises(ArtifactError, match='REVOKED'):
        workflow.verify_decision(c['root'], c['store'], result)
    with pytest.raises(ArtifactError, match='REVOKED'):
        identity.authenticate(c['store'], REVIEWER, PASSWORD, {})


def test_key_rotation_proves_old_and_new_credentials(context):
    c = context
    old = identity.registry(c['store'])
    new = identity.change_key(c['store'], REVIEWER, PASSWORD, operation='ROTATE',
        confirmation='ROTATE ' + REVIEWER, new_passphrase='new-synthetic-passphrase')
    assert new['public_key'] != old['public_key'] and new['enrollment_sha256'] == old['enrollment_sha256']
    with pytest.raises(ArtifactError):
        identity.authenticate(c['store'], REVIEWER, PASSWORD, {})
    identity.authenticate(c['store'], REVIEWER, 'new-synthetic-passphrase', {})


def test_tampered_registry_and_unsafe_permissions(context):
    c = context
    p = c['store'] / 'REGISTRY.json'
    p.chmod(0o644)
    with pytest.raises(ArtifactError, match='PERMISSIONS'):
        identity.registry(c['store'])
    p.chmod(0o600)
    value = read_json(p)
    value[0]['event']['display_name'] = 'Impersonation'
    p.write_text(json.dumps(value))
    with pytest.raises(ArtifactError):
        identity.registry(c['store'])


def test_stale_package_requires_new_confirmation(context):
    c = context
    path = (c['root'] / c['manifest']).parent / 'REVIEW_PACKAGE.json'
    value = read_json(path)
    value['expires_at'] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    path.write_text(json.dumps(value))
    manifest = read_json(c['root'] / c['manifest'])
    manifest['files']['REVIEW_PACKAGE.json'] = sha(path)
    (c['root'] / c['manifest']).write_text(json.dumps(manifest))
    with pytest.raises(ArtifactError, match='STALE'):
        submit(c, expected_sha=sha(c['root'] / c['manifest']))


@pytest.mark.parametrize('failure', ['source', 'sign', 'persist', 'commit'])
def test_failures_do_not_publish_partial_acceptance(context, monkeypatch, failure):
    c = context
    def fail(*a, **kw):
        raise ArtifactError('SYNTHETIC_FAILURE')
    if failure == 'source':
        monkeypatch.setattr(workflow, 'live_context', fail)
    elif failure == 'sign':
        monkeypatch.setattr(identity, 'sign', fail)
    elif failure == 'persist':
        monkeypatch.setattr(workflow, 'save', fail)
    else:
        monkeypatch.setattr(workflow.os, 'rename', fail)
    with pytest.raises(ArtifactError):
        submit(c)
    assert not list(c['root'].glob('data/evals/answer-quality/human-review-*'))


def test_interrupted_commit_authenticated_recovery(context, monkeypatch):
    c = context
    rename = os.rename
    def fail(*a, **kw):
        raise OSError('synthetic-commit-failure')
    monkeypatch.setattr(workflow.os, 'rename', fail)
    with pytest.raises(OSError):
        submit(c)
    monkeypatch.setattr(workflow.os, 'rename', rename)
    with pytest.raises(ArtifactError, match='DUPLICATE_OR_INTERRUPTED'):
        submit(c)
    target = workflow.target_identity(c['package'])
    workflow.recover(c['root'], c['store'], target, reviewer_id=REVIEWER, passphrase=PASSWORD,
                      confirmation='ABORT ' + target)
    result = submit(c)
    assert workflow.verify_decision(c['root'], c['store'], result)[1]['fully_validated']
    with pytest.raises(ArtifactError, match='CANNOT_BE_ABORTED'):
        workflow.recover(c['root'], c['store'], target, reviewer_id=REVIEWER, passphrase=PASSWORD,
                          confirmation='ABORT ' + target)


def test_source_failure_cannot_be_overridden_by_owner_vote(context, monkeypatch):
    c = context
    monkeypatch.setattr(c['service'], 'validate', lambda *a: False)
    result = submit(c)
    _, evaluation = workflow.verify_decision(c['root'], c['store'], result)
    assert evaluation['overall_status'] == 'VALIDATION_FAILED'
    assert not evaluation['fully_validated']


def test_no_secret_or_protected_source_payload_in_outputs(context):
    c = context
    result = submit(c)
    folder = (c['root'] / result).parent
    text = ''.join(p.read_text() for p in folder.iterdir())
    assert PASSWORD not in text and 'PRIVATE KEY' not in text
    assert 'verified_parent' not in text
    assert not list(c['root'].rglob('LIVE_ATTEMPT.json'))
    assert not list(c['root'].rglob('OWNER_AUTHORIZATION.json'))

