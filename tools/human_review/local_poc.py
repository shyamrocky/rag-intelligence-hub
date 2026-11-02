"""Unsigned localhost POC decisions, separate from authenticated HumanReview.

No key/identity enrollment, trusted human import, generation or provider calls.
The existing validator enforces technical checks; POC approval never becomes
cryptographically authenticated VALIDATED status.
"""
import fcntl
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from tools.preflight_suite.artifacts import now, save
from tools.quality_dashboard.artifacts import ArtifactError, Store, digest, sha

from . import workflow
from .review_state import record_identity, target_identity

MODE = 'LOCAL_POC_REVIEW'
SCHEMA = 'local-poc-review-1.0'
SUCCESSOR_SCHEMA = 'local-poc-review-1.1'
BASE = 'data/evals/human-review/local-poc'
POLICY = 'tools/human_review/local-poc-policy-1.0.json'
OUTCOMES = {'APPROVE', 'REJECT', 'REQUEST_CHANGES'}


def loopback(host):
    if host == 'localhost':
        return True
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or bool(getattr(address, 'ipv4_mapped', None)
                                          and address.ipv4_mapped.is_loopback)
    except (ValueError, TypeError):
        return False


def local_access():
    """Server configuration is authoritative; client-provided labels cannot enable this."""
    import streamlit as st

    return {'bind': st.get_option('server.address'), 'headers': dict(st.context.headers),
            'peer': st.context.ip_address}


def require_localhost():
    context = local_access()
    headers = {key.lower(): value for key, value in context['headers'].items()}
    host = urlsplit('http://' + headers.get('host', '')).hostname
    origin = headers.get('origin')
    # Streamlit returns peer=None for real loopback clients. Missing Host still blocks
    # headless/non-web callers. Reject proxy forwarding rather than trusting it.
    if (not loopback(context['bind']) or not loopback(host)
            or (context['peer'] is not None and not loopback(context['peer']))
            or any(key in headers for key in ('forwarded', 'x-forwarded-for', 'x-forwarded-host'))
            or (origin and (urlsplit(origin).scheme not in {'http', 'https'}
                            or not loopback(urlsplit(origin).hostname)))):
        raise ArtifactError('LOCAL_POC_REQUIRES_DIRECT_LOCALHOST_SERVER')


def technical_check(root, package, row):
    """Fresh unchanged M8 and v2 checks; no semantic certification or persistence."""
    from tools.answer_quality.current import validator_for
    from tools.answer_quality.fidelity import source_fields
    from tools.answer_quality.review import bound_assessment

    _, _, trust_receipt = workflow.trust_check(root, package['trust'])
    service, evidence, m7 = workflow.live_context(root, package, row)
    fields = {(parent['evidence']['unit_id'], pointer): text for parent in evidence['parents']
              for pointer, text in source_fields(parent['evidence']['verified_parent'])}
    bound_assessment(package['assessment_draft'], question=package['question'], response=row['response'],
        package=evidence, request_sha256=row['request_sha256'], fields=fields)
    result = validator_for(root, package['policy'])(service, layout_reviews=package['layout_reviews']).validate(
        row['response'], evidence, m7, question=package['question'], request_binding=row)
    if trust_receipt.get('review_only_trust_transition'):
        result['review_trust_transition'] = trust_receipt['review_only_trust_transition']
    service.check()
    return result


def technical_pass(result):
    return (result.get('source_integrity') == 'LIVE_M8_VALIDATED'
            and result.get('structural_validation') == 'PASS'
            and result.get('citation_validity') == 'PASS'
            and result.get('overall_status') != 'VALIDATION_FAILED')


def status(decision, checks):
    if not technical_pass(checks):
        return 'BLOCKED_TECHNICAL'
    return {'APPROVE': 'OWNER_APPROVED_POC', 'REJECT': 'OWNER_REJECTED_POC',
            'REQUEST_CHANGES': 'OWNER_REQUESTED_CHANGES_POC'}[decision]


