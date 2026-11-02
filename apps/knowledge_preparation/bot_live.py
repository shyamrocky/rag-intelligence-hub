"""Explicit staged owner consent UI. Refresh reads only; no broad live chat switch."""
from pathlib import Path
from uuid import uuid4

import streamlit as st

from tools.bot_runtime.store import directory, read, write
from tools.quality_dashboard.artifacts import ArtifactError, sha

ROOT=Path(__file__).resolve().parents[2]


def pending(root):
    """Only independently prepared, sealed exact-question requests are selectable."""
    values=[]
    from tools.bot_runtime.projection import discover
    from tools.generation_runner.bot_consent import preparation
    data=discover(root)
    if data['rejected']:
        return values
    for file in sorted((Path(root)/'workspace/bot-authorizations').glob('*/MANIFEST.json')):
        try:
            folder,m=preparation(root,file.relative_to(root).as_posix(),sha(file))
            if m['schema']=='bot-unsigned-preflight-preparation-1.0':
                template=read(folder/'PREFLIGHT_CONSENT_TEMPLATE.json')
                operation='model-preflight';qid=template['context']['question_id']
                info=template['context']
            elif m['schema']=='generation-unsigned-preparation-1.0':
                plan=read(folder/'PLAN.json')
                if plan.get('question_source')!='BOT' or len(plan['questions'])!=1:
                    continue
                operation='live';qid=plan['questions'][0]['question_id'];info=plan
            else:
                continue
            if data['records'].get(qid,{}).get('disposition')=='DISCARDED':
                continue
            attempts=data['records'].get(qid,{}).get('attempts',[])
            if operation=='model-preflight' and (any(a['mode']=='model-preflight' for a in attempts)
                    or (Path(root)/'data/runtime-qualifications/v1/claims'/f'{qid}.json').exists()):
                continue
            if operation=='live' and any(a.get('native_attempt') or a['mode']=='live' for a in attempts):
                continue
            values.append({'manifest':file.relative_to(root).as_posix(),'sha256':sha(file),
                           'operation':operation,'question_id':qid,'info':info})
        except (ArtifactError,ValueError,KeyError,TypeError,OSError):
            continue
    return values


def prepare_next(root,qid):
    """Only called following an explicit submission or stage-preparation click."""
    from tools.bot_runtime.dispatch import native
    outcome=native(root,qid,'prepare-next',arguments=[
        '--output','workspace/bot-authorizations/step-'+uuid4().hex])
    st.session_state['bot-next-step']=outcome
    return outcome


