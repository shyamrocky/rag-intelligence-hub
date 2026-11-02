"""Read-only result inbox, keeping technical, declared and assessed findings separate."""
from .handoff import discover


def candidate_controls(st, root, entry, *, ready):
    """Existing explicit POC controls; unsigned preparation is internal to submit."""
    from tools.quality_dashboard.artifacts import ArtifactError, digest

    from . import local_poc, workflow
    from .handoff import synchronize
    from .review_state import show_state

    candidate = entry['assessment_candidate']
    target = {'question_id': entry['question_id'], 'bindings': {
        'question_sha256': entry['row']['question_sha256'],
        'response_sha256': digest(entry['row']['response']),
        'request_sha256': entry['row']['request_sha256'],
        'package_sha256': entry['row']['M8_package_sha256']}, 'policy': entry['policy']}
    history, rejected = local_poc.discover(root)
    ready = not show_state(st, target, history, rejected=rejected) and ready
    st.caption('Assessment draft method: ' + candidate['assessment']['method'] +
               ' — not authenticated independent acceptance.')
    st.dataframe(candidate['assessment']['claims'], hide_index=True)
    st.dataframe(candidate['assessment']['requirements'], hide_index=True)
    fingerprint = digest({'source': entry['source'], 'candidate': candidate})
    if st.session_state.get('poc_candidate_fingerprint') != fingerprint:
        st.session_state['poc_candidate_fingerprint'] = fingerprint
        st.session_state['poc_confirmed'] = False
        st.session_state.pop('poc_review_message', None)

    def submit(decision):
        confirmed = st.session_state.pop('poc_confirmed', False)
        label = st.session_state.get('poc_reviewer_label', '')
        try:
            local_poc.require_localhost()
            if confirmed is not True or not isinstance(label, str) or not label.strip():
                raise ArtifactError('EXPLICIT_CONFIRMATION_REQUIRED')
            current = next(e for e in discover(root)['entries'] if e['entry_id'] == entry['entry_id'])
            if digest({'source': current['source'], 'candidate': current['assessment_candidate']}) != fingerprint:
                raise ArtifactError('DISPLAYED_ASSESSMENT_CHANGED')
            rows = synchronize(root, source_manifest=entry['source']['manifest_path'])
            record = next(r for r in rows if r['entry_id'] == entry['entry_id'])
            path = record['package_manifest']
            p, _, ph = workflow.load_package(root, path, expected=record['package_manifest_sha256'])
            if p['assessment_draft_sha256'] != digest(candidate['assessment']):
                raise ArtifactError('PREPARED_ASSESSMENT_CHANGED')
            result = local_poc.decide(root, path, expected_sha=ph, reviewer_label=label,
                decision=decision, confirmed=confirmed, notes=st.session_state.get('poc_owner_notes', ''))
            value = local_poc.read_record(root, result)
            st.session_state['poc_review_message'] = value['status'] + ' · ' + result
        except (ArtifactError, ValueError, TypeError, KeyError, OSError, StopIteration):
            st.session_state['poc_review_message'] = 'Decision not accepted; check confirmation, source bindings and assessment freshness.'

    with st.form('poc_candidate_' + fingerprint, clear_on_submit=True):
        st.text_input('Reviewer label (supplied by owner)', key='poc_reviewer_label')
        st.text_area('Owner notes (optional)', key='poc_owner_notes')
        st.checkbox('I reviewed this question, answer and findings and explicitly confirm my selected decision.', key='poc_confirmed')
        for label, decision in [('Approve', 'APPROVE'), ('Reject', 'REJECT'), ('Request Changes', 'REQUEST_CHANGES')]:
            st.form_submit_button(label, disabled=not ready, on_click=submit, args=(decision,))
    if st.session_state.get('poc_review_message'):
        st.info(st.session_state['poc_review_message'])


