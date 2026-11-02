"""Hash-bound review preparation and transactional, authenticated decisions.

No generation imports/calls. Only explicit decision submission reconstructs M8;
navigation and previews read sealed, source-free records. Private keys stay in
the operator's OS-protected store, outside the project/evaluation tree.
"""
import copy
import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from tools.answer_quality.review import Assessment, HumanReview, bound_assessment
from tools.preflight_suite.artifacts import now, save
from tools.quality_dashboard.artifacts import (
    ArtifactError,
    Store,
    digest,
    read_json,
    safe_path,
    sha,
)

from .identity import authenticate, locked, registry, verify, write_new

PACKAGE_SCHEMA = 'human-review-package-1.0'
DECISION_SCHEMA = 'signed-human-review-decision-1.0'
PACKAGE_BASE = 'data/evals/human-review/packages'
EVALUATION_BASE = 'data/evals/answer-quality'
POLICY = 'tools/human_review/POLICY.json'


def utc():
    return datetime.now(UTC)


def check_time(value, *, future=False):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or (stamp <= utc() if future else stamp > utc() + timedelta(seconds=30)):
        raise ArtifactError('STALE_OR_INVALID_REVIEW_TIMESTAMP')


def output_directory(root, relative):
    path = Path(root) / relative
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ArtifactError('UNSAFE_REVIEW_OUTPUT_PATH')
    path.mkdir(parents=True, mode=0o700)
    return path


def trust_check(root, reference, _seen=None):
    from tools.generation_runner.trust import bound, load_trust
    from tools.generation_trust_anchor import HUMAN_REVIEW_TRUST_MIGRATIONS
    transition = HUMAN_REVIEW_TRUST_MIGRATIONS.get(reference['path'])
    if transition is not None:
        seen = set() if _seen is None else set(_seen)
        if reference['path'] in seen:
            raise ArtifactError('REVIEW_TRUST_TRANSITION_CYCLE')
        seen.add(reference['path'])
        if reference['sha256'] != transition['parent_sha256']:
            raise ArtifactError('REVIEW_TRUST_PARENT_MISMATCH')
        parent = bound(root, reference['path'], reference['sha256'])
        base = reference['path'].rsplit('/', 1)[0]
        for name, expected in parent['files'].items():
            bound(root, base + '/' + name, expected)
        target = transition['successor']
        child = bound(root, target['path'], target['sha256'])
        manifest, policy, result = trust_check(root, target, seen)
        if (child.get('parent_manifest_sha256') != reference['sha256']
                or policy['human_review_contract'] != bound(root, base + '/POLICY.json',
                    parent['files']['POLICY.json'])['human_review_contract']):
            raise ArtifactError('REVIEW_TRUST_CONTRACT_CHANGED')
        effective = result.get('review_only_trust_transition', {}).get('effective', target)
        result = result | {'review_only_trust_transition': {'requested': reference, 'effective': effective}}
        return manifest, policy, result
    return load_trust(root, reference['path'], reference['sha256'])


def source_record(root, source):
    store = Store(root)
    manifest = store.manifest(source['manifest_path'], expected=source['manifest_sha256'])
    base = source['manifest_path'].rsplit('/', 1)[0] + '/'
    relative = source['result_path'].removeprefix(base)
    if (not source['result_path'].startswith(base)
            or manifest['files'].get(relative) != source['result_sha256']
            or manifest.get('mode') != 'live'):
        raise ArtifactError('COMPLETED_LIVE_RESULT_REQUIRED')
    store.bind(source['result_path'], source['result_sha256'])
    row = store.json(source['result_path'])
    if not row.get('generation_executed') or not row.get('response') or row.get('fixture_only'):
        raise ArtifactError('ACTUAL_GENERATED_RESPONSE_REQUIRED')
    return row


