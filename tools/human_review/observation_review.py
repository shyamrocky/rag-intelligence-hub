"""Local owner triage of exact preserved output, never formal answer approval."""
import fcntl
import json
import os
from pathlib import Path

from tools.generation.observation import observe
from tools.preflight_suite.artifacts import now, save
from tools.quality_dashboard.artifacts import ArtifactError, Store, digest, sha

BASE = 'data/evals/human-review/observations'
POLICY = 'response-observation-owner-triage-1.0'


def identity(attempt):
    row = attempt.get('row', {})
    return {'question_id': attempt['question_id'],
        'result_sha256': attempt['response_file_sha256'],
        'request_sha256': attempt['audit']['request_sha256'],
        'M8_package_sha256': attempt['audit']['M8_package_sha256'],
        'raw_sha256': row.get('audit', {}).get('raw_response_capture', {}).get('artifact', {}).get('sha256')
            if row.get('audit', {}).get('raw_response_capture', {}).get('artifact') else None,
        'policy': POLICY, 'validation_policy': attempt.get('review_policy')}


def load_output(root, attempt):
    """Selected explicit local read. Never return unverified private text."""
    from .local_poc import require_localhost
    from .response_diagnostics import capture_reference
    require_localhost()
    if attempt.get('response') is not None:
        return {'state': 'HISTORICAL_ACCEPTED_OBJECT', 'candidate': attempt['response'], 'text_parts': [], 'refusals': []}
    entry = {'run': attempt['run'], 'row': attempt['row']}
    _receipt, path = capture_reference(root, entry)
    if path is None:
        return {'state': 'RAW_RESPONSE_UNAVAILABLE', 'candidate': None, 'text_parts': [], 'refusals': []}
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeError):
        return {'state': 'INVALID_PROVIDER_JSON', 'candidate': None,
                'text_parts': [path.read_bytes().decode('utf-8', errors='replace')], 'refusals': []}
    return observe(value)


def validate_target(root, attempt):
    source = attempt.get('source')
    if not source:
        raise ArtifactError('BOUND_NATIVE_SOURCE_REQUIRED')
    store = Store(root)
    manifest = store.manifest(source['manifest_path'], expected=source['manifest_sha256'])
    base = source['manifest_path'].rsplit('/', 1)[0] + '/'
    relative = source['result_path'].removeprefix(base)
    if (not source['result_path'].startswith(base) or manifest.get('mode') != 'live'
            or manifest['files'].get(relative) != source['result_sha256']):
        raise ArtifactError('UNBOUND_OBSERVATION_SOURCE')
    row = store.json(source['result_path'])
    if row != attempt['row'] or row['question_id'] != attempt['question_id']:
        raise ArtifactError('CHANGED_OBSERVATION_TARGET')
    return row


def read_decision(root, attempt):
    validate_target(root, attempt)
    target = identity(attempt)
    name = BASE + '/' + digest(target) + '/MANIFEST.json'
    if not (Path(root) / name).exists():
        if (Path(root) / name).parent.exists():
            raise ArtifactError('INTERRUPTED_REVIEW_REQUIRES_RECOVERY')
        for prior in (Path(root) / BASE).glob('*/MANIFEST.json'):
            store = Store(root); store.manifest(prior.relative_to(root).as_posix(), schema=POLICY)
            value = store.json(prior.parent.relative_to(root).as_posix() + '/DECISION.json')
            if ({k: v for k, v in value['bindings'].items() if k != 'validation_policy'} ==
                    {k: v for k, v in target.items() if k != 'validation_policy'}):
                return value | {'status': 'PREVIOUS_POLICY_REVIEW_LOCKED', 'current_policy_accepted': False}
        return None
    store = Store(root); store.manifest(name, schema=POLICY)
    value = store.json(name.rsplit('/', 1)[0] + '/DECISION.json')
    if (value['bindings'] != target or value['formal_validation'] is not False
            or value['decision'] not in {'ANSWERED', 'PARTIAL', 'UNANSWERED', 'UNASSESSABLE'}
            or not value['confirmed'] or not value['reviewer_label'].strip()):
        raise ArtifactError('INVALID_OBSERVATION_REVIEW')
    return value


