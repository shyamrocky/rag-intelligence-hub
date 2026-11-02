"""Read-only native real-answer projection for Bot IDs; no benchmark expansion."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store, digest

from .store import reference


def records(root, questions):
    from tools.quality_dashboard.attempts import merge_native
    store=Store(root); rejected=[]
    values={qid:{'question_id':qid,'question_source':'BOT','question':r['question'],
        'reference':r['reference']|{'cohort_label':'Bot question — Unlabeled'},'group_ids':[],
        'attempts':[]} for qid,r in questions.items()}
    merge_native(root,values,store,rejected,include_unattempted=True)
    for qid,record in values.items():
        verified=[]
        for a in record['attempts']:
            row=a['row']
            try:
                if (row.get('question_source')!='BOT' or row.get('fixture_only')
                        or row.get('question_reference')!=reference(root,qid)):
                    raise ArtifactError('NATIVE_BOT_QUESTION_BINDING_CHANGED')
                store.bind(row['candidate_artifact'],row['candidate_artifact_sha256'])
                if store.json(row['candidate_artifact'])['query_sha256']!=row['question_sha256']:
                    raise ArtifactError('NATIVE_BOT_CANDIDATE_QUESTION_CHANGED')
                verified.append(a)
            except (ArtifactError,ValueError,TypeError,KeyError,OSError):
                rejected.append({'question_id':qid,'status':'INVALID_NATIVE_BOT_BINDING'})
        record['attempts']=verified
        record['latest_attempt']=verified[-1] if verified else None
        parsed=[a for a in verified if a['completed']]
        record['latest']=parsed[-1] if parsed else None
    return values,rejected


def operational(root, record, attempt):
    """Normalize execution dimensions without inventing model/semantic acceptance."""
    row=attempt['row'];audit=attempt['audit'];usage=attempt['usage']
    store=Store(root)
    store.bind(row['candidate_artifact'],row['candidate_artifact_sha256'])
    artifacts={'CANDIDATES.json':store.json(row['candidate_artifact'])}
    local_base=row['candidate_artifact'].rsplit('/',1)[0]
    store.manifest(local_base+'/MANIFEST.json',schema='runtime-execution-1.0')
    previous=store.json(local_base+'/RESULT.json')
    if previous['M8_package_sha256']!=row['M8_package_sha256']:
        raise ArtifactError('NATIVE_BOT_LOCAL_EVIDENCE_CHANGED')
    artifacts['RETRIEVAL_OBSERVATIONS.json']=store.json(local_base+'/RETRIEVAL_OBSERVATIONS.json')
    run_base=attempt['source']['result_path'].rsplit('/',1)[0]
    native_store=attempt['run']['store'] if 'store' in attempt['run'] else Store(root)
    native_store.manifest(attempt['source']['manifest_path'])
    local_audit=run_base+'/LOCAL_VALIDATION.json'
    if local_audit in native_store.verified:
        artifacts['LOCAL_VALIDATION.json']=native_store.json(local_audit)
    from tools.human_review import local_poc
    from tools.human_review.review_state import current_decision
    decisions,bad=local_poc.discover(root,question_id=row['question_id'])
    target={'question_id':row['question_id'],'policy':attempt['review_policy'],'bindings':{
        'question_sha256':row['question_sha256'],'response_sha256':digest(row.get('response')),
        'request_sha256':row['request_sha256'],'package_sha256':row['M8_package_sha256']}}
    decision=current_decision(target,decisions)
    owner_status='UNVERIFIED_REVIEW_HISTORY' if bad else decision[0]['status'] if decision else 'PENDING_REVIEW'
    return row|{'owner_review_status':owner_status,'evidence_summary':previous.get('evidence_summary'), 'run_id':attempt['run']['manifest']['run_id'],'mode':'live',
        'native_attempt':attempt,'native_record':record,
        'execution_status':'COMPLETED' if attempt['completed'] else 'FAILED' if row.get('generation_attempted') or row.get('generation_executed') else 'BLOCKED',
        'response_contract_status':'ACCEPTED' if attempt['completed'] else 'REJECTED' if row.get('generation_attempted') or row.get('generation_executed') else 'NOT_RUN',
        'model_status':row['response']['status'] if row.get('response') else None,
        'validation_status':(row.get('post_validation') or {}).get('overall_status','NOT_RUN'),
        'manifest_path':attempt['source']['manifest_path'],
        'raw_capture':audit.get('raw_response_capture'),
        'cost_usd':usage.get('total_estimated_cost_usd'), 'usage':usage,
        'timings':attempt['run'].get('timings',{}).get(row['question_id']),
        'created_at':attempt['timestamp_or_version'],'artifacts':artifacts,'audit':audit}


def review(st,root,record,attempt):
    """Reuse the actual local/signed workflow; no auto preparation on refresh."""
    if not attempt['completed']:
        from tools.human_review.observation_review import render
        render(st,root,attempt)
        return
    from tools.human_review.handoff import discover
    from tools.human_review.poc_ui import render
    entry=next((e for e in discover(root)['entries'] if e['source']==attempt['source']),None)
    if not entry:
        st.error('Source-bound review handoff unavailable. No approval inferred.')
        return
    render(st,root,selection={'record':record,'attempt':attempt,'normal_entry':entry})


def incomplete(root, questions, completed_run_ids):
    """Durable admission without a completion seal is visible, never replayed/read as output."""
    from tools.bot_runtime.store import verify_reference
    from tools.generation_runner.plan import BASE
    from tools.generation_runner.trust import context
    from tools.quality_dashboard.artifacts import read_json, safe_path
    values={};rejected=[]
    for path in sorted((Path(root)/BASE).glob('*/START.json')):
        if path.parent.name in completed_run_ids or (path.parent/'MANIFEST.json').exists():
            continue
        try:
            start=read_json(safe_path(root,path.relative_to(root).as_posix()))
            if start.get('mode')!='live':
                continue
            plan=read_json(safe_path(root,(path.parent/'PLAN.json').relative_to(root).as_posix()))
            if plan.get('question_source')!='BOT':
                continue
            ctx=context(plan)
            if len(plan['questions'])!=1:
                raise ArtifactError('INCOMPLETE_BOT_PLAN_SCOPE_INVALID')
            row=plan['questions'][0];qid=row['question_id']
            if qid not in questions:
                raise ArtifactError('INCOMPLETE_BOT_QUESTION_MISSING')
            verify_reference(root,qid,row['question_reference'])
            use=Path(root)/BASE/'authorization-use'/(start['authorization_sha256']+'.json')
            claim=read_json(safe_path(root,use.relative_to(root).as_posix()))
            if claim['run_id']!=path.parent.name or claim['question_ids']!=ctx['question_ids']:
                raise ArtifactError('INCOMPLETE_BOT_ADMISSION_UNBOUND')
            marker=path.parent/'questions'/qid/'GENERATION_HTTP_ATTEMPT.json'
            attempted=False
            if marker.exists():
                packet=read_json(safe_path(root,marker.relative_to(root).as_posix()))
                if packet['request_sha256']!=row['request_sha256']:
                    raise ArtifactError('INCOMPLETE_BOT_REQUEST_CHANGED')
                attempted=True
            values.setdefault(qid,[]).append(row|{'run_id':path.parent.name,'mode':'live','execution_status':'INCOMPLETE',
                'application_outcome':'RECOVERY_REQUIRED','created_at':start['created_at'],'response':None,
                'model_status':None,'response_contract_status':'NOT_VERIFIED','validation_status':'NOT_RUN',
                'provider_calls':None,'generation_attempted':attempted,'cost_usd':None,'owner_review_status':'NOT_ELIGIBLE',
                'diagnostics':['No completed result seal. Provider outcome/cost may be unknown. No automatic retry.'],
                'artifacts':{}})
        except (ArtifactError,ValueError,KeyError,TypeError,OSError):
            rejected.append({'run_id':path.parent.name,'status':'UNVERIFIED_INCOMPLETE_BOT_RUN'})
    return values,rejected