def inbox(st, root, prepared, *, selected_entry=None):
    """Return selected existing package, or False for a visible pending result.

    None means no native results: preserve the historical prepared-package selector.
    No file write, package preparation, M8 operation or provider access occurs here.
    """
    data = discover(root, prepared=prepared)
    if not data['entries']:
        return None
    entries = data['entries']
    from tools.quality_dashboard.artifacts import digest

    from . import local_poc, preparation
    from .review_state import recorded_review_required, status_label
    history, _ = local_poc.discover(root)
    dispositions = {}
    for i, e in enumerate(entries):
        receipts, rejected_receipts = preparation.discover(root, e)
        dispositions[i] = bool(receipts and not rejected_receipts
            and recorded_review_required(root, receipts[-1]))
    def label(i):
        e = entries[i]
        target = {'question_id': e['question_id'], 'policy': e['policy'],
            'bindings': {'question_sha256': e['row']['question_sha256'],
                'response_sha256': digest(e['row']['response']),
                'request_sha256': e['row']['request_sha256'], 'package_sha256': e['row']['M8_package_sha256']}}
        return e['question_id'] + ' — ' + status_label(target, history, review_required=dispositions[i])
    if selected_entry is None:
        index = st.selectbox('Completed generation for Human Review', range(len(entries)),
            index=len(entries) - 1, key='handoff_entry', format_func=label)
        entry = entries[index]
    else:
        entry = next(e for e in entries if e['entry_id'] == selected_entry['entry_id'])
    row, response = entry['row'], entry['row']['response']
    if st.session_state.get('handoff_displayed_id') != entry['entry_id']:
        st.session_state['handoff_displayed_id'] = entry['entry_id']
        st.session_state['poc_confirmed'] = False
        st.session_state.pop('poc_review_message', None)
    st.subheader(entry['question_id'] + ' — review handoff')
    st.write(entry['question'] or 'UNAVAILABLE — original question binding is missing.')
    from tools.answer_quality.abstention import render_response
    render_response(st, response)
    st.caption('Native generation status: ' + response['status'] + ' · Native validation: '
               + row.get('post_validation', {}).get('overall_status', 'UNAVAILABLE'))
    if entry['coverage'] and entry['coverage']['required']:
        missing = [g['group_id'] for g in entry['coverage']['groups'] if not g['included']]
        if missing:
            st.warning('Missing approved evidence: ' + ', '.join(missing) +
                ' — retrieval coverage finding, not a semantic verdict.')
    with st.expander('Historical diagnostics, model declarations and source references'):
        st.write('Verified technical findings — sealed measurements, not semantic acceptance')
        post = row.get('post_validation', {})
        st.dataframe([{'Dimension': name, 'Recorded outcome': post.get(key, 'UNAVAILABLE')}
            for name, key in [('Source integrity', 'source_integrity'), ('Schema', 'structural_validation'),
                              ('Citations', 'citation_validity'), ('Qualifications', 'qualification_status')]],
            hide_index=True)
        fidelity = post.get('quotation_fidelity', [])
        st.dataframe([{'Claim': q['claim_index'] + 1, 'Quote': q['quote_index'] + 1,
            'Fidelity': q['outcome'], 'Method': q.get('method'), 'Unit': q['unit_id']}
            for q in fidelity], hide_index=True)
        if post.get('diagnoses'):
            st.warning('Native findings: ' + ', '.join(
                item if isinstance(item, str) else item.get('category', item.get('status', 'HISTORICAL_FINDING'))
                for item in post['diagnoses']))
        st.caption('A fidelity failure is preserved as reported; it does not independently establish a '
                   'semantic contradiction. A valid citation does not establish semantic support.')
        if entry['coverage']:
            c = entry['coverage']
            st.write('Offline benchmark evidence availability — separate from answer quality')
            st.dataframe([{'Approved group': g['group_id'], 'Direct witness discovered': g['direct_witness_discovered'],
                'Supporting parent located': g['parent_located'], 'Delivered': g['included']}
                for g in c['groups']], hide_index=True)
            st.caption('Known-positive groups are not exhaustive relevance judgments. Missing approved '
                       'evidence does not by itself prove this answer semantically wrong; completeness still needs review.')
            if not c['required']:
                st.caption('No positive evidence-group denominator — unsupported control, not a 0/0 pass.')
        st.write('Model-declared assertions — not independently verified judgments')
        st.dataframe([{'Claim': i + 1, 'Claim text': c['claim_text'],
            'Cited Units': ', '.join(c['evidence_unit_ids'])} for i, c in enumerate(response['claims'])], hide_index=True)
        with st.expander('Supporting quotations and exact cited Unit IDs'):
            for i, c in enumerate(response['claims']):
                for quote in c['supporting_quotes']:
                    st.caption(f'Claim {i + 1} · ' + quote['evidence_unit_id'])
                    st.text(quote['quote'])
        st.write('Requested aspects — model-reported coverage, pending independent requirements review')
        st.dataframe(response['requirement_coverage'], hide_index=True)
        st.write('Model-reported missing information: ' + '; '.join(response['missing_information']))
        st.write('Model-reported qualifications: ' + '; '.join(response['relevant_qualifications']))
        st.write('Model-reported conflicts')
        st.dataframe(response['conflicts_detected'], hide_index=True)
        st.caption('Empty qualification/conflict lists are declarations, not proof of compliance or absence.')
        st.write('Independent semantic judgments')
        st.info('No new human acceptance is inferred by this handoff. Prepared assessments remain drafts '
                'until the owner explicitly confirms the exact record using the existing workflow.')
        from tools.answer_quality.reporting import render as quality_findings
        with st.expander('Existing answer-quality assessments and review provenance'):
            from tools.quality_dashboard.artifacts import ArtifactError
            try:
                quality_findings(st, root, row)
            except (ArtifactError, ValueError, KeyError, TypeError, OSError):
                st.info('UNAVAILABLE — incomplete or unverified extended quality assessment. '
                        'The original native result remains reviewable; no semantic judgment is inferred.')
    if entry['timing']:
        timing = entry['timing']
        st.write(f'Execution elapsed: {timing["end_to_end_ms"] / 1000:.3f} seconds · {timing["mode"]}')
        with st.expander('Stage-level execution timings'):
            st.dataframe([{'Stage': s['stage'], 'Status': s['status'], 'Exclusive ms': s['duration_ms']}
                for s in timing['stages']], hide_index=True)
    with st.expander('Review provenance and technical details'):
        st.json({'source': entry['source'], 'request_sha256': row['request_sha256'],
            'M8_package_sha256': row['M8_package_sha256'], 'entry_id': entry['entry_id'],
            'evidence_group_measurement': entry['coverage'], 'native_validation': post,
            'missing_assessments': entry['missing_assessments'],
            'invalid_assessment_inputs': entry['rejected_assessment_inputs']})
    if data['rejected']:
        st.warning('Unverified generation sources excluded: ' + str(len(data['rejected'])))
    from . import preparation
    receipts, bad_preparations = preparation.discover(root, entry)
    if bad_preparations:
        st.warning('Unverified assessment preparation records excluded; preparation must be checked before submission.')
    if receipts and not bad_preparations:
        from .assessment_ui import render
        render(st, root, receipts[-1])
        return False
    incomplete_preparation = bool(entry['prepared'] and any(
        name.endswith('/MATERIALS.json') for name in entry['prepared'][1]['supporting_artifacts']))
    if entry['prepared'] and not incomplete_preparation and not bad_preparations:
        return entry['prepared']
    if entry['assessment_candidate'] and not incomplete_preparation and not bad_preparations:
        st.info('A source-bound assessment is available. The confirmed decision submission will '
                'automatically prepare its unsigned package; refresh remains read-only.')
        return entry

    from . import local_poc
    from .review_state import show_state
    history, rejected = local_poc.discover(root)
    show_state(st, {'question_id': entry['question_id'], 'policy': entry['policy'], 'bindings': {
        'question_sha256': row['question_sha256'], 'response_sha256': digest(response),
        'package_sha256': row['M8_package_sha256'], 'request_sha256': row['request_sha256']}},
        history, rejected=rejected)
    st.warning('Reviewable pending entry — required assessments are missing: '
               + ', '.join(entry['missing_assessments']))
    st.info('Assessment status: ASSESSMENT_UNAVAILABLE — source-backed review materials have not been prepared. '
            'Use the bounded local preparation action below; no provider call or approval occurs.')
    failed = preparation.failures(root, entry)
    if failed:
        st.error('Latest preparation failure: ' + failed[-1]['reason'] + ' · ' + failed[-1]['manifest'])
    if incomplete_preparation:
        st.warning('UNSEALED_ASSESSMENT_PREPARATION — the interrupted preparation must finish before decisions.')
    def prepare():
        try:
            local_poc.require_localhost()
            results = preparation.run(root, question_ids=[entry['question_id']])
            if any(r['status'] == 'ASSESSMENT_UNAVAILABLE' for r in results):
                st.session_state['preparation_error'] = 'ASSESSMENT_UNAVAILABLE — inspect the exact failure receipt below.'
            else:
                st.session_state.pop('preparation_error', None)
        except (ArtifactError, ValueError, TypeError, KeyError, OSError):
            st.session_state['preparation_error'] = 'Local preparation failed; inspect the sealed failure receipt and source bindings.'
    st.button('Prepare evidence & review materials', key='prepare-' + entry['entry_id'], on_click=prepare)
    if st.session_state.get('preparation_error'):
        st.warning(st.session_state['preparation_error'])
    for label in ['Approve', 'Reject', 'Request Changes']:
        st.button(label, disabled=True, key='pending-' + entry['entry_id'] + '-' + label)
    st.caption('No assessment or approval is fabricated. Owner controls become available when a complete '
               'source-bound assessment exists; no manual review-package preparation is required.')
    return False