def decide(root, attempt, *, decision, label, notes, confirmed):
    from .local_poc import require_localhost
    require_localhost()
    from .handoff import review_trust
    from .workflow import trust_check
    trust_check(root, review_trust())
    if (confirmed is not True or not isinstance(label, str) or not label.strip()
            or decision not in {'ANSWERED', 'PARTIAL', 'UNANSWERED', 'UNASSESSABLE'}):
        raise ArtifactError('EXPLICIT_OWNER_TRIAGE_REQUIRED')
    # Re-read exact sealed source, not caller-supplied response/hash text.
    from tools.answer_quality.current import policy_reference
    if attempt.get('review_policy') != policy_reference(root):
        raise ArtifactError('STALE_REVIEW_POLICY')
    source = attempt.get('source')
    if not source:
        raise ArtifactError('BOUND_SOURCE_REQUIRED')
    validate_target(root, attempt)
    load_output(root, attempt)  # Reverify raw hash when available; missing historical data remains explicit.
    from tools.answer_quality.current import policy_reference
    target = identity(attempt) | {'validation_policy': policy_reference(root)}
    folder = Path(root) / BASE / digest(identity(attempt))
    from tools.generation.response_capture import _directory
    _directory(Path(root), BASE)
    fd = os.open(Path(root) / BASE / 'DECISIONS.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if folder.exists() or read_decision(root, attempt):
            raise ArtifactError('REVIEW_ALREADY_COMPLETED_NO_AUTOMATIC_REVISION')
        value = {'schema': POLICY, 'bindings': identity(attempt), 'validation_policy': target['validation_policy'],
            'decision': decision, 'reviewer_label': label.strip(), 'notes': notes, 'confirmed': True,
            'created_at': now(), 'formal_validation': False, 'source': source,
            'status': 'OWNER_TRIAGE_RECORDED', 'technical_findings_overridden': False}
        save(folder / 'DECISION.json', value)
        save(folder / 'MANIFEST.json', {'schema': POLICY,
            'files': {'DECISION.json': sha(folder / 'DECISION.json')}})
        return value
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)


def render(st, root, attempt):
    try:
        output = load_output(root, attempt)
    except (ArtifactError, ValueError, KeyError, OSError, TypeError):
        st.error('Protected response unavailable or unverified. No output can be certified.'); return
    st.warning('Returned output is untrusted experimental data. Contract failure is retained; semantic quality is unassessed.')
    candidate = output.get('candidate')
    if isinstance(candidate, dict):
        answer = candidate.get('answer')
        if isinstance(answer, str) and answer:
            st.markdown(answer, unsafe_allow_html=False)
        reasons = candidate.get('missing_information')
        if candidate.get('status') == 'ABSTAINED':
            st.write('Unable to answer from available evidence')
        if isinstance(reasons, list):
            for reason in reasons:
                if isinstance(reason, str): st.write(reason)
        with st.expander('Model declarations and returned claims — unverified'):
            for name in ('status', 'claims', 'requirement_coverage', 'relevant_qualifications', 'conflicts_detected'):
                st.write(name); st.json(candidate.get(name))
    else:
        for text in output.get('text_parts', []) + output.get('refusals', []):
            st.text(text)
        st.info(output['state'])
    from tools.quality_dashboard.observation_backfill import find
    try:
        derived = find(root, attempt)
    except (ArtifactError, ValueError, KeyError, OSError):
        derived = None
        st.warning('Derived observation unverified; original record remains available.')
    if derived:
        with st.expander('Additional offline field checks — original verdict preserved'):
            st.json(derived['field_checks'])
    audit = attempt['audit']
    st.write('Contract findings (separate from factual correctness)')
    for issue in audit.get('response_diagnostics', []):
        st.warning(issue.get('code', 'OUTPUT_CONTRACT_FINDING') + ' · field ' + str(issue.get('path', [])))
    with st.expander('Technical Details — preserved response, usage and validation'):
        st.json({'audit': audit, 'validation': attempt.get('validation'), 'observation_state': output['state']})
        if st.checkbox('Show protected raw provider response', key='observation-raw-' + digest(identity(attempt))):
            from .response_diagnostics import capture_reference
            _, path = capture_reference(root, {'run': attempt['run'], 'row': attempt['row']})
            if path: st.code(path.read_bytes().decode('utf-8', errors='replace'), language='json')
            else: st.info('RAW RESPONSE UNAVAILABLE')
    try:
        previous = read_decision(root, attempt)
    except (ArtifactError, ValueError, KeyError, OSError):
        st.error('Review history unverified; decisions disabled.'); return
    if previous:
        st.info('Owner triage: ' + previous['decision'] + ' — locked. Technical findings remain unchanged.')
        if previous.get('status') == 'PREVIOUS_POLICY_REVIEW_LOCKED':
            st.warning('Earlier policy review is preserved; it does not accept this policy. Explicit reassessment is required.')
        return
    st.caption('This records an owner observation only. It cannot approve an invalid contract, fix citations or authorize generation.')
    with st.form('observation-triage-' + digest(identity(attempt)), clear_on_submit=True):
        label = st.text_input('Owner reviewer label')
        decision = st.selectbox('Owner assessment of returned answer', ['UNASSESSABLE', 'ANSWERED', 'PARTIAL', 'UNANSWERED'])
        notes = st.text_area('Owner triage notes')
        confirmed = st.checkbox('I explicitly confirm this assessment of this exact returned output.')
        if st.form_submit_button('Record owner triage'):
            try:
                decide(root, attempt, decision=decision, label=label, notes=notes, confirmed=confirmed)
                st.success('Owner triage recorded. Original validation is unchanged.'); st.rerun()
            except (ArtifactError, ValueError, TypeError, KeyError, OSError):
                st.error('Decision not recorded: confirmation, integrity or duplicate check failed.')
