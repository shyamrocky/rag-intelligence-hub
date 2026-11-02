"""Read-only tracker tables; no source payloads, review actions or execution controls."""
import csv
import io
import json

import streamlit as st

from tools.quality_dashboard.artifacts import ArtifactError

from .adapter import build


def render(root, data=None):
    st.title('Final Generation Benchmark Tracker')
    st.caption('Verified generation attempts grouped by rollout stage and batch. Refresh is read-only.')
    st.page_link(st.session_state['master_dashboard_page'], label='Back to Master Dashboard', icon='📚')
    try:
        tracker = build(root, data)
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        st.error('UNAVAILABLE — tracker artifact identity or provenance verification failed.')
        return
    st.session_state['final_benchmark_tracker'] = tracker
    summary = tracker['summary']
    columns = st.columns(4)
    for col, label, value in zip(columns,
        ['Questions attempted', 'Accepted structured responses', 'Without accepted response', 'Attempt records'],
        [summary['attempted_questions'], summary['generation_completed'],
         summary['attempted_without_parsed_answer'], summary['attempt_records']]):
        col.metric(label, value)
    st.info('A parsed contract, exact quotation or model-declared ANSWERED status does not establish semantic '
            'correctness. LOCAL_POC_REVIEW approval is separate from authenticated formal validation. '
            'Original verdicts remain unchanged; source-bound reassessments are shown separately.')
    st.subheader('Batch costs and execution')
    st.dataframe(tracker['batches'], hide_index=True, width='stretch')
    st.caption(f"Measured-use estimated API cost across attempts: ${summary['measured_attempt_cost_usd']} · "
               f"{summary['unknown_cost_attempts']} attempt(s) with unavailable cost. Not invoice charges or account balance. "
               'Batch 4 includes the separately authorized Q18 recovery attempt; historical Q05 includes its failed attempt.')
    st.subheader('Question results')
    left, middle, right = st.columns(3)
    stage = left.selectbox('Batch / rollout stage', ['All stages', *[b['Stage'] for b in tracker['batches']]], key='tracker_stage')
    cohort = middle.selectbox('Question cohort', ['All cohorts', *sorted({r.get('Cohort', 'UNAVAILABLE') for r in tracker['rows']})], key='tracker_cohort')
    validation = right.selectbox('Validation filter', ['All results', 'Failed validation', 'Contract rejected', 'Review required'], key='tracker_validation')
    rows = [r for r in tracker['rows'] if (stage == 'All stages' or r['Stage'] == stage)
            and (cohort == 'All cohorts' or r.get('Cohort') == cohort)]
    if validation != 'All results':
        rows = [r for r in rows if {'Failed validation': r['Validation'] in {'VALIDATION_FAILED', 'FAILED'},
                'Contract rejected': r.get('Contract') == 'CONTRACT_REJECTED',
                'Review required': r['Validation'] in {'REVIEW_REQUIRED', 'INDETERMINATE'}}[validation]]
    visible = ['Stage', 'Question', 'Model status', 'Contract', 'Validation', 'Owner review', 'Main findings',
               'Estimated API cost USD', 'API seconds', 'Raw response']
    st.dataframe([{key: r.get(key) for key in visible} for r in rows], hide_index=True, width='stretch',
                 column_config={'Main findings': st.column_config.TextColumn(width='large')})
    st.caption('API seconds exclude M8 reconstruction and subsequent review preparation. Model status on a '
               'rejected contract is an untrusted declaration. NOT_RECORDED_HISTORICAL does not imply that a '
               'structured answer was lost; dedicated raw-body capture was added later.')
    if rows:
        if st.session_state.get('tracker_question') not in {r['Question'] for r in rows}:
            st.session_state['tracker_question'] = rows[0]['Question']
        qid = st.selectbox('Tracker question', [r['Question'] for r in rows], key='tracker_question')
        row = next(r for r in rows if r['Question'] == qid)
        st.write(row['Question text'])
        st.write(row.get('Main findings', ''))
        st.page_link(st.session_state['generation_runner_page'], label='Open Generation Runner → Human Review', icon='🧪')
        with st.expander('Technical details — selected result'):
            st.json(row)
    with st.expander('Export source-free run view'):
        output = io.StringIO()
        names = list(dict.fromkeys(key for row in tracker['rows'] for key in row))
        writer = csv.DictWriter(output, fieldnames=names)
        writer.writeheader()
        writer.writerows(tracker['rows'])
        st.download_button('Download tracker CSV', output.getvalue(), file_name='final-generation-benchmark-tracker.csv', mime='text/csv')
        st.download_button('Download tracker JSON', json.dumps(tracker, indent=2), file_name='final-generation-benchmark-tracker.json', mime='application/json')
    if tracker['unverified_review_records'] or tracker['unverified_assessment_records']:
        st.warning('Some review/assessment records could not be verified and were not used to establish acceptance.')