def prepare(root, *, source, question, assessment, trust, supporting_artifacts=None, layout_reviews=(),
            validation_policy=None):
    """Unsigned preparation only; cannot enroll a reviewer or approve a draft."""
    _, _, trust_receipt = trust_check(root, trust)
    trust = trust_receipt.get('review_only_trust_transition', {}).get('effective', trust)
    selected_policy = validation_policy or {'path': 'tools/answer_quality/POLICY.json',
        'sha256': sha(Path(root) / 'tools/answer_quality/POLICY.json')}
    from tools.answer_quality.current import validator_for
    validator_for(root, selected_policy)
    row = source_record(root, source)
    value = Assessment.model_validate(assessment).model_dump()
    bindings = {'question_sha256': hashlib.sha256(question.encode()).hexdigest(),
        'response_sha256': digest(row['response']), 'package_sha256': row['M8_package_sha256'],
        'request_sha256': row['request_sha256']}
    if any(value[k] != v for k, v in bindings.items()) or row['question_sha256'] != bindings['question_sha256']:
        raise ArtifactError('REVIEW_DRAFT_BINDING_MISMATCH')
    support = supporting_artifacts or {}
    for name, h in support.items():
        if sha(safe_path(root, name)) != h:
            raise ArtifactError('REVIEW_SUPPORT_CHANGED')
    # Layout equivalence must reference a sealed, separately inspected forensic record.
    for record in layout_reviews:
        path = record['review_id'].split('#')[0]
        if path not in support:
            raise ArtifactError('UNBOUND_LAYOUT_REVIEW')
    identity = 'review-' + uuid4().hex
    folder = output_directory(root, PACKAGE_BASE + '/' + identity)
    result = {'schema': PACKAGE_SCHEMA, 'review_id': identity, 'question_id': row['question_id'],
        'question': question, 'created_at': now(), 'expires_at': (utc() + timedelta(days=7)).isoformat(),
        'response_source': source, 'bindings': bindings, 'assessment_draft': value,
        'assessment_draft_sha256': digest(value), 'trust': trust,
        'policy': selected_policy,
        'approval_policy_sha256': sha(Path(root) / POLICY), 'supporting_artifacts': support,
        'layout_reviews': list(layout_reviews), 'generation_authorized': False,
        'status': 'AWAITING_AUTHENTICATED_EXPLICIT_CONFIRMATION'}
    save(folder / 'REVIEW_PACKAGE.json', result)
    save(folder / 'MANIFEST.json', {'schema': PACKAGE_SCHEMA, 'review_id': identity,
        'files': {'REVIEW_PACKAGE.json': sha(folder / 'REVIEW_PACKAGE.json')}})
    return (folder / 'MANIFEST.json').relative_to(root).as_posix()


def load_package(root, manifest_path, *, expected=None, require_fresh=True):
    store = Store(root)
    manifest = store.manifest(manifest_path, expected=expected, schema=PACKAGE_SCHEMA)
    base = manifest_path.rsplit('/', 1)[0]
    p = store.json(base + '/REVIEW_PACKAGE.json')
    if (p['schema'] != PACKAGE_SCHEMA or p['review_id'] != manifest['review_id']
            or digest(p['assessment_draft']) != p['assessment_draft_sha256']
            or p['generation_authorized'] is not False
            or sha(Path(root) / POLICY) != p['approval_policy_sha256']
            or sha(safe_path(root, p['policy']['path'])) != p['policy']['sha256']):
        raise ArtifactError('REVIEW_PACKAGE_OR_POLICY_CHANGED')
    if require_fresh:
        check_time(p['expires_at'], future=True)
    check_time(p['created_at'])
    row = source_record(root, p['response_source'])
    if (row['question_id'] != p['question_id'] or digest(row['response']) != p['bindings']['response_sha256']
            or row['question_sha256'] != hashlib.sha256(p['question'].encode()).hexdigest()
            or row['M8_package_sha256'] != p['bindings']['package_sha256']
            or row['request_sha256'] != p['bindings']['request_sha256']):
        raise ArtifactError('REVIEW_RESPONSE_OR_EVIDENCE_CHANGED')
    for name, h in p['supporting_artifacts'].items():
        store.bind(name, h)
    return p, row, sha(safe_path(root, manifest_path))


