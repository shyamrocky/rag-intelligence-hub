"""Compact request progress and guarded diagnostics; no execution imports."""
import streamlit as st

from tools.bot_runtime.trace import CODE, SECRET
from tools.bot_runtime.trace_read import discover, table


def render(root,qid,*,attempt=None,progress=False):
    st.subheader('Request progress')
    st.caption('Progress records operations, not answer correctness. Original validation and owner-review receipts determine acceptance.')
    data=discover(root,qid,progress=progress)
    if data['rejected']:
        st.warning('Some trace records are unavailable or failed integrity checks. They are not accepted as completed execution.')
    if not data['traces']:
        if attempt and attempt.get('timings'):
            from tools.bot_runtime.trace_read import LABELS
            timing=attempt['timings']
            st.dataframe([{'Stage':LABELS.get(x['stage'],'Additional recorded operation'),
                'Status':'Not started' if x['status']=='SKIPPED' else 'Failed' if x['status']=='FAILED' else 'Completed',
                'Seconds':None if x['duration_ms'] is None else round(x['duration_ms']/1000,3)}
                for x in timing['stages']],hide_index=True,width='stretch')
        st.info('This historical execution has no detailed request trace. Its recorded timings and findings remain available; a more specific exception cannot be reconstructed.')
        return
    traces=data['traces']
    # During subprocess execution, show the newest non-driver operations. A final
    # parent seal is still required before anything becomes an accepted result.
    selected=[t for t in traces if not t['folder'].startswith('workspace/')]
    if progress:selected=selected[-1:]
    for trace in selected:
        st.caption(trace['mode'].replace('-',' ').title()+' · '+trace['observation'].replace('_',' ').title())
        st.dataframe(table(trace),hide_index=True,width='stretch')
        for event in trace['events']:
            code=(event.get('detail') or {}).get('error_code')
            if code and CODE.fullmatch(code) and not SECRET.search(code):
                st.error('Recorded failure: '+code)
    if not selected:
        st.info('This selected execution has no detailed execution trace; its original timings and diagnostics remain below.'
                if attempt else 'The backend stage has started; detailed execution observations are not yet available.')
    if not progress:
        if attempt:
            st.caption('Human Review: '+(attempt.get('owner_review_status','PENDING_ASSESSMENT')
                if attempt.get('response') else 'Not available — no accepted generated response'))
        with st.expander('Technical details — trace and protected failure locations'):
            st.caption('Nested observations overlap; do not sum their durations. Use the existing end-to-end timing receipt for totals.')
            st.write([{'run':t['run_id'],'mode':t['mode'],'verification':t['observation']} for t in traces])
            if st.checkbox('Show protected trace diagnostics',key='trace-diagnostics-'+qid):
                try:
                    from tools.human_review.local_poc import require_localhost
                    require_localhost()
                    # Reverify at access time, rather than reuse a stale UI read.
                    checked=discover(root,qid)
                    if checked['rejected']:raise ValueError('TRACE_UNVERIFIED')
                    st.json(checked['traces'])
                except (OSError,ValueError,TypeError,KeyError):
                    st.error('Protected diagnostics require localhost and verified trace artifacts.')
