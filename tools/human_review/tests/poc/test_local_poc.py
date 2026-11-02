"""Unsigned local attestations cannot become authenticated validation."""
import json

import pytest

from tools.human_review import local_poc
from tools.quality_dashboard.artifacts import ArtifactError, read_json, sha


def submit(c, **overrides):
    args = {'expected_sha': c['sha'], 'reviewer_label': 'Synthetic local owner',
            'decision': 'APPROVE', 'confirmed': True, 'notes': 'Synthetic test only'}
    return local_poc.decide(c['root'], c['manifest'], **(args | overrides))


@pytest.mark.parametrize('decision,expected', [('APPROVE', 'OWNER_APPROVED_POC'),
    ('REJECT', 'OWNER_REJECTED_POC'), ('REQUEST_CHANGES', 'OWNER_REQUESTED_CHANGES_POC')])
def test_three_unsigned_decisions_without_registration(poc_context, decision, expected):
    c = poc_context
    result = submit(c, decision=decision)
    value = local_poc.read_record(c['root'], result)
    assert value['mode'] == 'LOCAL_POC_REVIEW' and value['status'] == expected
    assert not value['authenticated'] and not value['fully_validated'] and not value['generation_authorized']
    assert value['bindings'] == c['package']['bindings']
    assert value['owner_notes'] == 'Synthetic test only' and value['decided_at']
    assert value['technical_validation']['citation_validity'] == 'PASS'
    assert value['technical_validation']['overall_status'] == 'REVIEW_REQUIRED'
    assert not list(c['root'].rglob('*.pem'))


@pytest.mark.parametrize('overrides', [{'confirmed': False}, {'confirmed': None},
    {'reviewer_label': ''}, {'reviewer_label': '   '}, {'decision': 'AUTO_APPROVE'}, {'expected_sha': 'f' * 64}])
def test_label_confirmation_exact_package_required(poc_context, overrides):
    with pytest.raises(ArtifactError):
        submit(poc_context, **overrides)
    assert not list(poc_context['root'].glob(local_poc.BASE + '/*/MANIFEST.json'))


@pytest.mark.parametrize('context', [
    {'bind': None, 'headers': {'Host': 'localhost:8514'}, 'peer': None},
    {'bind': '0.0.0.0', 'headers': {'Host': 'localhost:8514'}, 'peer': None},
    {'bind': '127.0.0.1', 'headers': {}, 'peer': None},
    {'bind': '127.0.0.1', 'headers': {'Host': 'public.example'}, 'peer': None},
    {'bind': '127.0.0.1', 'headers': {'Host': 'localhost', 'Origin': 'https://public.example'}, 'peer': None},
    {'bind': '127.0.0.1', 'headers': {'Host': 'localhost', 'X-Forwarded-For': '127.0.0.1'}, 'peer': None},
    {'bind': '127.0.0.1', 'headers': {'Host': 'localhost'}, 'peer': '10.0.0.2'},
])
def test_non_local_or_unverified_access_blocks(poc_context, monkeypatch, context):
    monkeypatch.setattr(local_poc, 'local_access', lambda: context)
    with pytest.raises(ArtifactError, match='LOCALHOST'):
        submit(poc_context)
    assert not poc_context['calls']


@pytest.mark.parametrize('bind,host,peer', [('localhost', 'localhost:8514', None),
    ('::1', '[::1]:8514', '::1'), ('127.0.0.1', '127.0.0.1:8514', None)])
def test_explicit_loopback_configurations(monkeypatch, bind, host, peer):
    monkeypatch.setattr(local_poc, 'local_access', lambda: {'bind': bind, 'headers': {'Host': host}, 'peer': peer})
    local_poc.require_localhost()


def test_source_failure_is_not_owner_approval(poc_context, monkeypatch):
    c = poc_context
    monkeypatch.setattr(c['source'], 'validate', lambda *a: False)
    value = local_poc.read_record(c['root'], submit(c))
    assert value['status'] == 'BLOCKED_TECHNICAL'
    assert value['technical_validation']['overall_status'] == 'VALIDATION_FAILED'


def test_duplicate_and_later_explicit_decision_versioning(poc_context):
    c = poc_context
    original = submit(c)
    with pytest.raises(ArtifactError, match='DUPLICATE'):
        submit(c)
    with pytest.raises(ArtifactError, match='REVIEW_ALREADY_COMPLETED'):
        submit(c, decision='REQUEST_CHANGES', notes='Changed notes cannot bypass the lock.')
    submit(c, decision='REQUEST_CHANGES', revision_of={'path': original, 'sha256': sha(c['root'] / original)},
        revision_reason='Explicit synthetic reassessment of this same answer.', notes='Owner requests a revised answer.')
    history, rejected = local_poc.discover(c['root'])
    assert len(history) == 2 and not rejected
    assert history[-1][0]['status'] == 'OWNER_REQUESTED_CHANGES_POC'


def test_response_tampering_and_failed_commit_cannot_accept(poc_context, monkeypatch):
    c = poc_context
    def failed(*a, **kw):
        raise OSError('Owned failure control')
    monkeypatch.setattr(local_poc.os, 'rename', failed)
    with pytest.raises(OSError):
        submit(c)
    assert local_poc.discover(c['root']) == ([], 0)
    path = c['root'] / c['package']['response_source']['result_path']
    row = read_json(path)
    row['response']['answer'] = 'Fabricated replacement.'
    path.write_text(json.dumps(row))
    with pytest.raises(ArtifactError):
        submit(c)


def test_record_tampering_is_excluded(poc_context):
    c = poc_context
    result = submit(c)
    path = (c['root'] / result).parent / 'DECISION.json'
    value = read_json(path)
    value['status'] = 'VALIDATED'
    path.write_text(json.dumps(value))
    assert local_poc.discover(c['root'])[1] == 1


def test_no_publisher_packages_credentials_or_live_markers(poc_context):
    c = poc_context
    result = submit(c)
    text = ''.join(p.read_text() for p in (c['root'] / result).parent.iterdir())
    assert 'verified_parent' not in text and 'PRIVATE KEY' not in text
    assert not list(c['root'].rglob('LIVE_ATTEMPT.json'))
    assert not list(c['root'].rglob('HUMAN_ASSESSMENT.json'))


@pytest.mark.parametrize('field,value', [('source_integrity', 'FAIL'), ('citation_validity', 'FAIL'),
    ('structural_validation', 'FAIL'), ('overall_status', 'VALIDATION_FAILED')])
def test_owner_vote_cannot_override_technical_dimensions(field, value):
    checks = {'source_integrity': 'LIVE_M8_VALIDATED', 'citation_validity': 'PASS',
              'structural_validation': 'PASS', 'overall_status': 'REVIEW_REQUIRED'}
    checks[field] = value
    assert local_poc.status('APPROVE', checks) == 'BLOCKED_TECHNICAL'