def live_context(root, package, row):
    """Existing accepted M7/M8 path only, no retrieval, prompt or provider call."""
    from tools.evidence.service import EvidenceService
    from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA
    from tools.preflight_suite.artifacts import COMPLETION, baseline

    if row.get('question_source') == 'BOT':
        from tools.bot_runtime.store import verify_reference
        original = verify_reference(root, row['question_id'], row['question_reference'])
        question = original['question']
        store = Store(root)
        store.bind(row['candidate_artifact'], row['candidate_artifact_sha256'])
        candidate_path = row['candidate_artifact']
    else:
        store, inventory = baseline(root)
        question = inventory[package['question_id']]['question']
        candidate_path = COMPLETION + '/m7/' + package['question_id'] + '.json'
    if question != package['question']:
        raise ArtifactError('ORIGINAL_QUESTION_CHANGED')
    m7 = store.json(candidate_path)
    service = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
    evidence = service.assemble(m7, token_budget=128000)
    if (digest(m7) != row['M7_result_sha256'] or digest(evidence) != row['M8_package_sha256']
            or service.validate(evidence, m7) is not True):
        raise ArtifactError('FRESH_M8_OR_SAVED_M7_BINDING_FAILED')
    return service, evidence, m7


def confirmation_text(decision, question_id, package_sha):
    return f'{decision} {question_id} {package_sha}'


def target_identity(package):
    return digest({'question_id': package['question_id'], 'bindings': package['bindings'],
                   'assessment': package['assessment_draft_sha256'], 'policy': package['policy'],
                   'approval_policy': package['approval_policy_sha256']})


def verify_decision(root, store, manifest_path, *, package_manifest=None):
    """Signature verified BEFORE deriving the hash/allowlist for HumanReview."""
    state = registry(store)
    s = Store(root)
    manifest = s.manifest(manifest_path, schema='answer-quality-evaluation-2.0')
    base = manifest_path.rsplit('/', 1)[0]
    record = s.json(base + '/APPROVAL.json')
    body = record['decision']
    if (state['revoked'] or body['schema'] != DECISION_SCHEMA
            or body['reviewer_id'] != state['reviewer_id'] or body['public_key'] != state['public_key']
            or body['enrollment_sha256'] != state['enrollment_sha256']
            or body['registry_head_sha256'] != state['head_sha256']):
        raise ArtifactError('REVIEWER_UNKNOWN_REVOKED_OR_KEY_ROTATED')
    verify(body, record['signature'], state['public_key'])
    check_time(body['decided_at'])
    p, row, ph = load_package(root, body['package_manifest'],
                              expected=body['package_manifest_sha256'], require_fresh=False)
    if package_manifest is not None and body['package_manifest'] != package_manifest:
        raise ArtifactError('REVIEW_FOR_DIFFERENT_PACKAGE')
    if (body['bindings'] != p['bindings'] or body['question_id'] != p['question_id']
            or body['policy'] != p['policy'] or body['target_sha256'] != target_identity(p)
            or body['approval_policy_sha256'] != p['approval_policy_sha256']
            or body['package_manifest_sha256'] != ph
            or body['confirmation'] != confirmation_text(body['outcome'], p['question_id'], ph)
            or body['outcome'] not in {'APPROVE', 'REJECT', 'REQUEST_CHANGES'}
            or body['generation_authorized'] is not False):
        raise ArtifactError('SIGNED_REVIEW_BINDING_MISMATCH')
    assessment_path = base + '/HUMAN_ASSESSMENT.json'
    if body['outcome'] == 'APPROVE':
        if manifest['files'].get('HUMAN_ASSESSMENT.json') != body['assessment_sha256']:
            raise ArtifactError('SIGNED_ASSESSMENT_HASH_MISMATCH')
        human = HumanReview(root, assessment_path, body['assessment_sha256'],
                            approved_reviewers={state['reviewer_id']})
        expected = copy.deepcopy(p['assessment_draft'])
        expected.update(method='HUMAN_REVIEW', reviewer=body['reviewer_id'],
                        assessed_at=body['decided_at'], independent_of_generator=True)
        if human.value.model_dump() != expected:
            raise ArtifactError('SIGNED_REVIEW_IDENTITY_TIMESTAMP_MISMATCH')
    elif body['assessment_sha256'] != p['assessment_draft_sha256']:
        raise ArtifactError('SIGNED_REJECTED_ASSESSMENT_HASH_MISMATCH')
    evaluation = s.json(base + '/ASSESSMENT.json')
    if digest(evaluation) != body['evaluation_sha256']:
        raise ArtifactError('SIGNED_EVALUATION_CHANGED')
    if (evaluation['question_id'] != p['question_id'] or evaluation['response_sha256'] != digest(row['response'])
            or evaluation['request_sha256'] != p['bindings']['request_sha256']
            or manifest['response_source'] != p['response_source']
            or manifest['response_sha256'] != evaluation['response_sha256']
            or manifest['request_sha256'] != evaluation['request_sha256']):
        raise ArtifactError('SIGNED_EVALUATION_IDENTITY_MISMATCH')
    return body, evaluation


