"""Read sealed provider qualification observations without invoking any service."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store

from .store import verify_reference


def discover(root):
    output={};rejected=[]
    for path in sorted((Path(root)/'data/runtime-qualifications/v1').glob('qualification-*/MANIFEST.json')):
        try:
            store=Store(root);name=path.relative_to(root).as_posix()
            m=store.manifest(name,schema='bot-model-qualification-1.0')
            base=name.rsplit('/',1)[0]
            start=store.json(base+'/START.json');row=store.json(base+'/RESULT.json');audit=store.json(base+'/MODEL_PREFLIGHT.json')
            qid=row['question_id'];ctx=start['context']
            if row['status']=='MODEL_QUALIFIED':
                from tools.generation_runner.bot_source import validate_qualification
                validate_qualification(root,name,store)
            verify_reference(root,qid,row['question_reference'])
            if (m['question_id']!=qid or ctx['question_id']!=qid or row.get('generation_executed') is not False
                    or row['provider_calls']>2 or start['mode']!='model-preflight'):
                raise ArtifactError('INVALID_BOT_QUALIFICATION')
            local=ctx['local_manifest'];store.manifest(local,schema='runtime-execution-1.0')
            local_base=local.rsplit('/',1)[0];previous=store.json(local_base+'/RESULT.json')
            if (store.verified[local]!=ctx['local_manifest_sha256'] or previous['M8_package_sha256']!=ctx['M8_package_sha256']
                    or previous['M7_result_sha256']!=ctx['M7_result_sha256']):
                raise ArtifactError('BOT_QUALIFICATION_SOURCE_CHANGED')
            value={'question_id':qid,'question_reference':row['question_reference'],'run_id':path.parent.name,
                'mode':'model-preflight','fixture_only':False,'execution_status':row['status'],
                'application_outcome':'MODEL_QUALIFIED_NOT_GENERATION_AUTHORIZED' if row['status']=='MODEL_QUALIFIED' else row['status'],
                'response':None,'model_status':None,'response_contract_status':'NOT_RUN','validation_status':'NOT_RUN',
                'provider_calls':row['provider_calls'],'generation_calls':0,'generation_executed':False,
                'cost_usd':None,'audit':audit,'created_at':m['created_at'],'manifest_path':name,
                'request_sha256':ctx['request_sha256'],'M8_package_sha256':ctx['M8_package_sha256'],
                'M7_result_sha256':ctx['M7_result_sha256'],'evidence_summary':previous.get('evidence_summary'),
                'artifacts':{'CANDIDATES.json':store.json(local_base+'/CANDIDATES.json'),
                    'RETRIEVAL_OBSERVATIONS.json':store.json(local_base+'/RETRIEVAL_OBSERVATIONS.json'),
                    'LOCAL_VALIDATION.json':store.json(local_base+'/LOCAL_VALIDATION.json'),
                    'PROVIDER_CALLS.json':store.json(base+'/PROVIDER_CALLS.json')}}
            output.setdefault(qid,[]).append(value)
        except (ArtifactError,ValueError,TypeError,KeyError,OSError):
            rejected.append({'manifest':path.name,'status':'INVALID_BOT_QUALIFICATION'})
    return output,rejected
