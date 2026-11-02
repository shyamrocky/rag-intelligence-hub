"""Read-only trace discovery. Unsealed progress never becomes a completed result."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store

from .store import read, reference
from .trace import events


def discover(root,qid,*,progress=False):
    root=Path(root);qref=reference(root,qid);rows=[];rejected=[]
    paths=list((root/'data/runtime-executions/v1').glob('bot-*/REQUEST_TRACE'))
    paths+=list((root/'data/runtime-qualifications/v1').glob('qualification-*/REQUEST_TRACE'))
    paths+=list((root/'data/evals/generation-runner').glob('*/questions/'+qid+'/REQUEST_TRACE'))
    paths+=list((root/'workspace/bot-dispatch-traces').glob('dispatch-*/REQUEST_TRACE'))
    for folder in paths:
        try:
            first=read(folder/'000000.json')
            if first.get('question_id')!=qid:continue
            driver=folder.is_relative_to(root/'workspace/bot-dispatch-traces')
            native=folder.is_relative_to(root/'data/evals/generation-runner')
            run=folder.parents[2] if native else folder.parent
            manifest=run/'MANIFEST.json'
            sealed=(folder/'SEAL.json').exists()
            verified=False
            if not progress and sealed and not driver:
                store=Store(root);store.manifest(manifest.relative_to(root).as_posix())
                for p in folder.iterdir():
                    store.bind(p.relative_to(root).as_posix(),store.verified[p.relative_to(root).as_posix()])
                verified=True
            values=events(folder,question_id=qid,run_id=run.name,question_reference=qref,sealed=sealed)
            rows.append({'folder':folder.relative_to(root).as_posix(),'mode':first['mode'],
                         'run_id':run.name,'events':values,'execution_seal_verified':verified,
                         'observation':'SEALED_DIAGNOSTIC_ONLY' if driver and sealed else 'EXECUTION_SEAL_VERIFIED'
                            if verified else 'UNSEALED_PROGRESS_NOT_COMPLETION_AUTHORITY'})
        except (ArtifactError,OSError,ValueError,TypeError,KeyError):
            rejected.append({'trace':folder.relative_to(root).as_posix(),'status':'TRACE_UNAVAILABLE_OR_UNVERIFIED'})
    rows.sort(key=lambda r:(r['events'][0]['timestamp'],r['run_id']))
    return {'traces':rows,'rejected':rejected}


LABELS={'QUESTION_RECEIVED':'Question received','LIVE_RETRIEVAL':'Candidate retrieval and ranking',
 'SAVED_INPUT_VERIFICATION':'Saved retrieval input verification','SEARCH_WORKER':'Search worker',
 'SERVICE_BINDING_CHECK':'Source and service initialization','M8_EVIDENCE_ASSEMBLY':'Evidence reconstruction and assembly',
 'M8_SOURCE_VALIDATION':'Evidence source validation','PROMPT_ASSEMBLY':'Prompt preparation',
 'MODEL_PREFLIGHT':'Model qualification','MODEL_METADATA':'Model access check','MODEL_TOKEN_COUNT':'Exact model-token count',
 'LLM_GENERATION':'Generation request','POST_GENERATION_VALIDATION':'Technical validation',
 'OWNER_AUTHORIZATION':'Owner consent verification','ARTIFACT_PERSISTENCE':'Save execution artifacts',
 'FINAL_SOURCE_CHECK':'Final source check','REQUEST_BINDING_AND_POLICY':'Request and policy verification',
 'GENERATION_SERVICE_OVERHEAD':'Generation service','BACKEND_DISPATCH':'Backend stage dispatch',
 'NEXT_STAGE_READINESS':'Next approval readiness','EXECUTION_RESULT':'Execution outcome',
 'RETRIEVAL_COUNTS':'Retrieval counts','EVIDENCE_COUNTS':'Evidence counts'}
LABELS['PROMPT_GATE']='Local prompt gate decision'


def table(trace):
    latest={}
    for event in trace['events']:
        key=(event['stage'],event['operation'])
        latest[key]=event
    rows=[]
    for (stage,operation),event in latest.items():
        label=LABELS.get(stage,'Additional recorded operation')
        if stage=='SEARCH_WORKER':
            worker=operation.split(' ',1)[0]
            if worker in {'encode','vector','bm25'}:label+=' · '+worker
        rows.append({'Stage':label,'Status':event['status'].replace('_',' ').title(),
            'Seconds':None if event.get('duration_ms') is None else round(event['duration_ms']/1000,3)})
    observed={stage for stage,_ in latest}
    for stage in ['M8_EVIDENCE_ASSEMBLY','PROMPT_ASSEMBLY','MODEL_TOKEN_COUNT','LLM_GENERATION','POST_GENERATION_VALIDATION']:
        if stage not in observed:
            rows.append({'Stage':LABELS[stage],'Status':'Not started / not measured','Seconds':None})
    return rows
