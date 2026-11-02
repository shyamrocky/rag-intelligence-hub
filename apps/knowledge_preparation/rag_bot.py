"""Single-turn offline Bot preview; durable diagnostics, no saved conversations."""
import streamlit as st

STYLE = """
<style>
.stApp:has(.st-key-rag-bot),
[data-testid="stAppViewContainer"]:has(.st-key-rag-bot) {background:#f7f8fa;}
.st-key-rag-bot {max-width:940px;margin:5vh auto 2rem;gap:1rem;}
.st-key-rag-bot h1 {text-align:center;}
.st-key-rag-bot > [data-testid="stMarkdownContainer"],
.st-key-rag-bot > [data-testid="stCaptionContainer"] {text-align:center;}
.st-key-rag-bot-heading h1 {padding:0!important;margin:0!important;
    display:flex;align-items:center;justify-content:center;gap:1rem;}
.st-key-rag-bot-heading h1::before {content:"✦" / "";
    width:64px;height:64px;flex:0 0 64px;border-radius:18px;
    display:grid;place-items:center;font-size:2rem;font-weight:400;
    line-height:1;letter-spacing:0;color:#526b83;
    background:linear-gradient(135deg,#e5edf8,#eee8f6);border:1px solid #e2e7ef;}
.rag-bot-intro {text-align:center;color:#62626a;font-size:1.12rem;line-height:1.6;}
.st-key-rag-bot [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius:18px;border-color:#e3e7ed;box-shadow:none;
}
.st-key-rag-bot .st-key-rag-example-understand {background:#edf3fa;border-radius:18px;padding:1.1rem;}
.st-key-rag-bot .st-key-rag-example-explore {background:#edf4f0;border-radius:18px;padding:1.1rem;}
.st-key-rag-bot .st-key-rag-example-compare {background:#f1eef7;border-radius:18px;padding:1.1rem;}
.st-key-rag-bot [data-testid="stColumn"] > div {height:100%;}
.st-key-rag-bot [class*="st-key-rag-example-"] {height:100%;min-height:145px;gap:.4rem;}
.st-key-rag-bot [class*="st-key-rag-example-"] p {color:#353b46;}
.st-key-rag-bot [class*="st-key-rag-example-"] [data-testid="stCaptionContainer"] {color:#52606d;}
@media(max-width:800px) {.st-key-rag-bot {margin-top:2vh;}}
</style>
"""

EXAMPLES = [
    ("understand", "Understand", "What is RAG, and when would I use it?"),
    ("explore", "Explore", "How do keyword and vector search work together?"),
    ("compare", "Compare", "How does chunking affect retrieval?"),
]


def submitted_question(text):
    """Session display only: the user's question stays outside collapsed status."""
    with st.container(border=True, key='rag-submitted-question'):
        st.caption('Your question')
        st.write(text)


