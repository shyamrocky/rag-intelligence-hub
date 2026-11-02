"""Lightweight default review mode; original signed controls remain unchanged."""
from tools.quality_dashboard.artifacts import ArtifactError, read_json, safe_path

from . import local_poc
from .review_state import group_packages, package_history, show_history, show_state, target_identity
from .ui import packages


def render(st, root, *, selection=None):
    mode = st.radio('Human review mode', ['LOCAL_POC_REVIEW', 'SIGNED_HUMAN_REVIEW (advanced)'],
                    key='owner_review_mode', horizontal=True)
    if mode != local_poc.MODE:
        from .ui import render as signed_review
        signed_review(st, root)
        return
    st.subheader('Human Review — LOCAL_POC_REVIEW')
    st.caption('Local owner attestation for the Week 2 POC. No registration, signing key or passphrase. '
               'OWNER_APPROVED_POC is separate from authenticated human validation and generation permission.')
    ready = True
    try:
        local_poc.require_localhost()
    except (ArtifactError, ValueError, TypeError):
        ready = False
        st.warning('LOCAL_POC_REVIEW requires direct localhost access and server.address=127.0.0.1 '
                   '(or ::1/localhost). Restart Streamlit with the documented localhost command.')
    from .unified_ui import select
    if selection is None:
        selection = select(st, root)
    if selection and not selection['normal_entry']:
        return
    values, rejected = packages(root)
    from .handoff_ui import candidate_controls, inbox
    selected = inbox(st, root, values, selected_entry=selection['normal_entry'] if selection else None)
    from_inbox = selected is not None
    if selected is False:
        return
    if isinstance(selected, dict):
        candidate_controls(st, root, selected, ready=ready)
        return
    if rejected:
        st.caption(f'{rejected} expired or unverified review packages excluded.')
    if not values and selected is None:
        st.info('No compatible prepared review available. No approval has been created.')
        return
    if selected is None:
        groups = group_packages(values)
        index = st.selectbox('Local POC review package', range(len(groups)), index=len(groups) - 1,
            format_func=lambda i: groups[i][-1][1]['question_id'] + ' · ' + target_identity(groups[i][-1][1])[:12],
            key='poc_package')
        selected = groups[index][-1]
    path, p, row, fingerprint = selected
    if st.session_state.get('poc_displayed_hash') != fingerprint:
        st.session_state['poc_displayed_hash'] = fingerprint
        st.session_state['poc_confirmed'] = False
        st.session_state.pop('poc_review_message', None)
    if not from_inbox:
        st.write(p['question'])
        from tools.answer_quality.abstention import render_response
        render_response(st, row['response'])
    st.caption('Generated status: ' + row['response']['status'] + ' · Original verdict: '
               + row.get('post_validation', {}).get('overall_status', 'UNAVAILABLE'))
    from collections import Counter
    st.write('Grounding (prepared, not independent acceptance): ' + ', '.join(f'{n} {kind}' for kind, n in Counter(c['outcome'] for c in p['assessment_draft']['claims']).items()))
    st.write('Completeness (prepared): ' + ', '.join(f'{n} {kind}' for kind, n in Counter(r['outcome'] for r in p['assessment_draft']['requirements']).items()))
    st.write('Material qualifications: ' + p['assessment_draft']['qualifications']['outcome'])
    st.write('Material conflicts: ' + p['assessment_draft']['conflicts']['outcome'])
    for issue in p['assessment_draft']['uncertainty']:
        st.warning('Outstanding issue: ' + issue)
    with st.expander('Advanced Review / Edit Findings', expanded=False):
        st.write('Claim grounding and citations — prepared findings for owner review')
        st.dataframe([{'Claim': row['response']['claims'][c['claim_index']]['claim_text'],
            'Grounding': c['outcome'], 'Cited Units': ', '.join(row['response']['claims'][c['claim_index']]['evidence_unit_ids']),
            'Rationale': c['rationale'], 'Quotation coverage gap': c.get('quotation_coverage_gap')}
            for c in p['assessment_draft']['claims']], hide_index=True)
        st.write('Completeness')
        st.dataframe([{'Requirement': r['requirement'], 'Coverage': r['outcome'], 'Rationale': r['rationale']}
            for r in p['assessment_draft']['requirements']], hide_index=True)
        for name in p['supporting_artifacts']:
            if name.endswith('/ADDITIONAL_ASSERTIONS.json'):
                inventory = read_json(safe_path(root, name))
                st.write('Additional factual assertions')
                st.dataframe([{'Assertion': a['assertion'], 'Grounding': a['outcome'], 'Rationale': a['rationale']}
                    for a in inventory['material_assertions']], hide_index=True)
        st.write('Qualifications: ' + p['assessment_draft']['qualifications']['rationale'])
        st.write('Generated qualifications: ' + '; '.join(row['response']['relevant_qualifications']))
        st.write('Conflicts: ' + p['assessment_draft']['conflicts']['rationale'])
    history, unverified = local_poc.discover(root, question_id=p['question_id'])
    ready = not show_state(st, p, history, rejected=unverified) and ready
    show_history(st, package_history(root), history, target_identity(p))

    def submit(decision):
        confirmed = st.session_state.pop('poc_confirmed', False)
        try:
            result = local_poc.decide(root, path, expected_sha=fingerprint,
                reviewer_label=st.session_state.get('poc_reviewer_label', ''), decision=decision,
                confirmed=confirmed, notes=st.session_state.get('poc_owner_notes', ''))
            value = local_poc.read_record(root, result)
            st.session_state['poc_review_message'] = value['status'] + ' · ' + result
        except (ArtifactError, ValueError, OSError, TypeError, KeyError):
            st.session_state['poc_review_message'] = ('Decision not accepted. Supply your reviewer label and explicit '
                'confirmation; localhost, freshness, duplicate and technical checks must pass.')

    # Binding the form identity to the package prevents confirmation carrying across answers.
    with st.form('poc_decision_' + fingerprint, clear_on_submit=True):
        st.text_input('Reviewer label (supplied by owner)', key='poc_reviewer_label')
        st.text_area('Owner notes (optional)', key='poc_owner_notes')
        st.checkbox('I reviewed this question, answer and findings and explicitly confirm my selected decision.',
                    key='poc_confirmed')
        for label, decision in [('Approve', 'APPROVE'), ('Reject', 'REJECT'), ('Request Changes', 'REQUEST_CHANGES')]:
            st.form_submit_button(label, disabled=not ready, on_click=submit, args=(decision,))
    if st.session_state.get('poc_review_message'):
        st.info(st.session_state['poc_review_message'])
    with st.expander('Technical Details — exact POC review bindings'):
        st.json({'mode': local_poc.MODE, 'package': path, 'manifest_sha256': fingerprint,
                 'bindings': p['bindings'], 'assessment_sha256': p['assessment_draft_sha256'],
                 'policy': p['policy'], 'authenticated': False, 'fully_validated': False})
        st.caption('The server binds this submission to the exact displayed package. No manual hash entry is needed.')
