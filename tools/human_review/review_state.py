"""Answer-level identity and read-only package/decision projection for local review.

Assessment drafts, trust migrations and package renewals are history of the same
answer, not permission for another decision. Policy or evidence changes are new
targets. This identity does not replace signed HumanReview's stricter contract.
"""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store, digest


def package_history(root):
    """Expired, intact packages stay inspectable but never become submission targets."""
    from .workflow import PACKAGE_BASE, load_package
    values = []
    for file in sorted((Path(root) / PACKAGE_BASE).glob('*/MANIFEST.json')):
        try:
            path = file.relative_to(root).as_posix()
            p, row, fingerprint = load_package(root, path, require_fresh=False)
            values.append((path, p, row, fingerprint))
        except (ArtifactError, KeyError, TypeError, ValueError, OSError):
            continue
    return values


def target_identity(package):
    return digest({'question_id': package['question_id'],
        'bindings': {k: package['bindings'][k] for k in (
            'question_sha256', 'response_sha256', 'package_sha256', 'request_sha256')},
        'validation_policy': package['policy']})


def record_identity(record):
    return target_identity({'question_id': record['question_id'],
        'bindings': record['bindings'], 'policy': record['evidence_policy']})


def answer_identity(package):
    """Cross-policy duplicate guard only; never transfers a policy approval."""
    return digest({'question_id': package['question_id'], 'bindings': {
        k: package['bindings'][k] for k in ('question_sha256', 'response_sha256',
            'package_sha256', 'request_sha256')}})


def latest_answer_decision(package, history):
    rows = [(v, path) for v, path in history if answer_identity(v) == answer_identity(package)]
    return max(rows, key=lambda item: (item[0]['decided_at'], item[1])) if rows else None


def recorded_review_required(root, receipt):
    """Verified display projection only; never an approval or eligibility override.

    The existing source-bound preparation and owner completeness receipt already
    record this disposition. Old negative decisions stay in history and retain
    their duplicate locks. No M8, provider or decision operation is invoked here.
    """
    p = receipt['prepared'][1]
    checks = receipt['materials']['fresh_technical_validation']
    expected = {'question_sha256': 'question_sha256', 'response_sha256': 'response_sha256',
        'package_sha256': 'M8_package_sha256', 'request_sha256': 'request_sha256'}
    if (checks.get('overall_status') != 'REVIEW_REQUIRED'
            or checks.get('source_integrity') != 'LIVE_M8_VALIDATED'
            or checks.get('structural_validation') != 'PASS' or checks.get('citation_validity') != 'PASS'
            or any(checks.get(field) != p['bindings'][key] for key, field in expected.items())):
        return False
    for name, fingerprint in p['supporting_artifacts'].items():
        if not name.endswith('/OWNER_DECISION_RECEIPT.json'):
            continue
        store = Store(root)
        store.bind(name, fingerprint)
        record = store.json(name)
        context, decisions = record.get('context', {}), record.get('decisions', {})
        if (record.get('schema') == 'owner-decision-receipt-1.0'
                and record.get('question_id') == p['question_id']
                and all(context.get(key) == value for key, value in p['bindings'].items())
                and context.get('validation_policy') == p['policy']
                and record.get('status') == 'OWNER_COMPLETENESS_RECORDED_GROUNDING_REVIEW_REQUIRED'
                and decisions.get('semantic_completeness') == 'ANSWERED'
                and decisions.get('source_grounding') == 'NOT_APPROVED_PENDING_ORIGINAL_EVIDENCE_ASSESSMENT'
                and record.get('not_a_generation_or_spending_authorization') is True
                and record.get('authenticated_human_review_accepted') is False):
            return True
    return False


def status_label(package, history, *, review_required=False):
    current = current_decision(package, history)
    related = latest_answer_decision(package, history)
    value = related or current
    if review_required and (not value or value[0]['status'] == 'BLOCKED_TECHNICAL'):
        return 'REVIEW_REQUIRED'
    if not value:
        return 'Pending Review'
    record = value[0]
    label = {'APPROVE': 'Approved (Local POC)', 'REJECT': 'Rejected',
             'REQUEST_CHANGES': 'Changes Requested'}[record['decision']]
    if record['status'] == 'BLOCKED_TECHNICAL':
        label = ('Approval Blocked' if record['decision'] == 'APPROVE' else label) + ' — Technical Block Recorded'
    if record['evidence_policy'] != package['policy']:
        label += ' (previous policy; reassessment required)'
    return label


def current_decision(package, history):
    matches = [(v, path) for v, path in history
        if record_identity(v) == target_identity(package) and v['status'] != 'BLOCKED_TECHNICAL']
    return max(matches, key=lambda item: (item[0]['decided_at'], item[1])) if matches else None


def group_packages(values):
    groups = {}
    for item in values:
        groups.setdefault(target_identity(item[1]), []).append(item)
    return [sorted(items, key=lambda p: (p[1]['created_at'], p[0]))
            for _, items in sorted(groups.items())]


def show_state(st, package, history, *, rejected=0, review_required=False):
    current = current_decision(package, history)
    related = latest_answer_decision(package, history)
    if related and (record_identity(related[0]) != target_identity(package)
                    or related[0]['status'] == 'BLOCKED_TECHNICAL'):
        current = None
    st.subheader('Review status: ' + (current[0]['status'] if current else
        status_label(package, history, review_required=review_required)
            if review_required or related else 'PENDING_REVIEW'))
    if review_required and (not related or related[0]['status'] == 'BLOCKED_TECHNICAL'):
        st.info('Semantic completeness: ANSWERED — accepted by the owner. '
                'Source grounding remains under review. Earlier Changes Requested and technical-block '
                'records are preserved in history; this is not a full approval or generation authorization.')
    if related and not current:
        st.info('A sealed decision intent already exists for this answer. It does not approve a new policy. '
                'Decision controls are locked; deliberate reassessment requires an explicit revision and reason.')
    if current:
        st.info('Review already completed. Decision controls are locked for this exact answer. '
                'Reassessment requires an explicit new review revision and documented reason.')
        st.caption('Current sealed local POC decision: ' + current[1])
        st.write('Owner notes: ' + current[0]['owner_notes'])
        if (package.get('assessment_draft_sha256')
                and current[0]['assessment_sha256'] != package['assessment_draft_sha256']):
            st.caption('The existing decision binds an earlier assessment of this exact answer. '
                       'It does not independently approve the newer assessment draft.')
    if rejected:
        st.warning('Unverified local review history blocks submission; original artifacts remain unchanged.')
    return related is not None or rejected > 0


def show_history(st, values, history, target, package=None):
    with st.expander('Review package and decision history'):
        st.dataframe([{'Package': path, 'Created': p['created_at'], 'Expires': p['expires_at'],
            'Trust baseline': p['trust']['path'], 'Policy': p['policy']['path'],
            'Assessment hash': p['assessment_draft_sha256']}
            for path, p, _, _ in values if target_identity(p) == target
                or (package and answer_identity(p) == answer_identity(package))], hide_index=True)
        st.dataframe([{'Decision': v['status'], 'Recorded': v['decided_at'],
            'Reviewer label': v['reviewer_label'], 'Receipt': path,
            'Revision': v.get('revision', 0), 'Revision reason': v.get('revision_reason', '')}
            for v, path in history if record_identity(v) == target
                or (package and answer_identity(v) == answer_identity(package))], hide_index=True)
