"""Authenticated reviews populate the existing source-free quality reader."""
import json

import pytest

from tools.answer_quality import reporting
from tools.human_review import workflow
from tools.quality_dashboard.artifacts import ArtifactError, read_json, sha

from .test_workflow import submit


def test_signed_result_discovery_and_revoked_or_forged_records_fail_closed(context, monkeypatch):
    from tools.human_review import identity
    c = context
    monkeypatch.setattr(identity, 'default_store', lambda: c['store'])
    result = submit(c)
    values, rejected = reporting.discover(c['root'], question_id=c['row']['question_id'],
        response_sha256=c['package']['bindings']['response_sha256'],
        request_sha256=c['row']['request_sha256'])
    assert not rejected and len(values) == 1
    assert values[0][0]['fully_validated']
    folder = (c['root'] / result).parent
    evaluation = read_json(folder / 'ASSESSMENT.json')
    evaluation['answer'] = 'Tampered rendering'
    (folder / 'ASSESSMENT.json').write_text(json.dumps(evaluation))
    manifest = read_json(folder / 'MANIFEST.json')
    manifest['authenticated_review'] = False
    manifest['files']['ASSESSMENT.json'] = sha(folder / 'ASSESSMENT.json')
    (folder / 'MANIFEST.json').write_text(json.dumps(manifest))
    values, rejected = reporting.discover(c['root'], question_id=c['row']['question_id'],
        response_sha256=c['package']['bindings']['response_sha256'],
        request_sha256=c['row']['request_sha256'])
    assert not values and rejected


def test_same_draft_new_package_does_not_bypass_duplicate(context):
    from tools.quality_dashboard.artifacts import ArtifactError
    c = context
    submit(c)
    path = workflow.prepare(c['root'], source=c['package']['response_source'],
        question=c['owned']['question'], assessment=c['package']['assessment_draft'], trust=c['package']['trust'])
    h = sha(c['root'] / path)
    from .conftest import PASSWORD, REVIEWER
    with pytest.raises(ArtifactError, match='DUPLICATE'):
        workflow.decide(c['root'], c['store'], path, expected_sha=h, reviewer_id=REVIEWER,
            passphrase=PASSWORD, decision='APPROVE',
            confirmation=workflow.confirmation_text('APPROVE', c['row']['question_id'], h))


def test_invalid_citation_never_promoted(context):
    c = context
    row = read_json(c['root'] / c['package']['response_source']['result_path'])
    row['response']['claims'][0]['evidence_unit_ids'] = ['FABRICATED']
    (c['root'] / c['package']['response_source']['result_path']).write_text(json.dumps(row))
    # The immutable row/package source binding rejects this before signing.
    with pytest.raises(ArtifactError):
        submit(c)
    assert not list(c['root'].glob('data/evals/answer-quality/human-review-*'))


def test_safe_output_rejects_symlink(context):
    from tools.quality_dashboard.artifacts import ArtifactError
    c = context
    outside = c['root'].parent / 'outside'
    outside.mkdir()
    (c['root'] / 'escape').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ArtifactError, match='UNSAFE'):
        workflow.output_directory(c['root'], 'escape/output')
    assert not list(outside.iterdir())