def decide(root, store, manifest_path, *, expected_sha, reviewer_id, passphrase, decision,
           confirmation, note=''):
    if Path(store).resolve().is_relative_to(Path(root).resolve()):
        raise ArtifactError('SIGNING_CREDENTIALS_MUST_BE_OUTSIDE_PROJECT')
    if decision not in {'APPROVE', 'REJECT', 'REQUEST_CHANGES'}:
        raise ArtifactError('EXPLICIT_REVIEW_DECISION_REQUIRED')
    p, row, ph = load_package(root, manifest_path, expected=expected_sha)
    if confirmation != confirmation_text(decision, p['question_id'], ph):
        raise ArtifactError('FRESH_HASH_BOUND_CONFIRMATION_REQUIRED')
    with locked(store):
        state = registry(store)
        # Authentication happens on THIS decision, never a cached UI login/name.
        challenge = {'review_id': p['review_id'], 'package_sha256': ph, 'decision': decision,
                     'nonce': uuid4().hex}
        authenticate(store, reviewer_id, passphrase, challenge)
        trust_check(root, p['trust'])
        target = target_identity(p)
        ledger = Path(store) / 'decisions'
        ledger.mkdir(mode=0o700, exist_ok=True)
        marker = ledger / (target + '.json')
        if marker.exists():
            raise ArtifactError('DUPLICATE_OR_INTERRUPTED_REVIEW_DECISION')
        # A second package cannot bypass duplicate prevention for the same assessment.
        for file in (Path(root) / EVALUATION_BASE).glob('human-review-*/MANIFEST.json'):
            record = read_json(file.parent / 'APPROVAL.json')
            if record['decision']['target_sha256'] == target:
                raise ArtifactError('DUPLICATE_REVIEW_DECISION')
        service, evidence, m7 = live_context(root, p, row)
        from tools.answer_quality.current import validator_for
        from tools.answer_quality.fidelity import source_fields
        PostGenerationValidator = validator_for(root, p['policy'])

        fields = {(parent['evidence']['unit_id'], pointer): text
            for parent in evidence['parents'] for pointer, text in source_fields(parent['evidence']['verified_parent'])}
        bound_assessment(p['assessment_draft'], question=p['question'], response=row['response'],
                         package=evidence, request_sha256=row['request_sha256'], fields=fields)
        decided_at = now()
        identity = 'human-review-' + uuid4().hex
        stage = output_directory(root, 'data/evals/human-review/pending/' + identity)
        body = {'schema': DECISION_SCHEMA, 'outcome': decision, 'reviewer_id': reviewer_id,
            'display_name': state['display_name'], 'public_key': state['public_key'],
            'enrollment_sha256': state['enrollment_sha256'], 'registry_head_sha256': state['head_sha256'],
            'decided_at': decided_at, 'package_manifest': manifest_path, 'package_manifest_sha256': ph,
            'question_id': p['question_id'], 'bindings': p['bindings'], 'policy': p['policy'],
            'approval_policy_sha256': p['approval_policy_sha256'], 'target_sha256': target,
            'confirmation': confirmation, 'note': note, 'generation_authorized': False}
        if decision == 'APPROVE':
            value = copy.deepcopy(p['assessment_draft'])
            value.update(method='HUMAN_REVIEW', reviewer=reviewer_id, assessed_at=decided_at,
                         independent_of_generator=True)
            save(stage / 'HUMAN_ASSESSMENT.json', Assessment.model_validate(value).model_dump())
            body['assessment_sha256'] = sha(stage / 'HUMAN_ASSESSMENT.json')
            # Only the authenticated signature supplies externally trusted importer inputs.
            _, signature = authenticate(store, reviewer_id, passphrase, body)
            verify(body, signature, state['public_key'])
            human = HumanReview(root, (stage / 'HUMAN_ASSESSMENT.json').relative_to(root).as_posix(),
                body['assessment_sha256'], approved_reviewers={reviewer_id})
            result = PostGenerationValidator(service, assessor=human, layout_reviews=p['layout_reviews']).validate(
                row['response'], evidence, m7, question=p['question'], request_binding=row)
        else:
            body['assessment_sha256'] = p['assessment_draft_sha256']
            result = PostGenerationValidator(service, layout_reviews=p['layout_reviews']).validate(
                row['response'], evidence, m7, question=p['question'], request_binding=row)
            result['fully_validated'] = False
            result['overall_status'] = ('VALIDATION_FAILED' if decision == 'REJECT'
                                        or result['overall_status'] == 'VALIDATION_FAILED' else 'REVIEW_REQUIRED')
            result['review_reasons'] = result.get('review_reasons', []) + ['OWNER_' + decision]
        result.update(question_id=p['question_id'], question=p['question'], answer=row['response']['answer'],
            response_sha256=p['bindings']['response_sha256'], request_sha256=p['bindings']['request_sha256'],
            M8_package_sha256=p['bindings']['package_sha256'], question_sha256=p['bindings']['question_sha256'])
        # Replace staging-only importer reference with its final location before signing.
        final = Path(root) / EVALUATION_BASE / identity
        if any(p.is_symlink() for p in [final, *final.parents]):
            raise ArtifactError('UNSAFE_REVIEW_OUTPUT_PATH')
        final.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if result.get('review_provenance'):
            result['review_provenance']['path'] = (final / 'HUMAN_ASSESSMENT.json').relative_to(root).as_posix()
        body['evaluation_sha256'] = digest(result)
        _, signature = authenticate(store, reviewer_id, passphrase, body)
        verify(body, signature, state['public_key'])
        save(stage / 'ASSESSMENT.json', result)
        save(stage / 'APPROVAL.json', {'decision': body, 'signature': signature})
        save(stage / 'MANIFEST.json', {'schema': 'answer-quality-evaluation-2.0', 'question_id': p['question_id'],
            'response_sha256': p['bindings']['response_sha256'], 'request_sha256': row['request_sha256'],
            'response_source': p['response_source'], 'authenticated_review': True,
            'generation_authorized': False, 'created_at': decided_at,
            'files': {f.name: sha(f) for f in stage.iterdir()}})
        # Fully verify the proposed publication before it becomes discoverable.
        verify_decision(root, store, (stage / 'MANIFEST.json').relative_to(root).as_posix())
        # Detect changes after slow M8 validation; no earlier preview is a bearer token.
        load_package(root, manifest_path, expected=ph)
        trust_check(root, p['trust'])
        service.check()
        write_new(marker, {'target': target, 'outcome': decision,
            'final_manifest': (final / 'MANIFEST.json').relative_to(root).as_posix(),
            'stage': stage.relative_to(root).as_posix(), 'created_at': decided_at})
        os.rename(stage, final)  # Single same-filesystem commit; no partial accepted publication.
        return (final / 'MANIFEST.json').relative_to(root).as_posix()


