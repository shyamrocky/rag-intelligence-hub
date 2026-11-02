"""Read-only failed-generation inbox. Diagnostic inspection never approves an answer."""
import hashlib

from tools.generation.response_capture import NAME, verify_capture
from tools.generation_runner.dashboard import discover as generation_runs
from tools.quality_dashboard.artifacts import ArtifactError, Store


def discover(root):
    entries = []
    questions = {}
    try:
        from tools.preflight_suite.artifacts import baseline
        _, questions = baseline(root)
    except (ArtifactError, ValueError, KeyError, OSError):
        pass
    for run in generation_runs(root)['runs']:
        for row in run['results']['questions']:
            if (row.get('response') is not None or not (row.get('generation_executed')
                    or row.get('generation_attempted') or row.get('status') == 'RAW_RESPONSE_CAPTURE_FAILED')):
                continue
            q = questions.get(row['question_id'], {})
            text = q.get('question')
            if text and hashlib.sha256(text.encode()).hexdigest() != row.get('question_sha256'):
                text = None
            entries.append({'row': row, 'run': run, 'question': text,
                            'identity': run['manifest']['run_id'] + '/' + row['question_id']})
    return entries


def capture_reference(root, entry):
    run, row = entry['run'], entry['row']
    store = Store(root)
    store.manifest(run['manifest_path'], schema='grounded-generation-runner-1.0')
    base = run['manifest_path'].rsplit('/', 1)[0]
    receipt = row.get('audit', {}).get('raw_response_capture')
    relative = f"questions/{row['question_id']}/{NAME}"
    if relative in run['manifest']['files']:
        sealed = store.json(base + '/' + relative)
        if receipt is not None and receipt != sealed:
            raise ArtifactError('CAPTURE_RECEIPT_MISMATCH')
        receipt = sealed
    elif receipt and receipt.get('status') == 'RAW_RESPONSE_CAPTURED':
        raise ArtifactError('UNSEALED_CAPTURE_RECEIPT')
    if receipt is None:
        return None, None
    return receipt, verify_capture(root, receipt, row, run_id=run['manifest']['run_id'])


def render(st, root):
    entries = discover(root)
    if not entries:
        return
    with st.expander('Human Review — response failure diagnostics', expanded=True):
        st.caption('Read-only diagnostic items. An unparseable response cannot be approved as an answer.')
        index = st.selectbox('Question / generation failure', range(len(entries)), index=len(entries)-1,
            key='response_diagnostic_entry', format_func=lambda i: entries[i]['row']['question_id']
            + ' — ' + entries[i]['row']['status'] + ' · ' + entries[i]['run']['manifest']['run_id'])
        entry = entries[index]
        row, audit = entry['row'], entry['row'].get('audit', {})
        st.write(entry['question'] or 'Original question unavailable or unverified.')
        st.error('Generation response rejected or unavailable: ' + row['status'])
        st.json({'blocking_reasons': audit.get('blocking_reasons', []),
                 'specific_validation_errors': audit.get('response_diagnostics', []),
                 'usage': audit.get('usage'), 'request_sha256': row['request_sha256'],
                 'source_result': entry['run']['manifest_path']})
        try:
            receipt, path = capture_reference(root, entry)
            if receipt is None:
                st.info('RAW RESPONSE UNAVAILABLE — historical execution did not retain the provider output. '
                        'No original text or exact parser subcause can be reconstructed from its hash.')
            else:
                st.write('Raw response capture: ' + receipt['status'])
                st.json(receipt)
                if path is None:
                    st.warning('Raw response unavailable. ' + str(receipt.get('reason') or 'No captured body.'))
                elif st.checkbox('Show protected raw provider response', key='raw-response-' + entry['identity']):
                    from .local_poc import require_localhost
                    require_localhost()
                    # Reverify at read time. Plain code display treats model output as data.
                    _, path = capture_reference(root, entry)
                    st.code(path.read_bytes().decode('utf-8', errors='replace'), language='json')
        except (ArtifactError, ValueError, KeyError, OSError, TypeError):
            st.warning('Raw response unavailable or unverified; check the capture receipt, hash and localhost access.')
        timing = entry['run'].get('timings', {}).get(row['question_id'])
        if timing:
            with st.expander('Diagnostic execution timings'):
                st.dataframe(timing['stages'], hide_index=True)
        st.caption('No approval, retry, generation or source reconstruction is available from this diagnostic view.')
