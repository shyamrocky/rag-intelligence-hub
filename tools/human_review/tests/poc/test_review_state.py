"""Owned synthetic answer versions, cross-package locks and explicit revision history."""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from tools.human_review import local_poc, workflow
from tools.human_review.review_state import current_decision, group_packages, target_identity
from tools.preflight_suite.artifacts import save
from tools.quality_dashboard.artifacts import ArtifactError, digest, read_json, sha

from .test_local_poc import submit
from .test_poc_ui import app_for


def another_package(c):
    return workflow.prepare(c['root'], source=c['package']['response_source'], question=c['package']['question'],
        assessment=c['package']['assessment_draft'], trust=c['package']['trust'])


@pytest.mark.parametrize('decision', ['APPROVE', 'REJECT', 'REQUEST_CHANGES'])
def test_package_migration_and_changed_form_cannot_repeat_decision(poc_context, decision):
    c = poc_context
    first = submit(c, decision=decision)
    path = another_package(c)
    with pytest.raises(ArtifactError, match='REVIEW_ALREADY_COMPLETED'):
        local_poc.decide(c['root'], path, expected_sha=sha(c['root'] / path), reviewer_label='Another label',
            notes='Different note', confirmed=True, decision='APPROVE')
    history, rejected = local_poc.discover(c['root'])
    p, row, ph = workflow.load_package(c['root'], path)
    assert not rejected and current_decision(p, history)[1] == first
    assert len(group_packages([(c['manifest'], c['package'], c['row'], c['sha']), (path, p, row, ph)])) == 1
    app = app_for(c)
    app.run()
    assert not app.exception and all(b.disabled for b in app.button)
    assert len(next(s for s in app.selectbox if s.label == 'Local POC review package').options) == 1
    assert any('history' in e.label for e in app.expander)


@pytest.mark.parametrize('field', ['question_sha256', 'response_sha256', 'package_sha256', 'request_sha256', 'policy'])
def test_identity_never_transfers_across_bound_versions(poc_context, field):
    c = poc_context
    submit(c)
    p = copy.deepcopy(c['package'])
    if field == 'policy':
        p['policy']['sha256'] = 'e' * 64
    else:
        p['bindings'][field] = 'e' * 64
    assert target_identity(p) != target_identity(c['package'])
    assert current_decision(p, local_poc.discover(c['root'])[0]) is None


def test_assessment_and_trust_renewal_do_not_create_new_answer(poc_context):
    p = copy.deepcopy(poc_context['package'])
    p['assessment_draft_sha256'] = 'f' * 64
    p['trust'] = {'path': 'new-reviewed-baseline', 'sha256': 'e' * 64}
    assert target_identity(p) == target_identity(poc_context['package'])


def test_two_concurrent_packages_publish_only_one_decision(poc_context):
    c = poc_context
    other = another_package(c)
    barrier = Barrier(2)
    def attempt(path):
        barrier.wait(timeout=10)
        try:
            return local_poc.decide(c['root'], path, expected_sha=sha(c['root'] / path),
                reviewer_label=path, decision='APPROVE', confirmed=True)
        except ArtifactError as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [c['manifest'], other]))
    assert sum('REVIEW_ALREADY_COMPLETED' in result for result in results) == 1
    assert len(local_poc.discover(c['root'])[0]) == 1


def test_reassessment_requires_exact_latest_receipt_and_reason(poc_context):
    c = poc_context
    first = submit(c)
    ref = {'path': first, 'sha256': sha(c['root'] / first)}
    for overrides in [{'revision_of': ref}, {'revision_reason': 'Reason alone'},
        {'revision_of': dict(ref, sha256='f' * 64), 'revision_reason': 'Wrong prior'},
        {'revision_of': ref, 'revision_reason': '   '}]:
        with pytest.raises(ArtifactError):
            submit(c, **overrides)
    second = submit(c, decision='REJECT', revision_of=ref, revision_reason='Explicit new source analysis')
    value = local_poc.read_record(c['root'], second)
    assert value['revision'] == 1 and value['previous_decision'] == ref
    assert value['revision_reason'] == 'Explicit new source analysis'
    with pytest.raises(ArtifactError):
        submit(c, revision_of=ref, revision_reason='Stale revision cannot overwrite newer decision')
    assert local_poc.discover(c['root'])[1] == 0


def test_modified_approved_answer_cannot_be_opened(poc_context):
    c = poc_context
    submit(c)
    path = c['root'] / c['package']['response_source']['result_path']
    value = read_json(path)
    value['response']['answer'] += ' New unsupported assertion.'
    path.write_text(__import__('json').dumps(value))
    assert local_poc.discover(c['root'])[1] == 1
    with pytest.raises(ArtifactError):
        submit(c)


def test_new_sealed_response_version_is_pending(poc_context):
    c = poc_context
    submit(c)
    row = copy.deepcopy(c['row'])
    row['response']['answer'] += ' A newly generated response version.'
    folder = c['root'] / 'data/evals/generation-runner/new-synthetic-version'
    save(folder / 'RESULT.json', row)
    save(folder / 'MANIFEST.json', {'mode': 'live', 'files': {'RESULT.json': sha(folder / 'RESULT.json')}})
    source = {'manifest_path': (folder / 'MANIFEST.json').relative_to(c['root']).as_posix(),
        'manifest_sha256': sha(folder / 'MANIFEST.json'),
        'result_path': (folder / 'RESULT.json').relative_to(c['root']).as_posix(), 'result_sha256': sha(folder / 'RESULT.json')}
    assessment = copy.deepcopy(c['package']['assessment_draft'])
    assessment['response_sha256'] = digest(row['response'])
    path = workflow.prepare(c['root'], source=source, question=c['package']['question'],
        assessment=assessment, trust=c['package']['trust'])
    p, _, _ = workflow.load_package(c['root'], path)
    assert current_decision(p, local_poc.discover(c['root'])[0]) is None
    app = app_for(c)
    assert not app.exception
    assert len(next(s for s in app.selectbox if s.label == 'Local POC review package').options) == 2


def test_expired_package_is_history_not_default(poc_context, monkeypatch):
    from datetime import timedelta
    c = poc_context
    stamp = workflow.utc() + timedelta(days=8)
    monkeypatch.setattr(workflow, 'utc', lambda: stamp)
    path = another_package(c)
    app = app_for(c)
    assert not app.exception
    assert any(path in str(j.value) for j in app.json)
    assert all(not b.disabled for b in app.button)


def test_markdown_is_rendered_as_answer(poc_context):
    app = app_for(poc_context)
    answer = poc_context['row']['response']['answer']
    assert any(answer == m.value for m in app.markdown)
    assert all(answer != t.value for t in app.text)
