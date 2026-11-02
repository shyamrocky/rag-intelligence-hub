"""Shared Bot operational view. Discovery is read-only and never imports a runner."""
from pathlib import Path

import streamlit as st

from tools.bot_runtime.projection import discover

ROOT = Path(__file__).resolve().parents[2]
STAGES = {'Knowledge Retrieval', 'Pre-Generation', 'Generation', 'Post-Generation Evaluation', 'Human Review'}


def source(stage, *, data=None):
    key = 'bot-source-' + stage
    shadow = st.session_state.get('workspace-question-source', 'Benchmark questions')
    st.session_state[key] = shadow
    def changed():
        st.session_state['workspace-question-source'] = st.session_state[key]
    choice = st.radio('Question source', ['Benchmark questions', 'Bot questions'], horizontal=True,
                      key=key, on_change=changed)
    if choice == 'Benchmark questions':
        return False
    render(stage, data=data)
    return True


def render(stage, *, root=None, data=None):
    data = discover(root or ROOT) if data is None else data
    st.caption('Bot questions are unlabeled operational records. They are excluded from Offline Retrieval Evaluation and the frozen benchmark.')
    if data['rejected']:
        st.error(f"{len(data['rejected'])} Bot record(s) failed integrity checks and are unavailable.")
    if data['summary'].get('unresolved_native_runs'):
        st.warning('An incomplete native run requires inspection. Output and billing may be unknown; no automatic retry is permitted.')
    records = data['records']
    if not records:
        st.info('No Bot questions recorded yet. A backend simulation and the Bot page use the same native path.')
        return
    for col, label, count in zip(st.columns(3), ['Bot questions', 'Offline simulations', 'Real generation requests'],
        [data['summary']['questions'], data['summary']['mock_runs'], data['summary']['real_generation_requests']], strict=True):
        with col.container(border=True):
            st.metric(label, count)
    show_discarded=st.checkbox('Show discarded questions',value=False,key='bot-discarded-'+stage) if data['summary'].get('discarded_questions') else False
    ids = [q for q,r in records.items() if r.get('disposition','ACTIVE')=='ACTIVE' or show_discarded]
    if not ids:
        st.info('No active Bot questions. Discarded questions remain available in history.')
        return
    prior = st.session_state.get('bot-shared-question')
    key = 'bot-question-' + stage
    if st.session_state.get(key) not in ids:
        st.session_state[key] = prior if prior in ids else ids[0]
    def selected():
        st.session_state['bot-shared-question'] = st.session_state[key]
    qid = st.selectbox('Bot question', ids, key=key, on_change=selected,
                       format_func=lambda q: f"{q} — "+('Discarded — ' if records[q].get('disposition')=='DISCARDED' else '')+records[q]['question'])
    record = records[qid]
    st.markdown(record['question'])
    from apps.knowledge_preparation.bot_chat import show_finding
    show_finding(record.get('chat_execution'))
    st.caption('Answerability: Unassessed · Evidence labels: Unlabeled · No known-positive recall denominator')
    rows = [{
        'Question': r['question_id'], 'Question text': r['question'], 'Disposition':r.get('disposition','ACTIVE'),
        'Mode': a.get('mode', 'NOT_RUN'), 'Execution': a.get('execution_status', 'NOT_RUN'),
        'Model declaration': a.get('model_status') or 'NOT_RUN',
        'Response contract': a.get('response_contract_status', 'NOT_RUN'),
        'Validation': a.get('validation_status', 'NOT_RUN'),
        'Human Review': 'SIMULATION — NOT ELIGIBLE' if a.get('mode') == 'mock' else a.get('owner_review_status', 'PENDING_ASSESSMENT'),
        'Actual cost USD': a.get('cost_usd') if a.get('cost_usd') is not None else 'UNAVAILABLE',
        'Stop reason': (r.get('chat_execution') or {}).get('finding',{}).get('code') if (r.get('chat_execution') or {}).get('finding') else '',
    } for r in records.values() for a in (r['attempts'] or [{}])]
    with st.expander('All Bot questions and outcomes'):
        st.dataframe(rows, hide_index=True, width='stretch')
    if not record['attempts']:
        st.info('Registered; no verified execution result. Any rejected or interrupted record requires inspection before a new submission.')
        return
    attempts = record['attempts']
    index = st.selectbox('Saved Bot execution', range(len(attempts)), index=len(attempts) - 1,
                         format_func=lambda i: attempts[i]['run_id'], key='bot-attempt-' + stage + qid)
    show_attempt(stage, attempts[index])


