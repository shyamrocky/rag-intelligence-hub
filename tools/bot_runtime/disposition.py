"""Owner bookkeeping for a failed local submission, never an execution permission."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store, sha

from .store import directory, locked, now, reference, seal, write

BASE='data/runtime-dispositions/v1'
SCHEMA='bot-question-disposition-1.0'


def target(root,qid,manifest):
    qref=reference(root,qid);store=Store(root)
    if not manifest.startswith('data/runtime-executions/v1/bot-'):
        raise ArtifactError('LOCAL_EXECUTION_DISPOSITION_REQUIRED')
    m=store.manifest(manifest,schema='runtime-execution-1.0')
    row=store.json(manifest.rsplit('/',1)[0]+'/RESULT.json')
    if (m['question_id']!=qid or row['question_id']!=qid or row['question_reference']!=qref
            or m['mode']!='local-check' or row['mode']!='local-check'
            or row['execution_status'] not in {'FAILED','BLOCKED'}
            or row['provider_calls']!=0 or row['generation_executed'] is not False):
        raise ArtifactError('FAILED_LOCAL_PREPARATION_REQUIRED')
    return {'manifest':manifest,'sha256':sha(Path(root)/manifest),'question_reference':qref,
            'run_id':m['run_id'],'original_execution_status':row['execution_status']}


def discard(root,qid,manifest,*,owner_statement,reason):
    if not isinstance(owner_statement,str) or not owner_statement.strip() or not isinstance(reason,str) or not reason.strip():
        raise ArtifactError('EXPLICIT_OWNER_DISPOSITION_REQUIRED')
    bound=target(root,qid,manifest)
    base=directory(root,BASE)
    with locked(base):
        folder=base/qid
        if folder.exists():raise ArtifactError('DISPOSITION_ALREADY_RECORDED')
        folder.mkdir(mode=0o700)
        value={'schema':SCHEMA,'question_id':qid,'status':'DISCARDED','created_at':now(),
               'target':bound,'owner_statement':owner_statement.strip(),'reason':reason.strip(),
               'authority':'EXPLICIT_LOCAL_OWNER_INSTRUCTION_NOT_CRYPTOGRAPHIC_ATTESTATION',
               'generation_authority':False,'evaluation_acceptance':False}
        write(folder/'DISPOSITION.json',value)
        seal(folder,SCHEMA,question_id=qid,generation_authority=False)
        return folder/'MANIFEST.json'


def read(root,qid):
    reference(root,qid)
    path=Path(root)/BASE/qid/'MANIFEST.json'
    if not path.parent.exists():return None
    store=Store(root);m=store.manifest(path.relative_to(root).as_posix(),schema=SCHEMA)
    value=store.json((path.parent/'DISPOSITION.json').relative_to(root).as_posix())
    if (m.get('question_id')!=qid or set(m['files'])!={'DISPOSITION.json'}
            or value.get('schema')!=SCHEMA or value.get('question_id')!=qid or value.get('status')!='DISCARDED'
            or value.get('generation_authority') is not False or value.get('evaluation_acceptance') is not False
            or value.get('authority')!='EXPLICIT_LOCAL_OWNER_INSTRUCTION_NOT_CRYPTOGRAPHIC_ATTESTATION'
            or not isinstance(value.get('owner_statement'),str) or not value['owner_statement'].strip()
            or not isinstance(value.get('reason'),str) or not value['reason'].strip()
            or value.get('target')!=target(root,qid,value['target']['manifest'])):
        raise ArtifactError('DISPOSITION_BINDING_CHANGED')
    return value|{'manifest':path.relative_to(root).as_posix(),'manifest_sha256':sha(path)}
