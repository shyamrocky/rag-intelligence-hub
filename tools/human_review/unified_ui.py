"""One answer selector, exact attempt history, preserved ordinary/signed review paths."""
from tools.quality_dashboard.artifacts import digest


def select(st, root):
    from pathlib import Path

    from tools.quality_dashboard.completion_adapter import load_completed

    from . import local_poc
    from .handoff import discover
    from .review_state import status_label
    if not (Path(root) / 'data/evals/expanded-benchmark/v1/MANIFEST.json').exists():
        return None  # Preserve standalone prepared/signed review component use.
    data = load_completed(root)
    entries = discover(root)['entries']
    history, _ = local_poc.discover(root)
    records = {q: r for q, r in data['records'].items() if r['attempts']}
    if not records:
        return None
    def label(qid):
        record = records[qid]; a = record['latest_attempt']
        if not a['completed']:
            return qid + ' — Output contract issue / owner triage'
        entry = next((e for e in entries if e['question_id'] == qid and e['row'].get('response') == a['response']), None)
        if entry:
            target = {'question_id': qid, 'policy': entry['policy'], 'bindings': {
                'question_sha256': entry['row']['question_sha256'], 'response_sha256': digest(a['response']),
                'request_sha256': a['audit']['request_sha256'], 'package_sha256': a['audit']['M8_package_sha256']}}
            return qid + ' — ' + status_label(target, history)
        return qid + ' — Historical answer / review pending'
    qid = st.selectbox('Completed generation for Human Review', list(records),
        index=len(records)-1, key='unified-review-question', format_func=label)
    record = records[qid]
    attempts = record['attempts']
    a = attempts[-1]
    with st.expander('Generation attempt history — original results preserved'):
        selected = st.selectbox('Exact response / attempt', range(len(attempts)), index=len(attempts)-1,
            key='unified-review-attempt-' + qid, format_func=lambda i: attempts[i]['experiment'].rsplit('/',1)[-1]
                + ' · ' + attempts[i]['status'])
        a = attempts[selected]
        st.dataframe([{'Attempt': x['experiment'].rsplit('/',1)[-1], 'Contract parsed': x['completed'],
                       'Status': x['status'], 'Cost USD': x['usage'].get('total_estimated_cost_usd')}
                      for x in attempts], hide_index=True)
    st.subheader(qid + ' — Human Review')
    st.write(record['question'])
    if not a['completed']:
        from .observation_review import render
        render(st, root, a)
    elif not a.get('run'):
        from tools.answer_quality.abstention import render_response
        render_response(st, a['response'])
        st.info('Historical Q05 response and validation retained. Owner semantic review is pending; '
                'this legacy record is not silently converted into a native approval package.')
    from .trace import render as trace
    with st.expander('Pipeline trace, evidence and measured telemetry'):
        trace(st, root, record, a)
    return {'record': record, 'attempt': a,
            'normal_entry': next((e for e in entries if e['question_id'] == qid
                and e['source'] == a.get('source')), None)}
