import copy

import pytest

from tools.human_review import handoff, workflow
from tools.quality_dashboard.artifacts import ArtifactError, sha

from .conftest import assessment_input, publish


@pytest.mark.parametrize('status', ['ANSWERED', 'PARTIAL', 'ABSTAINED'])
@pytest.mark.parametrize('validation', ['REVIEW_REQUIRED', 'VALIDATION_FAILED'])
def test_every_completed_status_visible_without_semantic_invention(native, status, validation):
    publish(native, status=status, validation=validation)
    values = handoff.discover(native['root'])['entries']
    assert len(values) == 1
    e = values[0]
    assert e['row']['response']['status'] == status
    assert e['row']['post_validation']['overall_status'] == validation
    assert e['status'] == 'PENDING_ASSESSMENTS' and e['missing_assessments']
    assert not e['independent_semantic_acceptance']
    if status == 'ABSTAINED':
        assert not e['row']['response']['claims']


@pytest.mark.parametrize('mode', ['mock', 'dry-run'])
def test_offline_results_not_mistaken_for_real_review(native, mode):
    publish(native, mode=mode)
    assert not handoff.discover(native['root'])['entries']


def test_refresh_and_restart_are_read_only(native, monkeypatch):
    publish(native)
    def denied(*a, **kw):
        pytest.fail('DISCOVERY_MUST_NOT_PREPARE_OR_RECONSTRUCT')
    monkeypatch.setattr(workflow, 'prepare', denied)
    monkeypatch.setattr(workflow, 'live_context', denied)
    before = {p: sha(p) for p in native['root'].rglob('*') if p.is_file()}
    first, second = handoff.discover(native['root']), handoff.discover(native['root'])
    assert first == second and len(first['entries']) == 1
    assert before == {p: sha(p) for p in native['root'].rglob('*') if p.is_file()}


def test_pending_backfill_is_idempotent_without_approval(native):
    publish(native)
    first = handoff.synchronize(native['root'])
    assert first[0]['status'] == 'PENDING_ASSESSMENTS'
    assert first == handoff.synchronize(native['root'])
    assert len(list((native['root'] / handoff.BASE).glob('*/MANIFEST.json'))) == 1
    assert not list(native['root'].rglob('DECISION.json'))


def test_existing_assessment_automatically_prepares_once(native):
    publish(native)
    entry = handoff.discover(native['root'])['entries'][0]
    assessment_input(native, entry)
    first = handoff.synchronize(native['root'])
    assert first[0]['status'] == 'PACKAGE_PREPARED'
    p, _, _ = workflow.load_package(native['root'], first[0]['package_manifest'])
    assert p['assessment_draft'] == native['package']['assessment_draft']
    assert p['generation_authorized'] is False
    assert first == handoff.synchronize(native['root'])
    assert not list(native['root'].rglob('DECISION.json'))


def test_expired_package_renews_additively_and_restart_deduplicates(native, monkeypatch):
    from datetime import timedelta
    publish(native)
    assessment_input(native, handoff.discover(native['root'])['entries'][0])
    original = handoff.synchronize(native['root'])[0]
    stamp = workflow.utc() + timedelta(days=8)
    monkeypatch.setattr(workflow, 'utc', lambda: stamp)
    renewed = handoff.synchronize(native['root'])[0]
    assert renewed['package_manifest'] != original['package_manifest']
    assert handoff.synchronize(native['root'])[0] == renewed
    assert (native['root'] / original['package_manifest']).is_file()
    assert not list(native['root'].rglob('DECISION.json'))


@pytest.mark.parametrize('fault', ['response-hash', 'claim-hash', 'missing-claim', 'unreviewed-requirements', 'tamper'])
def test_incomplete_or_changed_assessment_stays_pending(native, fault):
    publish(native)
    entry = handoff.discover(native['root'])['entries'][0]
    value = copy.deepcopy(native['package']['assessment_draft'])
    if fault == 'response-hash': value['response_sha256'] = 'f' * 64
    if fault == 'claim-hash': value['claims'][0]['claim_sha256'] = 'f' * 64
    if fault == 'missing-claim': value['claims'].pop()
    if fault == 'unreviewed-requirements': value['question_requirements_reviewed'] = False
    folder = assessment_input(native, entry, assessment=value)
    if fault == 'tamper': (folder / 'ASSESSMENT.json').write_text('{}')
    e = handoff.discover(native['root'])['entries'][0]
    assert e['status'] == 'PENDING_ASSESSMENTS' and e['rejected_assessment_inputs'] == 1


@pytest.mark.parametrize('fault', ['result', 'unsealed', 'wrong-question'])
def test_tampered_or_unbound_native_result_fails_closed(native, fault, monkeypatch):
    run, _ = publish(native)
    if fault == 'result':
        (run / 'questions/SYNTHETIC-Q1/RESULT.json').write_text('{}')
    elif fault == 'unsealed':
        (run / 'MANIFEST.json').unlink()
    else:
        monkeypatch.setattr(handoff, 'inventory_context', lambda _: (None,
            {'SYNTHETIC-Q1': {'question': 'Another question'}}, {}, {}))
    assert not handoff.discover(native['root'])['entries']


def test_malformed_saved_handoff_blocks_reuse(native):
    publish(native)
    handoff.synchronize(native['root'])
    next((native['root'] / handoff.BASE).glob('*/HANDOFF.json')).write_text('{}')
    with pytest.raises(ArtifactError):
        handoff.synchronize(native['root'])


def test_post_seal_failure_never_retries_generation(native, monkeypatch):
    def fail(*a, **kw):
        raise OSError('synthetic storage failure')
    monkeypatch.setattr('tools.human_review.preparation.run', fail)
    assert handoff.after_generation(native['root'], 'synthetic/manifest') == []


def test_identical_answers_across_sources_group_with_source_history(native):
    publish(native, name='native-one')
    publish(native, name='native-two')
    entries = handoff.discover(native['root'])['entries']
    assert len(entries) == 1 and len(entries[0]['source_history']) == 1


def test_no_candidate_can_create_a_human_approval(native):
    publish(native)
    entry = handoff.discover(native['root'])['entries'][0]
    assessment_input(native, entry)
    values = handoff.synchronize(native['root'])
    assert values[0]['owner_approval_created'] is False
    assert not list(native['root'].rglob('APPROVAL.json'))
    assert not list(native['root'].rglob('HUMAN_ASSESSMENT.json'))
