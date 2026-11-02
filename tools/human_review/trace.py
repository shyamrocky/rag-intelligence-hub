"""In-app question/attempt lineage and bounded protected evidence access."""
import json
from pathlib import Path
from uuid import uuid4

from tools.preflight_suite.artifacts import COMPLETION, baseline, save
from tools.quality_dashboard.artifacts import ArtifactError, Store, digest, safe_path, sha

BASE = 'data/evals/human-review/observation-material'


def load_material(root, attempt):
    row = attempt.get('row', {})
    references = []
    if row.get('review_material'):
        references.append(row['review_material'])
    for file in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        store = Store(root)
        store.manifest(file.relative_to(root).as_posix(), schema='observation-material-1.0')
        ref = store.json(file.parent.relative_to(root).as_posix() + '/REFERENCE.json')
        if ref['source'] == attempt.get('source'):
            references.append(ref['material'])
    for ref in reversed(references):
        if (ref['M8_package_sha256'] != attempt['audit']['M8_package_sha256']
                or ref['request_sha256'] != attempt['audit']['request_sha256']):
            raise ArtifactError('REVIEW_MATERIAL_BINDING_MISMATCH')
        p = safe_path(root, ref['artifact']['path'], prefix='workspace/generation-review-material')
        if sha(p) != ref['artifact']['sha256'] or any(x.stat().st_mode & 0o077 for x in (p, p.parent, p.parent.parent, Path(root) / 'workspace/generation-review-material')):
            raise ArtifactError('REVIEW_MATERIAL_UNVERIFIED')
        value = json.loads(p.read_bytes())
        if digest(value['M8_package']) != ref['M8_package_sha256'] or digest(value['M7_result']) != ref['M7_result_sha256']:
            raise ArtifactError('REVIEW_EVIDENCE_HASH_MISMATCH')
        return value
    return None


def prepare_material(root, attempt, question):
    """Explicit local action only; exact historical request package or fail closed."""
    from tools.generation_runner.review_material import retain

    from .local_poc import require_localhost
    from .workflow import live_context
    require_localhost()
    source = attempt.get('source')
    if not source:
        raise ArtifactError('NATIVE_BOUND_RESULT_REQUIRED')
    store = Store(root); store.manifest(source['manifest_path'], expected=source['manifest_sha256'])
    store.bind(source['result_path'], source['result_sha256'])
    row = store.json(source['result_path'])
    if row != attempt['row']:
        raise ArtifactError('HISTORICAL_RESULT_CHANGED')
    service, evidence, m7 = live_context(root, {'question_id': row['question_id'], 'question': question}, row)
    service.check()
    run = Path(root) / 'workspace/local-observation-preparation' / ('local-' + uuid4().hex)
    ref = retain(Path(root), run / 'questions' / row['question_id'], row, evidence, m7)
    folder = Path(root) / BASE / uuid4().hex
    save(folder / 'REFERENCE.json', {'source': source, 'material': ref, 'provider_calls': 0})
    save(folder / 'MANIFEST.json', {'schema': 'observation-material-1.0',
                                 'files': {'REFERENCE.json': sha(folder / 'REFERENCE.json')}})
    return ref


