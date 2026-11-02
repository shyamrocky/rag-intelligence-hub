"""Local evidence inspection and explicit owner judgments; no inference or auto-approval."""
import copy

from tools.quality_dashboard.artifacts import ArtifactError, read_json, safe_path

from . import local_poc, preparation
from .review_state import package_history, show_history, show_state, target_identity


def render(st, root, receipt):
    ppath, p, row, _ = receipt['prepared']
    materials = receipt['materials']
    st.subheader('Assessment status: ' + materials['status'])
    st.caption('Provisional findings are not human acceptance. Unassessed dimensions require your judgment. '
               'No LLM judge or external call is performed.')
    history, rejected = local_poc.discover(root)
    from .review_state import recorded_review_required
    locked = show_state(st, p, history, rejected=rejected,
        review_required=recorded_review_required(root, receipt))
    from .review_state import latest_answer_decision
    current = latest_answer_decision(p, history)
    revision_of, revision_reason = None, ''
    if current:
        with st.expander('Deliberate reassessment — explicit new revision', expanded=False):
            reason = st.text_area('Reason for reassessment', key='revision-reason-' + receipt['manifest_sha256'])
            initiate = st.checkbox('Initiate a separate review revision of this exact answer; do not transfer its previous approval.',
                key='revision-start-' + receipt['manifest_sha256'])
            if initiate and reason.strip() and not rejected:
                from tools.quality_dashboard.artifacts import sha
                revision_of = {'path': current[1], 'sha256': sha(root / current[1])}
                revision_reason = reason.strip()
                locked = False
                st.warning('New revision initiated explicitly. No decision exists until you confirm and submit below.')
    show_history(st, package_history(root), history, target_identity(p), package=p)
    local = True
    try:
        local_poc.require_localhost()
    except (ArtifactError, ValueError, TypeError):
        local = False
        st.warning('Evidence inspection and decisions require direct localhost access.')
    st.write('Fresh technical checks (source-bound preparation, not semantic proof)')
    checks = materials['fresh_technical_validation']
    st.dataframe([{'Dimension': name, 'Outcome': checks.get(name, 'UNAVAILABLE')}
        for name in ['source_integrity', 'structural_validation', 'citation_validity', 'overall_status']], hide_index=True)
    if not local_poc.technical_pass(checks):
        st.error('Approval blocked by technical validation. Review cannot override this failure; '
                 'the original validation verdict remains unchanged.')
    draft = p['assessment_draft']
    from collections import Counter
    st.write('Grounding (provisional): ' + ', '.join(f'{n} {kind}' for kind, n in Counter(c['outcome'] for c in draft['claims']).items()))
    st.write('Completeness (provisional): ' + ', '.join(f'{n} {kind}' for kind, n in Counter(r['outcome'] for r in draft['requirements']).items()))
    fidelity = checks.get('quotation_fidelity', [])
    st.write('Quotation fidelity: ' + ', '.join(f'{n} {kind}' for kind, n in Counter(q['outcome'] for q in fidelity).items()))
    st.write('Qualifications: ' + draft['qualifications']['rationale'])
    st.write('Conflicts: ' + draft['conflicts']['rationale'])
    for issue in draft['uncertainty']:
        st.warning('Outstanding judgment: ' + issue)
    if local:
        evidence = preparation.source_context(root, receipt)
        with st.expander('Inspect authentic supplied evidence and source-use metadata'):
            if not evidence['parents']:
                st.info('No citations: inspect the question, missing-information statement and supplied-package diagnostics. '
                        'Abstention does not require invented citations; its appropriateness still needs judgment.')
            selected_unit = st.selectbox('Supplied source Unit to inspect',
                [parent['unit_id'] for parent in evidence['parents']], key='inspect-unit-'+receipt['manifest_sha256'])
            for parent in evidence['parents']:
                if parent['unit_id'] != selected_unit:
                    continue
                st.write('Authorized Unit: ' + parent['unit_id'])
                for pointer, text in parent['source_fields'].items():
                    st.caption('Publisher source content · ' + pointer)
                    st.text(text)
                st.caption('QA/source-use metadata — application observations, not publisher claims')
                st.json({'consumer': parent['consumer_metadata'], 'obligations': parent['source_obligations']})
    additional = []
    for name in p['supporting_artifacts']:
        if name.endswith('/ADDITIONAL_ASSERTIONS.json'):
            additional.extend(read_json(safe_path(root, name))['material_assertions'])
    if st.session_state.get('assessment_displayed_hash') != receipt['manifest_sha256']:
        st.session_state['assessment_displayed_hash'] = receipt['manifest_sha256']
        st.session_state['assessment_confirmed'] = False
        st.session_state.pop('assessment_message', None)
    st.write('Owner judgments — edit provisional findings or assess unresolved dimensions')
    refs = materials['source_field_references']
    meta = materials['metadata_field_references']
    def passages(label, default, available, key):
        defaults = [i for i, r in enumerate(available) if any(
            r['unit_id'] == d['unit_id'] and r['pointer'] == d['pointer'] for d in default)]
        indices = st.multiselect(label, range(len(available)), default=defaults, key=key,
            format_func=lambda i: available[i]['unit_id'].split(':')[-1] + ' · ' + available[i]['pointer'])
        return [available[i] for i in indices]

    result = copy.deepcopy(draft)
    extras = []
    key = receipt['manifest_sha256']
    with st.form('owner_assessment_' + key, clear_on_submit=False):
        label = st.text_input('Reviewer label (supplied by owner)', key='assessment_reviewer')
        with st.expander('Advanced Review / Edit Findings', expanded=False):
            requirement_count = st.number_input('Number of question requirements to review', min_value=1, max_value=30,
                value=len(draft['requirements']), key='assessment_requirement_count_' + receipt['manifest_sha256'])
            extra_count = st.number_input('Additional assertions outside the model claim list', min_value=0, max_value=30,
                value=len(additional), key='assessment_extra_count_' + receipt['manifest_sha256'])

            for c in result['claims']:
                i = c['claim_index']
                choices = ['INDETERMINATE', 'SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'CONTRADICTED']
                c['outcome'] = st.selectbox(f'Claim {i+1} support', choices, index=choices.index(c['outcome']), key=f'{key}-c{i}-status')
                c['rationale'] = st.text_area(f'Claim {i+1} rationale', value=c['rationale'], key=f'{key}-c{i}-reason')
                allowed_refs = [r for r in refs if r['unit_id'] in row['response']['claims'][i]['evidence_unit_ids']]
                c['passages'] = passages(f'Claim {i+1} source fields examined', c['passages'], allowed_refs, f'{key}-c{i}-refs')
            requirements = []
            for i in range(int(requirement_count)):
                r = copy.deepcopy(draft['requirements'][i]) if i < len(draft['requirements']) else {
                    'requirement_id': f'OWNER-{i+1}', 'requirement': '', 'outcome': 'INDETERMINATE',
                    'rationale': '', 'claim_indices': [], 'passages': []}
                r['requirement'] = st.text_input(f'Requirement {i+1}', value=r['requirement'], key=f'{key}-r{i}-text')
                options = ['INDETERMINATE', 'COMPLETE', 'PARTIAL', 'INCOMPLETE']
                r['outcome'] = st.selectbox(f'Requirement {i+1} coverage', options, index=options.index(r['outcome']), key=f'{key}-r{i}-status')
                r['rationale'] = st.text_area(f'Requirement {i+1} rationale', value=r['rationale'], key=f'{key}-r{i}-reason')
                r['passages'] = passages(f'Requirement {i+1} supporting fields', r['passages'], refs, f'{key}-r{i}-refs')
                requirements.append(r)
            result['requirements'] = requirements
            for i in range(int(extra_count)):
                a = copy.deepcopy(additional[i]) if i < len(additional) else {
                    'assertion': '', 'outcome': 'INDETERMINATE', 'rationale': '', 'passages': []}
                a['assertion'] = st.text_area(f'Additional assertion {i+1}', value=a['assertion'], key=f'{key}-a{i}-text')
                options = ['INDETERMINATE', 'SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'CONTRADICTED']
                a['outcome'] = st.selectbox(f'Additional assertion {i+1} support', options, index=options.index(a['outcome']), key=f'{key}-a{i}-status')
                a['rationale'] = st.text_area(f'Additional assertion {i+1} rationale', value=a['rationale'], key=f'{key}-a{i}-reason')
                a['passages'] = passages(f'Additional assertion {i+1} source or QA metadata fields', a.get('passages', []), refs + meta, f'{key}-a{i}-refs')
                extras.append(a)
            for field, title in [('qualifications', 'Material qualifications'), ('conflicts', 'Material conflicts')]:
                options = ['INDETERMINATE', 'SATISFIED', 'MISSING']
                result[field]['outcome'] = st.selectbox(title, options, index=options.index(result[field]['outcome']), key=key+'-'+field)
                result[field]['rationale'] = st.text_area(title + ' rationale', value=result[field]['rationale'], key=key+'-'+field+'-reason')
            options = ['UNDETERMINED', 'APPROPRIATE', 'INAPPROPRIATE']
            appropriate = st.selectbox('Declared answer status appropriateness', options,
                index=0 if draft['response_status_appropriate'] is None else 1 if draft['response_status_appropriate'] else 2,
                key=key+'-appropriate')
            result['response_status_appropriate'] = None if appropriate == 'UNDETERMINED' else appropriate == 'APPROPRIATE'
        result['answer_claim_inventory_complete'] = st.checkbox('I checked all factual assertions, including those outside the claim list.', key=key+'-inventory')
        result['question_requirements_reviewed'] = st.checkbox('I checked every requested part of the original question.', key=key+'-requirements')
        unresolved = st.text_area('Unresolved issues (one per line; clear only after resolving them)', value='\n'.join(draft['uncertainty']), key=key+'-uncertainty')
        result['uncertainty'] = [s.strip() for s in unresolved.splitlines() if s.strip()]
        notes = st.text_area('Owner notes (optional)', key='assessment_notes')
        confirmed = st.checkbox('I explicitly confirm these exact owner judgments and my selected decision.', key='assessment_confirmed')
        action = None
        for button, decision in [('Approve', 'APPROVE'), ('Reject', 'REJECT'), ('Request Changes', 'REQUEST_CHANGES')]:
            if st.form_submit_button(button, disabled=locked or not local or (decision == 'APPROVE' and not local_poc.technical_pass(checks))):
                action = decision
    if action:
        try:
            path = preparation.owner_decide(root, receipt['manifest'], expected_sha=receipt['manifest_sha256'],
                reviewer_label=label, decision=action, confirmed=confirmed, assessment=result,
                additional_assertions=extras, notes=notes, revision_of=revision_of, revision_reason=revision_reason)
            st.session_state['assessment_message'] = local_poc.read_record(root, path)['status'] + ' · ' + path
            st.rerun()
        except (ArtifactError, ValueError, TypeError, KeyError, OSError):
            st.error('Decision not accepted. Confirm your label and judgments; approval requires resolved support, '
                     'completeness and disclosures plus fresh technical validation. No original result was changed.')
    if st.session_state.get('assessment_message'):
        st.info(st.session_state['assessment_message'])
    with st.expander('Technical Details — assessment preparation'):
        st.json({'preparation': receipt['manifest'], 'bindings': p['bindings'], 'package': ppath,
            'assessment_method': materials['assessment_method'], 'authenticated': False,
            'formal_validation_status': 'REVIEW_REQUIRED_UNLESS_SEPARATELY_AUTHENTICATED'})