def read_record(root, manifest_path):
    store = Store(root)
    m = store.manifest(manifest_path)
    if m['schema'] not in {SCHEMA, SUCCESSOR_SCHEMA, 'local-poc-review-1.2'}:
        raise ArtifactError('INVALID_LOCAL_POC_SCHEMA')
    base = manifest_path.rsplit('/', 1)[0]
    value = store.json(base + '/DECISION.json')
    p, _row, _fingerprint = workflow.load_package(root, value['package_manifest'],
        expected=value['package_manifest_sha256'], require_fresh=False)
    if (value['schema'] != m['schema'] or value['mode'] != MODE or value['decision'] not in OUTCOMES
            or value['authenticated'] is not False or value['fully_validated'] is not False
            or value['generation_authorized'] is not False or value['bindings'] != p['bindings']
            or value['question_id'] != p['question_id'] or value['assessment_sha256'] != p['assessment_draft_sha256']
            or value['evidence_policy'] != p['policy']
            or value['local_poc_policy_sha256'] != sha(Path(root) / POLICY)
            or not value['reviewer_label'].strip() or value['explicit_confirmation'] is not True
            or value['status'] != status(value['decision'], value['technical_validation'])
            or m['status'] != value['status'] or m['mode'] != MODE
            or value['duplicate_key'] != duplicate_key(p, value['decision'], value['reviewer_label'], value['owner_notes'])):
        raise ArtifactError('INVALID_LOCAL_POC_RECORD')
    checks = value['technical_validation']
    if technical_pass(checks) and (
            checks.get('response_sha256') != p['bindings']['response_sha256']
            or checks.get('M8_package_sha256') != p['bindings']['package_sha256']
            or checks.get('request_sha256') != p['bindings']['request_sha256']
            or checks.get('fully_validated') is not False
            or checks.get('independent_human_acceptance') is not False):
        raise ArtifactError('LOCAL_POC_TECHNICAL_BINDING_MISMATCH')
    workflow.check_time(value['decided_at'])
    if value['schema'] in {SUCCESSOR_SCHEMA, 'local-poc-review-1.2'}:
        previous = value['previous_decision']
        if (value['logical_target_sha256'] != target_identity(p)
                or type(value['revision']) is not int or value['revision'] < 0
                or not isinstance(value['revision_reason'], str)
                or (value['revision'] == 0 and (previous is not None or value['revision_reason']))
                or (value['revision'] > 0 and (not isinstance(previous, dict)
                    or set(previous) != {'path', 'sha256'} or not value['revision_reason'].strip()))):
            raise ArtifactError('INVALID_LOCAL_POC_REVISION')
    return value


def discover(root, *, question_id=None):
    rows, rejected = [], 0
    for file in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        try:
            path = file.relative_to(root).as_posix()
            row = read_record(root, path)
            if question_id is None or row['question_id'] == question_id:
                rows.append((row, path))
        except (ArtifactError, ValueError, OSError, KeyError, TypeError):
            rejected += 1
    rows.sort(key=lambda item: (item[0]['decided_at'], item[1]))
    latest = {}
    verified = []
    for value, path in rows:
        target = record_identity(value)
        prior = latest.get(target)
        if value['schema'] in {SUCCESSOR_SCHEMA, 'local-poc-review-1.2'}:
            if value['schema'] == 'local-poc-review-1.2':
                from .review_state import latest_answer_decision
                prior = latest_answer_decision(value, verified)
            expected = {'path': prior[1], 'sha256': sha(Path(root) / prior[1])} if prior else None
            if (value['previous_decision'] != expected
                    or value['revision'] != (prior[0].get('revision', 0) + 1 if prior else 0)):
                rejected += 1
                continue
        verified.append((value, path))
        if value['status'] != 'BLOCKED_TECHNICAL':
            latest[target] = (value, path)
    return verified, rejected


def duplicate_key(package, decision, label, notes):
    return digest({'target': workflow.target_identity(package), 'decision': decision,
                   'label': label, 'notes': notes})


