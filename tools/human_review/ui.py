"""Explicit authenticated review controls; all other dashboard actions stay read-only."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, read_json, safe_path

from .identity import default_store, registry
from .workflow import PACKAGE_BASE, decide, load_package, target_identity, verify_decision


def packages(root):
    values, rejected = [], 0
    for file in sorted((Path(root) / PACKAGE_BASE).glob('*/MANIFEST.json')):
        try:
            path = file.relative_to(root).as_posix()
            p, row, h = load_package(root, path)
            values.append((path, p, row, h))
        except (ArtifactError, KeyError, TypeError, OSError):
            rejected += 1
    return values, rejected


def render(st, root, *, credential_store=None):
    store = credential_store or default_store()
    st.subheader('Human Review')
    st.caption('Local signed review under ADR D052. Approval is separate from generation permission. '
               'Only explicit confirmed submissions run fresh M8 validation; browsing never does.')
    values, rejected = packages(root)
    if rejected:
        st.warning(f'{rejected} stale or unverified review packages excluded.')
    if not values:
        st.info('No unsigned review package available. Prepare one with the documented local CLI.')
        return
    selected = st.selectbox('Human review package', range(len(values)),
        format_func=lambda i: values[i][1]['question_id'] + ' · ' + values[i][1]['review_id'],
        key='human_review_package')
    path, p, row, ph = values[selected]
    st.write(p['question'])
    from tools.answer_quality.abstention import render_response
    render_response(st, row['response'])
    st.caption('Generated status: ' + row['response']['status'] + ' · Historical verdict: '
               + row.get('post_validation', {}).get('overall_status', 'UNAVAILABLE'))
    st.write('Claim grounding and citations — proposed findings for confirmation')
    st.dataframe([{'Claim': row['response']['claims'][c['claim_index']]['claim_text'],
        'Grounding': c['outcome'], 'Rationale': c['rationale'],
        'Cited Units': ', '.join(row['response']['claims'][c['claim_index']]['evidence_unit_ids']),
        'Quotation coverage gap': c.get('quotation_coverage_gap')} for c in p['assessment_draft']['claims']],
        hide_index=True)
    st.write('Completeness')
    st.dataframe([{'Requirement': r['requirement'], 'Outcome': r['outcome'], 'Rationale': r['rationale']}
        for r in p['assessment_draft']['requirements']], hide_index=True)
    for name in p['supporting_artifacts']:
        if name.endswith('/ADDITIONAL_ASSERTIONS.json'):
            inventory = read_json(safe_path(root, name))
            st.write('Additional factual assertions included in the review')
            st.dataframe([{'Assertion': a['assertion'], 'Outcome': a['outcome'], 'Rationale': a['rationale']}
                for a in inventory['material_assertions']], hide_index=True)
    st.write('Material qualifications: ' + p['assessment_draft']['qualifications']['rationale'])
    st.write('Conflicts: ' + p['assessment_draft']['conflicts']['rationale'])
    st.write('Generated qualifications: ' + '; '.join(row['response']['relevant_qualifications']))
    st.caption('Q04 recorded substantive decisions do not need another semantic vote. '
               'Confirmation accepts this exact prepared record, not any other answer.')
    ready = False
    try:
        state = registry(store)
        ready = not state['revoked']
        st.caption('Enrolled reviewer: ' + state['display_name'] + ' (' + state['reviewer_id'] + ')'
                   + (' — REVOKED' if state['revoked'] else ' — passphrase authentication required'))
    except (ArtifactError, KeyError, OSError, TypeError):
        st.warning('NOT_REGISTERED — the owner must run one-time local CLI enrollment. '
                   'No real owner key or identity has been created automatically.')
    for result in sorted((Path(root) / 'data/evals/answer-quality').glob('human-review-*/MANIFEST.json')):
        try:
            body, evaluation = verify_decision(root, store, result.relative_to(root).as_posix())
            if body['target_sha256'] == target_identity(p):
                st.info('Current authenticated decision: ' + body['outcome'] + ' · ' + evaluation['overall_status'])
                ready = False
        except (ArtifactError, KeyError, OSError, TypeError):
            st.caption('Unverified/revoked signed review excluded; independent acceptance remains pending.')
    st.code(ph, language=None)
    st.caption('Confirmation format: APPROVE / REJECT / REQUEST_CHANGES, then question ID, then the full hash above. '
               'Example prefix: APPROVE ' + p['question_id'] + ' …')

    def submit(outcome):
        secret = st.session_state.pop('human_review_secret', '')
        confirmed = st.session_state.pop('human_review_confirmed', False)
        phrase = st.session_state.pop('human_review_confirmation', '')
        try:
            if not confirmed:
                raise ArtifactError('EXPLICIT_RECORD_CONFIRMATION_REQUIRED')
            receipt = decide(root, store, path, expected_sha=ph,
                reviewer_id=st.session_state.get('human_review_reviewer', ''), passphrase=secret,
                decision=outcome, confirmation=phrase, note=st.session_state.get('human_review_note', ''))
            st.session_state['human_review_message'] = 'Signed decision published: ' + receipt
        except (ArtifactError, OSError, TypeError, KeyError):
            st.session_state['human_review_message'] = ('Decision not accepted. Check credentials, exact confirmation, '
                'freshness and source integrity. No historical result was rewritten; use CLI verify for details.')
        finally:
            secret = None  # No credential retained in the session or receipt.

    with st.form('human_review_decision', clear_on_submit=True):
        st.text_input('Registered reviewer ID', key='human_review_reviewer')
        st.text_input('Signing-key passphrase', type='password', key='human_review_secret')
        st.text_input('Exact hash-bound confirmation', key='human_review_confirmation')
        st.text_input('Review note (optional)', key='human_review_note')
        st.checkbox('I confirm this exact review record and the selected decision.', key='human_review_confirmed')
        for label, outcome in [('Approve', 'APPROVE'), ('Reject', 'REJECT'), ('Request Changes', 'REQUEST_CHANGES')]:
            st.form_submit_button(label, disabled=not ready, on_click=submit, args=(outcome,))
    if 'human_review_message' in st.session_state:
        st.info(st.session_state['human_review_message'])
    with st.expander('Technical Details — unsigned review bindings'):
        st.json({'package': path, 'manifest_sha256': ph, 'bindings': p['bindings'],
                 'policy': p['policy'], 'trust': p['trust'], 'status': p['status']})
        st.caption('Receipt is review-only, never source authorization or paid-execution permission.')
