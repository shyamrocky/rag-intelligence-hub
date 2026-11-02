"""Read-only, source-free quality view. Never imports runner/evidence/provider services."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store, digest


def discover(root, *, question_id, response_sha256, request_sha256):
    found, rejected = [], []
    for path in sorted((Path(root) / 'data/evals/answer-quality').glob('*/MANIFEST.json')):
        try:
            store = Store(root)
            manifest = store.manifest(path.relative_to(root).as_posix(), schema='answer-quality-evaluation-2.0')
            base = path.parent.relative_to(root).as_posix()
            assessment = store.json(base + '/ASSESSMENT.json')
            if (manifest.get('authenticated_review') or 'APPROVAL.json' in manifest['files']
                    or assessment.get('overall_status') == 'VALIDATED' or assessment.get('fully_validated')
                    or assessment.get('semantic_status') == 'HUMAN_REVIEWED'
                    or assessment.get('independent_human_acceptance')):
                # A self-consistent JSON manifest is not reviewer authentication.
                from tools.human_review.identity import default_store
                from tools.human_review.workflow import verify_decision
                _, authenticated = verify_decision(root, default_store(), path.relative_to(root).as_posix())
                if authenticated != assessment:
                    raise ArtifactError('AUTHENTICATED_REVIEW_ASSESSMENT_MISMATCH')
            source = manifest['response_source']
            native = store.manifest(source['manifest_path'], expected=source['manifest_sha256'])
            store.bind(source['result_path'], source['result_sha256'])
            result = store.json(source['result_path'])
            native_base = source['manifest_path'].rsplit('/', 1)[0] + '/'
            relative = source['result_path'].removeprefix(native_base)
            if (not source['result_path'].startswith(native_base)
                    or native['files'].get(relative) != source['result_sha256']
                    or result['question_id'] != manifest['question_id']
                    or digest(result['response']) != assessment['response_sha256']
                    or result['request_sha256'] != assessment['request_sha256']):
                raise ArtifactError('QUALITY_RESPONSE_SOURCE_MISMATCH')
            if (assessment['schema'] not in {'post-generation-validation-2.0', 'post-generation-validation-2.1'}
                    or manifest['question_id'] != assessment['question_id']
                    or manifest['response_sha256'] != assessment['response_sha256']
                    or manifest['request_sha256'] != assessment['request_sha256']):
                raise ArtifactError('QUALITY_IDENTITY_MISMATCH')
            # Assessments never migrate across questions, prompt versions or answers.
            if (manifest['question_id'] == question_id and assessment['response_sha256'] == response_sha256
                    and assessment['request_sha256'] == request_sha256):
                found.append((manifest.get('created_at', ''), assessment, path.relative_to(root).as_posix()))
        except (ArtifactError, KeyError, ValueError, OSError, TypeError):
            rejected.append(path.parent.name)
    return [(assessment, path) for _, assessment, path in sorted(found, key=lambda item: (item[0], item[2]))], rejected


def render(st, root, row):
    if not row.get('response'):
        return
    direct = row.get('post_validation', {})
    entries, rejected = discover(root, question_id=row['question_id'],
        response_sha256=digest(row['response']), request_sha256=row['request_sha256'])
    if direct.get('schema') in {'post-generation-validation-2.0', 'post-generation-validation-2.1'}:
        entries.insert(0, (direct, 'Original sealed runner result'))
    if not entries:
        return
    st.subheader('Answer quality — validation v2')
    st.caption('Separate successor assessment; historical verdicts remain unchanged. '
               'Quotation alignment does not certify claim support.')
    value, reference = entries[-1]
    st.write('Outcome: ' + value['overall_status'])
    st.dataframe([{'Dimension': name, 'Outcome': outcome} for name, outcome in [
        ('Response structure', value['structural_validation']),
        ('Citation and source integrity', value['citation_validity']),
        ('Semantic assessment', value['semantic_status']),
        ('Requirement completeness', value.get('completeness', {}).get('outcome', 'INDETERMINATE')),
        ('Material qualifications', value.get('material_qualifications', 'INDETERMINATE')),
        ('Conflicts', value.get('conflicts', 'INDETERMINATE'))]], hide_index=True)
    st.write('Claims and evidence support')
    st.dataframe([{'Claim': c['claim_index'] + 1, 'Support': c['outcome'], 'Rationale': c['rationale'],
                   'Quotation coverage gap': c.get('quotation_coverage_gap')}
                  for c in value.get('claim_grounding', [])], hide_index=True)
    st.write('Question requirements')
    st.dataframe([{'Requirement': r['requirement'], 'Coverage': r['outcome'], 'Rationale': r['rationale']}
                  for r in value.get('completeness', {}).get('requirements', [])], hide_index=True)
    st.write('Review needed: ' + '; '.join(value.get('review_reasons', [])))
    with st.expander('Technical Details — fidelity, source pointers and assessment provenance'):
        st.caption(reference)
        st.json(value)
    if rejected:
        st.caption('Unverified quality records excluded: ' + str(len(rejected)))