def show_attempt(stage, attempt):
    if attempt.get('question_disposition')=='DISCARDED':
        st.warning('DISCARDED — original failure and diagnostics retained for history. Start a new chat for a new submission.')
    from apps.knowledge_preparation.request_trace import render as trace_view
    trace_view(ROOT,attempt['question_id'],attempt=attempt)
    mock = attempt['mode'] == 'mock'
    if mock:
        st.warning('MOCK — synthetic evidence and response; no real retrieval, source authority, provider token count or paid inference.')
    st.write('Execution: **' + attempt['execution_status'] + '**')
    if attempt.get('application_outcome'):
        st.write('Outcome: ' + attempt['application_outcome'].replace('_', ' ').title())
    artifacts = attempt.get('artifacts', {})
    if stage == 'Knowledge Retrieval':
        result = artifacts.get('CANDIDATES.json', {})
        st.write(f"{len(result.get('candidates', []))} selected chunks · Hybrid BM25 + BGE · RRF k=60 · Top-30 maximum")
        st.caption('Complete parents are assembled within 128,000 BGE tokens. Empty label coverage does not mean this question is unsupported.')
        st.dataframe(result.get('candidates', []), hide_index=True, width='stretch')
        summary = attempt.get('evidence_summary', {})
        counts, budget = summary.get('counts', {}), summary.get('budget', {})
        st.write(f"Evidence Units: {counts.get('selected_parents', 'UNAVAILABLE')} included · {counts.get('omitted_parents', 'UNAVAILABLE')} excluded")
        tokens = budget.get('exact_llm_evidence_tokens')
        st.write('Evidence size: ' + (f"{tokens:,}" if tokens is not None else 'NOT_MEASURED') + ' / 128,000 BGE tokens')
        with st.expander('Evidence Unit inclusion and exclusions'):
            st.json(summary)
        native = artifacts.get('RETRIEVAL_OBSERVATIONS.json', {})
        with st.expander('Native search observations'):
            st.json(native)
        st.caption('Inspect source passages in Knowledge Preparation → Chunks & Lineage using the exact Chunk ID. Synthetic IDs have no corpus passage.')
    elif stage == 'Pre-Generation':
        audit = artifacts.get('LOCAL_VALIDATION.json', {})
        st.write('Prompt: ' + audit.get('template_version', 'NOT_RUN'))
        st.write('Request preparation: ' + audit.get('status', 'NOT_RUN'))
        if attempt.get('native_attempt') or attempt.get('mode') == 'model-preflight':
            model = attempt.get('audit', {})
            st.dataframe([{'Measurement':name,'Recorded value':str(value) if value is not None else 'UNAVAILABLE'}
                for name,value in [('Model input tokens',model.get('generator_input_tokens')),
                    ('Context fit',model.get('context_fit')),('Maximum estimated cost USD',model.get('cost_estimate',{}).get('estimated_max_cost_usd'))]], hide_index=True)
            with st.expander('Model preflight call measurements'):
                st.json(artifacts.get('PROVIDER_CALLS.json', 'Available in the sealed native generation audit/timing receipt'))
            st.caption('Saved qualification is not permanent authorization. Fresh source, model, token and cost checks remain mandatory before generation.')
        else:
            st.info('Local assembly is not model qualification. No provider tokens, current context-fit approval or live cost qualification were measured.')
        with st.expander('Local checks'):
            st.json(audit)
    else:
        response = attempt.get('response')
        if response:
            from tools.answer_quality.abstention import render_response
            render_response(st, response)
            st.caption('Model-declared status: ' + response['status'] + ' · Semantic acceptance is separate.')
            with st.expander('Citations, quotations, claim inventory and model declarations'):
                st.json({k: response.get(k) for k in ('claims', 'requirement_coverage', 'relevant_qualifications',
                                                    'conflicts_detected', 'missing_information')})
        elif attempt.get('native_attempt'):
            from apps.knowledge_preparation.generation import returned_output
            returned_output(attempt['native_attempt'])
        elif artifacts.get('RESPONSE_OBSERVATION.json'):
            st.warning('Returned output failed the response contract. It remains available for diagnostic review; it cannot be approved as an accepted answer.')
            with st.expander('Captured output — untrusted'):
                st.json(artifacts['RESPONSE_OBSERVATION.json'])
        else:
            st.info('No accepted model response. An operational failure or empty-evidence block is not an LLM abstention.')
        st.write('Validation: **' + attempt.get('validation_status', 'NOT_RUN') + '**')
        st.caption('Grounding, completeness, applicable qualifications and conflicts require an actual independent assessment. No findings are invented from citation presence.')
        with st.expander('Technical validation findings'):
            st.json(attempt.get('post_validation'))
        if stage == 'Human Review' and attempt.get('native_attempt'):
            from tools.bot_runtime.native import review
            review(st, ROOT, attempt['native_record'], attempt['native_attempt'])
        elif stage == 'Human Review':
            st.info('Simulation entries are diagnostic-only. Local checks have no generated answer. Owner approval and signed review cannot accept either as a real generated result.')
            st.button('Approve', disabled=True, key='bot-approve-' + attempt['run_id'])
            st.button('Reject', disabled=True, key='bot-reject-' + attempt['run_id'])
            st.button('Request Changes', disabled=True, key='bot-changes-' + attempt['run_id'])
            st.caption('Existing benchmark local-owner and signed review controls remain available under Benchmark questions.')
    if attempt.get('diagnostics'):
        st.warning('Recorded diagnostic findings')
        st.json(attempt['diagnostics'])
    timing = attempt.get('timings')
    if timing:
        st.write(f"End-to-end: {timing['end_to_end_ms'] / 1000:.3f} sec")
        with st.expander('Execution stages and timing'):
            from apps.knowledge_preparation.generation import STAGE_NAMES
            st.dataframe([{'Stage': STAGE_NAMES.get(s['stage'], 'Fresh candidate retrieval' if s['stage']=='LIVE_RETRIEVAL' else s['stage'].replace('_',' ').title()), 'Status': s['status'],
                'Seconds': None if s['duration_ms'] is None else round(s['duration_ms'] / 1000, 3)} for s in timing['stages']],
                hide_index=True, width='stretch')
    capture = attempt.get('raw_capture')
    with st.expander('Protected raw-response diagnostics'):
        if not capture or capture.get('artifact') is None:
            st.info('Raw response unavailable.' if not capture else capture['status'] + ' — raw response unavailable.')
        elif st.checkbox('Show protected raw response', key='bot-raw-' + stage + attempt['run_id']):
            try:
                from tools.generation.response_capture import verify_capture
                from tools.human_review.local_poc import require_localhost
                require_localhost()
                path = verify_capture(ROOT, capture, attempt, run_id=attempt['run_id'])
                if path is not None:
                    st.code(path.read_bytes().decode('utf-8', errors='replace'), language='json')
            except (ValueError, OSError, KeyError, TypeError):
                st.error('Raw response unavailable or unverified. No unverified bytes are shown.')
    with st.expander('Technical Details — exact identity and provenance'):
        st.json({k: attempt.get(k) for k in ('question_id', 'run_id', 'question_reference', 'manifest_path',
            'M7_result_sha256', 'M8_package_sha256', 'request_sha256', 'trust', 'raw_capture')})