def recover(root, store, target, *, reviewer_id, passphrase, confirmation):
    """Explicit authenticated abort of an interrupted, NEVER published decision."""
    if not isinstance(target, str) or len(target) != 64 or any(c not in '0123456789abcdef' for c in target):
        raise ArtifactError('INVALID_REVIEW_RECOVERY_TARGET')
    if confirmation != 'ABORT ' + target:
        raise ArtifactError('EXPLICIT_RECOVERY_CONFIRMATION_REQUIRED')
    with locked(store):
        marker = Path(store) / 'decisions' / (target + '.json')
        value = read_json(marker)
        if (Path(root) / value['final_manifest']).exists():
            raise ArtifactError('PUBLISHED_REVIEW_CANNOT_BE_ABORTED')
        body = {'operation': 'ABORT_UNPUBLISHED_REVIEW', 'target': target,
                'reviewer_id': reviewer_id, 'created_at': now(), 'marker_sha256': sha(marker)}
        _, signature = authenticate(store, reviewer_id, passphrase, body)
        write_new(marker.with_suffix('.abort-' + uuid4().hex + '.json'),
                  {'event': body, 'signature': signature, 'original_marker': value})
        os.rename(marker, marker.with_suffix('.interrupted-' + uuid4().hex + '.json'))
        return 'UNPUBLISHED_REVIEW_ABORTED_NO_ACCEPTANCE'