def decide(root, manifest_path, *, expected_sha, reviewer_label, decision, confirmed, notes='',
           revision_of=None, revision_reason=''):
    require_localhost()  # Checked again on submission, never a cached UI boolean.
    if (decision not in OUTCOMES or confirmed is not True or not isinstance(reviewer_label, str)
            or not reviewer_label.strip() or len(reviewer_label) > 100
            or any(ord(c) < 32 for c in reviewer_label) or not isinstance(notes, str) or len(notes) > 5000):
        raise ArtifactError('EXPLICIT_LOCAL_POC_CONFIRMATION_AND_REVIEWER_LABEL_REQUIRED')
    reviewer_label, notes = reviewer_label.strip(), notes.strip()
    p, row, fingerprint = workflow.load_package(root, manifest_path, expected=expected_sha)
    workspace = Path(root) / 'workspace/local-poc-review'
    if any(path.is_symlink() for path in [workspace, *workspace.parents]):
        raise ArtifactError('UNSAFE_LOCAL_REVIEW_DIRECTORY')
    workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(workspace / 'REVIEW.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        key = duplicate_key(p, decision, reviewer_label, notes)
        previous, rejected = discover(root)
        if rejected:
            raise ArtifactError('UNVERIFIED_LOCAL_POC_HISTORY')
        from .review_state import latest_answer_decision
        current = latest_answer_decision(p, previous)
        if current and revision_of is None:
            raise ArtifactError('DUPLICATE_LOCAL_POC_DECISION_REVIEW_ALREADY_COMPLETED')
        if revision_of is not None and (not current or revision_of != {
                'path': current[1], 'sha256': sha(Path(root) / current[1])}
                or not isinstance(revision_reason, str) or not revision_reason.strip()
                or len(revision_reason) > 5000):
            raise ArtifactError('EXPLICIT_CURRENT_REVIEW_REVISION_AND_REASON_REQUIRED')
        if revision_of is None and revision_reason:
            raise ArtifactError('EXPLICIT_CURRENT_REVIEW_REVISION_AND_REASON_REQUIRED')
        if revision_of is None and any(v['duplicate_key'] == key for v, _ in previous):
            raise ArtifactError('DUPLICATE_LOCAL_POC_DECISION')
        if decision == 'APPROVE':
            from .preparation import approval_ready
            if not approval_ready(p['assessment_draft'], row['response']):
                raise ArtifactError('UNRESOLVED_OWNER_JUDGMENTS_PREVENT_APPROVAL')
        checks = technical_check(root, p, row)
        require_localhost()
        workflow.load_package(root, manifest_path, expected=fingerprint)
        workflow.trust_check(root, p['trust'])
        value = {'schema': 'local-poc-review-1.2', 'mode': MODE, 'decision': decision,
            'status': status(decision, checks), 'reviewer_label': reviewer_label, 'owner_notes': notes,
            'decided_at': now(), 'question_id': p['question_id'], 'bindings': p['bindings'],
            'assessment_sha256': p['assessment_draft_sha256'], 'evidence_policy': p['policy'],
            'local_poc_policy_sha256': sha(Path(root) / POLICY), 'technical_validation': checks,
            'package_manifest': manifest_path, 'package_manifest_sha256': fingerprint,
            'duplicate_key': key, 'explicit_confirmation': True, 'authenticated': False,
            'authentication': 'NONE_LOCAL_OWNER_ATTESTATION_ONLY', 'fully_validated': False,
            'generation_authorized': False, 'logical_target_sha256': target_identity(p),
            'revision': current[0].get('revision', 0) + 1 if current else 0,
            'previous_decision': revision_of, 'revision_reason': revision_reason.strip()}
        identity = 'poc-' + uuid4().hex
        pending = workflow.output_directory(root, 'data/evals/human-review/local-poc-pending/' + identity)
        final = Path(root) / BASE / identity
        if any(path.is_symlink() for path in [final, *final.parents]):
            raise ArtifactError('UNSAFE_LOCAL_REVIEW_DIRECTORY')
        final.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        save(pending / 'DECISION.json', value)
        save(pending / 'MANIFEST.json', {'schema': value['schema'], 'mode': MODE, 'status': value['status'],
            'files': {'DECISION.json': sha(pending / 'DECISION.json')}})
        read_record(root, (pending / 'MANIFEST.json').relative_to(root).as_posix())
        os.rename(pending, final)
        return (final / 'MANIFEST.json').relative_to(root).as_posix()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