def render(st, root, record, attempt):
    st.subheader('M0 → M10 trace and evidence')
    st.caption('M0–M6 are reused source/index releases. M7 verifies saved candidates; M9 is offline evaluation. '
               'No retrieval, assembly or provider execution occurs on refresh.')
    store, _ = baseline(root)
    m7 = store.json(COMPLETION + '/m7/' + record['question_id'] + '.json')
    case = store.json(COMPLETION + '/m8/' + record['question_id'] + '.json')
    exact = bool(attempt and digest(m7) == attempt.get('row', {}).get('M7_result_sha256')
                 and case['M8_package_sha256'] == attempt['audit'].get('M8_package_sha256'))
    with st.expander('Source preparation and indexes — M0–M6'):
        selector = store
        cfg_name = 'config/hybrid-retrieval-m7-v1.json'
        selector.bind(cfg_name, selector.verified[cfg_name])
        selected = selector.json(cfg_name)
        selector.bind(selected['manifest_path'], selected['manifest_sha256'])
        manifest = selector.json(selected['manifest_path'])
        st.dataframe([{'Release': name, 'Status': 'HASH_VERIFIED_REUSED', 'SHA-256': ref['sha256']}
            for name, ref in manifest['spec']['selections'].items()
            if selector.bind(ref['path'], ref['sha256'])], hide_index=True)
        for name, label in [('m0-m1-prepared-inputs.jsonl', 'M0/M1 prepared sources'),
                            ('M1_M2_VALIDATIONS.json', 'M1/M2 source validation')]:
            path = 'data/chunking/m3-durable-v1/' + name
            if path in store.verified:
                store.bind(path, store.verified[path]); st.write(label + ': verified reused release')
        st.caption('M3 parent/chunk catalog → M4 BGE embeddings → M5 vector index → M6 BM25 lexical index. '
                   'Per-question processing times for these reused releases are NOT_MEASURED.')
    with st.expander('Saved M7 candidates and M8 delivered/omitted parents'):
        st.write('Exact match to selected request' if exact else 'Historical completion measurement; exact request equivalence not established')
        st.dataframe([{'Rank': i+1, 'Chunk': c.get('chunk_id'), 'Unit': c.get('unit_id'),
                       'Score': c.get('score')} for i, c in enumerate(m7['candidates'])], hide_index=True)
        st.write('Supplied complete Units', case['actual_M8_included_parent_ids'])
        st.write('Omitted Units and reasons', case['omitted'])
        st.write('BGE evidence budget (not generator tokens)', case['budget_accounting'])
    with st.expander('M9 known-positive evidence and question requirements'):
        st.write(record['question'])
        st.write('Approved evidence groups', record['group_ids'])
        if record.get('completion'):
            st.json(record['completion'].get('group_outcomes', []))
        st.caption('Missing known-positive evidence is separate from semantic grounding and completeness. '
                   'Labels are not exhaustive relevance judgments. Retrieval precision is unavailable.')
    if attempt:
        st.write('M10 execution: ' + attempt['status'])
        st.dataframe([{'Metric': k, 'Value': str(v)} for k, v in attempt['usage'].items()], hide_index=True)
        if attempt.get('run'):
            timing = attempt['run'].get('timings', {}).get(record['question_id'])
            with st.expander('Stage-level execution latency'):
                if timing:
                    st.caption(timing['mode'] + ' · ' + timing['generation_label'])
                    st.write('End-to-end milliseconds', timing['end_to_end_ms'])
                    st.dataframe(timing['stages'], hide_index=True)
                else:
                    st.info('NOT_MEASURED')
        try:
            from .local_poc import require_localhost
            require_localhost()
            material = load_material(root, attempt)
            with st.expander('Inspect authentic source passages, citations and qualifications'):
                if material:
                    parents = material['M8_package']['parents']
                    units = [p['evidence']['unit_id'] for p in parents]
                    if units:
                        uid = st.selectbox('Authorized source Unit', units, key='trace-unit-' + attempt['experiment'])
                        parent = next(p['evidence']['verified_parent'] for p in parents if p['evidence']['unit_id'] == uid)
                        from tools.answer_quality.fidelity import source_fields
                        for pointer, text in source_fields(parent):
                            st.caption('Publisher passage · ' + pointer); st.text(text)
                        st.write('Citation locators', parent.get('citation_locators'))
                        from .preparation import metadata_fields
                        st.write('QA/use metadata — separate from publisher facts'); st.json(metadata_fields(parent))
                else:
                    st.info('Protected source review material not yet retained for this historical attempt. '
                            'Existing prepared review views remain available below. No evidence is reconstructed on refresh.')
                    if attempt.get('source') and st.button('Prepare exact historical evidence locally (no provider)',
                            key='prepare-trace-' + attempt['experiment']):
                        with st.spinner('Validating original M8 bindings locally'):
                            prepare_material(root, attempt, record['question'])
                        st.rerun()
        except (ArtifactError, ValueError, KeyError, OSError, TypeError):
            st.info('Protected source review unavailable or local access not verified; no source content exposed.')