def render(*,active=None):
    with st.expander('Live request readiness — separate owner consent',expanded=False):
        if active:
            from tools.bot_runtime.disposition import read as disposition
            try:discarded=disposition(ROOT,active)
            except (ArtifactError,OSError,ValueError,KeyError,TypeError):
                st.error('Request disposition could not be verified. Approval controls are unavailable.')
                return
            if discarded:
                st.info('This request is DISCARDED. Its history is retained; start a new chat for a new submission.')
                return
        st.caption('Prepare evidence locally, authorize token/count preflight, then separately authorize one exact paid request. No automatic continuation or retries.')
        values=pending(ROOT)
        if active:
            values=[v for v in values if v['question_id']==active]
        if not values:
            outcome=st.session_state.get('bot-next-step',{})
            if active and outcome.get('status')=='POLICY_REVIEW_REQUIRED':
                st.info('Evidence preparation is recorded. This question’s exact provider or spending scope still needs review; no OpenAI call has been authorized.')
            else:
                st.info('Type a question to prepare evidence locally. Provider preflight and paid answering require separate approval.')
            if active:
                if st.button('Prepare next approval step',key='bot-prepare-next'):
                    try:
                        from tools.human_review.local_poc import require_localhost
                        require_localhost()
                        prepare_next(ROOT,active)
                        st.rerun()
                    except (ArtifactError,ValueError,KeyError,TypeError,OSError):
                        st.error('The next step is blocked. No provider call or retry was made; inspect the saved execution state.')
                if outcome:
                    st.caption('Readiness: '+outcome.get('status','UNAVAILABLE').replace('_',' ').title())
            return
        index=st.selectbox('Prepared request',range(len(values)),
            format_func=lambda i:values[i]['question_id']+' · '+('Model token and cost preflight' if values[i]['operation']=='model-preflight' else 'One paid generation request'),
            key='bot-live-preparation')
        value=values[index];qid=value['question_id'];live=value['operation']=='live'
        from tools.bot_runtime.store import question_record
        question=question_record(ROOT,qid)
        st.markdown(question['question'])
        if live:
            plan=value['info'];r=plan['questions'][0]
            st.write(f"Projected maximum: ${r['maximum_cost_usd']} · Request ceiling: ${r['per_question_cap_usd']} · Plan ceiling: ${plan['aggregate_cap_usd']}")
            st.caption('One generation request; zero retries or fallback. Historical benchmark permissions are not Bot authority.')
        else:
            st.write('Maximum one model-metadata request and one token-count request. Full verified evidence will be sent to OpenAI; no answer will be generated.')
        local=True
        try:
            from tools.human_review.local_poc import require_localhost
            require_localhost()
        except (ArtifactError,ValueError,TypeError):
            local=False
            st.warning('Owner consent requires direct localhost access.')
        with st.form('bot-consent-'+value['sha256'],clear_on_submit=True):
            statement=st.text_area('Your explicit approval statement',key='bot-owner-statement-'+value['sha256'])
            confirmed=st.checkbox('I approve this exact question, evidence transfer and the displayed call/spending limits.',key='bot-owner-confirm-'+value['sha256'])
            submit=st.form_submit_button('Approve generation' if live else 'Approve token/cost preflight',disabled=not local)
        if submit:
            try:
                from tools.bot_runtime.dispatch import native
                from tools.human_review.local_poc import require_localhost
                require_localhost()
                if confirmed is not True or not statement.strip():
                    raise ArtifactError('EXPLICIT_OWNER_APPROVAL_REQUIRED')
                # Sealed preparation is reverified in the isolated native CLI; the
                # statement is never a command-line argument or printed diagnostic.
                folder=directory(ROOT,'workspace/bot-ui-submissions/'+uuid4().hex)
                textfile=folder/'OWNER_STATEMENT.json'
                write(textfile,{'statement':statement})
                # The native CLI extracts the exact owner-supplied statement.
                issued=native(ROOT,qid,'issue-live-consent' if live else 'issue-preflight-consent',arguments=[
                    '--preparation-manifest',value['manifest'],'--preparation-sha',value['sha256'],
                    '--owner-statement-file',textfile.relative_to(ROOT).as_posix(),'--confirm-exact-request'])
                if live:
                    plan=value['info'];r=plan['questions'][0]
                    args=['--preflight-manifest',plan['preflight_manifest'],'--per-question-cap',r['per_question_cap_usd'],
                        '--aggregate-cap',plan['aggregate_cap_usd'],'--owner-authorization',issued['consent'],
                        '--authorization-sha',issued['consent_sha256'],'--execute-approved-live']
                else:
                    args=['--local-manifest',value['info']['local_manifest'],'--preflight-consent',issued['consent'],
                          '--preflight-consent-sha',issued['consent_sha256']]
                with st.status('Preparing a grounded request and verifying its authorization…'):
                    from apps.knowledge_preparation.request_trace import render as progress_view
                    placeholder=st.empty()
                    def progress():
                        with placeholder.container():progress_view(ROOT,qid,progress=True)
                    outcome=native(ROOT,qid,'live' if live else 'model-preflight',arguments=args,progress=progress)
                st.session_state['bot-active-id']=qid
                st.success('Stage recorded. Inspect its saved outcome; no next stage was started.')
                st.json(outcome)
                if not live:
                    prepare_next(ROOT,qid)
                st.rerun()
            except (ArtifactError,ValueError,KeyError,TypeError,OSError):
                st.error('This stage was blocked or could not complete. Inspect saved execution status. No automatic retry or next stage was started.')
        with st.expander('Technical Details — exact displayed preparation'):
            st.json({'manifest':value['manifest'],'sha256':value['sha256'],'question_id':qid})
