"""Shared answer/attempt presentation; preserves strict original findings."""
from . import ui as historical


def render(data, record, attempt):
    st = historical.st
    if attempt and not attempt['completed']:
        st.subheader('Generation — Returned Output & Findings')
        st.warning('Provider attempt recorded; structured answer contract was not accepted. '
                   'This is not an independent factual-error judgment.')
        if attempt.get('run'):
            from tools.human_review.observation_review import render as observation
            observation(st, data['store'].root, attempt)
        else:
            st.info('Original response text unavailable for this historical attempt.')
        st.dataframe([attempt['usage']], hide_index=True)
    else:
        historical.generation(data, record, attempt)
    if attempt:
        from tools.human_review.trace import render as trace
        with st.expander('M0–M10 provenance, supplied evidence and attempt details'):
            trace(st, data['store'].root, record, attempt)