def render():
    st.markdown(STYLE, unsafe_allow_html=True)
    with st.container(key="rag-bot"):
        with st.container(horizontal=True, horizontal_alignment='center', vertical_alignment='center',
                          wrap=False, key='rag-bot-heading'):
            st.title("What would you like to explore?", width='content')
        st.markdown('<p class="rag-bot-intro">Ask a question about RAG. We’ll find and verify the evidence before answering.</p>', unsafe_allow_html=True)
        st.caption("Example questions")
        for column, (key, label, question) in zip(st.columns(3), EXAMPLES, strict=True):
            with column, st.container(border=True, key="rag-example-" + key):
                st.caption(label)
                st.markdown(question)
    from pathlib import Path
    from uuid import uuid4

    from apps.knowledge_preparation.bot_chat import controls as approval_controls
    from apps.knowledge_preparation.bot_chat import show_finding
    from apps.knowledge_preparation.bot_chat import state as chat_state
    from tools.bot_runtime.chat_records import record as chat_record
    from tools.bot_runtime.dispatch import completed, native
    from tools.bot_runtime.store import register

    root = Path(__file__).resolve().parents[2]
    active = st.session_state.get('bot-active-id')
    guidance = st.expander('Guidance & limits', expanded=False)
    with st.expander('Developer settings', expanded=False):
        mode = st.radio('Request mode', ['Chat', 'Request Approvals / Triage', 'Offline Simulation'],
                        key='bot-request-mode', help='Changing modes never submits a question or grants permission.')
    previous_mode = st.session_state.get('bot-rendered-mode', mode)
    st.session_state['bot-rendered-mode'] = mode
    if mode != 'Chat':
        st.caption('Mode: ' + mode)
    if st.button('New chat', key='bot-new-chat'):
        for key in ['bot-active-id', 'bot-submission-id', 'bot-next-step', 'bot-chat-dispatch-finding',
                    'bot-question-draft', 'bot-restore-draft', 'bot-ui-request', 'bot-question-input']:
            st.session_state.pop(key, None)
        st.rerun()
    st.caption('To ask another question after receiving an answer, click New chat. Each question starts fresh.')

    readiness = chat_state(root)
    with guidance:
        if readiness['enabled']:
            settings = readiness['settings']
            st.caption(f"Chat ready · \\${settings['per_question_cap_usd']} per question · \\${settings['total_bot_cap_usd']} total Bot cap")
            if readiness['budget']:
                st.caption(f"Available after existing reservations: \\${readiness['budget']['remaining_usd']}")
        else:
            st.caption('Current Chat configuration or spending information is unavailable.')
        from tools.generation_runner.bot_chat import DISCLOSURE
        st.caption(DISCLOSURE)
        st.caption('Execution records are retained privately for diagnostics and review; conversations and answers are not cached.')
        st.caption('Preparing a grounded answer can take a couple of minutes while we find and verify the evidence.')
    # The keyed composer is always rendered BEFORE approval controls can rerun.
    # A pending Send is captured as a draft first. Programmatic prefill does not
    # submit: Streamlit requires the user to Send the restored text explicitly.
    queued_text = st.session_state.get('bot-question-input')
    if not active and isinstance(queued_text, str) and queued_text:
        st.session_state['bot-question-draft'] = queued_text
        st.session_state['bot-restore-draft'] = True
    # A new user Send already in widget state takes precedence over prefill.
    if (not active and st.session_state.pop('bot-restore-draft', False)
            and not st.session_state.get('bot-question-input')):
        st.session_state['bot-question-input'] = st.session_state.get('bot-question-draft', '')
    prompt = st.chat_input('Ask a question about RAG…', key='bot-question-input',
                           disabled=bool(active) or mode != 'Chat')
    if prompt and not active:
        st.session_state['bot-question-draft'] = prompt
        st.session_state['bot-restore-draft'] = True

    if mode == 'Request Approvals / Triage':
        st.caption('Prepare evidence locally and inspect the existing staged approval workflow. No automatic paid request.')
        approval_controls()
        from apps.knowledge_preparation.bot_live import render as live_readiness
        live_readiness(active=active)
    elif mode == 'Offline Simulation':
        st.info('Offline simulation uses synthetic evidence and responses. The main chat box is disabled; backend simulation tools remain available. No provider calls or paid generation.')
    elif not readiness['enabled']:
        st.warning('Chat configuration could not be verified. Send will record a clear stop reason; no safety check will be bypassed.')
    elif readiness['blocked']:
        st.warning('A budget or execution-history check requires attention. A new request will stop safely if the check remains unresolved.')

    if active:
        st.session_state['workspace-question-source'] = 'Bot questions'
        st.session_state['bot-shared-question'] = active
        ui = st.session_state.get('bot-ui-request', {})
        text = ui.get('question') if ui.get('question_id') == active else None
        if not text:
            from tools.bot_runtime.store import question_record
            from tools.quality_dashboard.artifacts import ArtifactError
            try:
                text = question_record(root, active)['question']
            except (ArtifactError, OSError, ValueError, KeyError, TypeError):
                text = None
        if text:
            submitted_question(text)
        if ui.get('label'):
            st.info(ui['label'])
        st.caption('Execution reference: ' + active)
        attempt = completed(root, active)
        control = chat_record(root, active)
        show_finding(control)
        show_finding(st.session_state.get('bot-chat-dispatch-finding'))
        if attempt:
            response = attempt.get('response') or {}
            if mode == 'Chat' and response:
                if response.get('answer'):
                    st.markdown(response['answer'])
                else:
                    st.markdown('**Unable to answer from available evidence**')
                    for missing in response.get('missing_information', []):
                        st.markdown(missing)
                st.caption('Model status: ' + response.get('status', 'UNAVAILABLE') + ' · Independent answer-quality review remains separate.')
            from apps.knowledge_preparation.bot_records import show_attempt
            with st.expander('Execution details', expanded=mode != 'Chat'):
                show_attempt('Pre-Generation' if attempt['mode'] in {'local-check', 'model-preflight'} else 'Generation', attempt)
        elif not control or control.get('status') == 'INCOMPLETE':
            st.warning('No completed execution receipt is available yet. The outcome is not confirmed; do not resubmit. Refresh to inspect saved progress.')
        for column, label in zip(st.columns(3), ['Knowledge Retrieval', 'Generation', 'Human Review'], strict=True):
            if label in st.session_state.get('kp_pages', {}):
                column.page_link(st.session_state['kp_pages'][label], label=label)

    if not prompt or active:
        return
    if mode != 'Chat':
        st.info('The chat box is disabled in developer modes. Your draft is preserved; return to Chat to Send.')
        return
    if previous_mode != mode:
        st.info('Your question is preserved. Confirm the selected mode, then Send when ready.')
        return
    qid = None
    submitted_question(prompt)
    with st.status('Question received — recording your request…', expanded=True) as status:
        try:
            from tools.human_review.local_poc import require_localhost
            require_localhost()
            nonce = st.session_state.setdefault('bot-submission-id', uuid4().hex)
            question = register(root, prompt, nonce)
            qid = question['question_id']
            st.session_state['bot-active-id'] = qid
            st.session_state['bot-question-draft'] = ''
            st.session_state['bot-restore-draft'] = False
            st.session_state['bot-ui-request'] = {'question_id': qid, 'mode': mode,
                'label': 'Question received · ' + qid, 'state': 'RECEIVED', 'question': prompt}
            st.write('Question received · ' + qid)
            status.update(label='Processing — preparing your request · ' + qid, state='running')
            st.session_state['bot-ui-request'].update(label='Processing · ' + qid, state='PROCESSING')
            progress_area = st.empty()
            def progress():
                from apps.knowledge_preparation.request_trace import render as trace_view
                from tools.bot_runtime.trace_read import LABELS, discover
                traces = discover(root, qid, progress=True)['traces']
                events = [e for t in traces if not t['folder'].startswith('workspace/') for e in t['events']]
                if events:
                    event = max(events, key=lambda e: e['timestamp'])
                    label = LABELS.get(event['stage'], 'Preparing request')
                    status.update(label='Processing — ' + label + ' · ' + qid, state='running')
                with progress_area.container():
                    trace_view(root, qid, progress=True)
            value = native(root, qid, 'chat', arguments=['--confirm-exact-request'], progress=progress)
            if value.get('finding'):
                st.session_state['bot-chat-dispatch-finding'] = value
            control = chat_record(root, qid)
            attempt = completed(root, qid)
            issue = st.session_state.get('bot-chat-dispatch-finding')
            if (control and control.get('status') in {'BLOCKED', 'FAILED', 'INCOMPLETE'}) or issue:
                label = 'Stopped — see the recorded reason · ' + qid
                state = 'STOPPED'
            elif control and control.get('status') == 'REVIEW_REQUIRED':
                label = 'Response received — review required · ' + qid
                state = 'REVIEW_REQUIRED'
            elif (control and control.get('status') == 'COMPLETED') or (attempt and attempt.get('execution_status') == 'COMPLETED'):
                label = 'Answer received · ' + qid
                state = 'COMPLETED'
            elif attempt and attempt.get('execution_status') in {'FAILED', 'BLOCKED'}:
                label = 'Stopped — see the recorded reason · ' + qid
                state = 'STOPPED'
            else:
                label = 'Execution recorded — inspect the saved outcome · ' + qid
                state = 'RECORDED'
            st.session_state['bot-ui-request'].update(label=label, state=state)
            status.update(label=label, state='error' if state == 'STOPPED' else 'complete')
        except (OSError, ValueError, KeyError, TypeError):
            label = ('Stopped — execution retained; no automatic retry · ' + qid if qid
                     else 'Could not record your question. The draft is retained; no automatic retry.')
            if qid:
                st.session_state['bot-ui-request'].update(label=label, state='STOPPED')
            status.update(label=label, state='error')
            st.error(label)
    if qid:
        st.rerun()
