"""UI -> same native CLI in the existing generation environment. No shell/SDK/key."""
import json
import os
import subprocess
from pathlib import Path
from time import monotonic
from uuid import uuid4

from .store import ID


def simulate(root, qid, *, scenario='abstained'):
    if not ID.fullmatch(qid) or scenario not in {'abstained', 'answered', 'partial', 'schema-error', 'api-failure', 'empty-evidence'}:
        raise ValueError('INVALID_OFFLINE_DISPATCH')
    root = Path(root).resolve(strict=True)
    interpreter = root / 'tools/generation/.venv/bin/python'
    env = {k: v for k, v in os.environ.items() if not any(
        secret in k.upper() for secret in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL'))}
    env.update(PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
               TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='false', OTEL_SDK_DISABLED='true')
    result = subprocess.run([str(interpreter), '-m', 'tools.generation_runner', 'bot', 'mock',
        '--question-id', qid, '--scenario', scenario], cwd=root, env=env,
        capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        raise ValueError('OFFLINE_SIMULATION_BLOCKED_SEE_SAVED_EXECUTION_STATUS')
    value = json.loads(result.stdout)
    if value.get('question_id') != qid or value.get('mode') != 'mock':
        raise ValueError('INVALID_DISPATCH_RESULT')
    return value


def completed(root, qid):
    # Read-only polling is permissible; it cannot retry a consumed submission.
    from .projection import discover
    data = discover(root)
    record = data['records'].get(qid)
    return record['attempts'][-1] if record and record['attempts'] else None


def native(root, qid, mode, *, arguments, progress=None):
    """Explicit click only. CLI preserves all native consent/trust boundaries."""
    modes={'local-check','prepare-next','prepare-model-preflight','model-preflight','prepare-live','issue-preflight-consent','issue-live-consent','live','chat'}
    flags={'--local-manifest','--preflight-manifest','--trust-manifest','--trust-sha','--output',
        '--preflight-consent','--preflight-consent-sha','--owner-authorization','--authorization-sha',
        '--preparation-manifest','--preparation-sha','--per-question-cap','--aggregate-cap',
        '--owner-statement-file','--confirm-exact-request','--execute-approved-live'}
    if not ID.fullmatch(qid) or mode not in modes or not isinstance(arguments,list):
        raise ValueError('INVALID_NATIVE_BOT_DISPATCH')
    i=0
    while i<len(arguments):
        flag=arguments[i]
        if flag not in flags:
            raise ValueError('UNREVIEWED_BOT_DISPATCH_FLAG')
        i+=1
        if flag not in {'--confirm-exact-request','--execute-approved-live'}:
            if i>=len(arguments) or not isinstance(arguments[i],str) or arguments[i].startswith('--'):
                raise ValueError('INVALID_BOT_DISPATCH_VALUE')
            i+=1
    root=Path(root).resolve(strict=True)
    # No SDK/credential reads in Streamlit. The native runner loads credentials only
    # after verifying the owner consent and preservation gate in its own runtime.
    env=dict(os.environ,PYTHONPATH=str(root),PYTHONDONTWRITEBYTECODE='1')
    if mode in {'local-check','prepare-next','prepare-live','prepare-model-preflight'}:
        env={k:v for k,v in env.items() if not any(secret in k.upper() for secret in ('KEY','TOKEN','SECRET','PASSWORD','CREDENTIAL'))}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',ANONYMIZED_TELEMETRY='false',OTEL_SDK_DISABLED='true')
    from .store import reference
    from .trace import RequestTrace
    run_id='dispatch-'+uuid4().hex
    trace=RequestTrace(root,root/'workspace/bot-dispatch-traces'/run_id,
        question_id=qid,run_id=run_id,mode=mode,question_reference=reference(root,qid))
    status='FAILED'
    try:
        with trace.span('BACKEND_DISPATCH',operation=mode):
            command=[str(root/'tools/generation/.venv/bin/python'),'-m','tools.generation_runner',
                'bot',mode,'--question-id',qid,*arguments]
            if progress is None:
                result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=900,check=False)
            else:
                deadline=monotonic()+900
                with subprocess.Popen(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as process:
                    while True:
                        try:
                            stdout,stderr=process.communicate(timeout=max(.001,min(.5,deadline-monotonic())))
                            result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
                            break
                        except subprocess.TimeoutExpired:
                            if monotonic()>=deadline:
                                process.kill();process.communicate()
                                raise ValueError('BOT_BACKEND_TIMEOUT_NO_AUTOMATIC_RETRY') from None
                            try:progress()
                            except Exception as error:  # noqa: BLE001 - monitoring cannot alter execution
                                trace.error('PROGRESS_DISPLAY',error)
            if result.returncode:
                if mode == 'chat':
                    value = json.loads(result.stdout.splitlines()[-1])
                    from tools.generation_runner.bot_chat import MESSAGES
                    issue = value.get('finding', {})
                    if (value.get('question_id') == qid and value.get('mode') == mode
                            and issue.get('code') in MESSAGES):
                        trace.emit('CHAT_ADMISSION', 'BLOCKED', detail=issue)
                        from .store import directory, seal, write
                        folder = directory(root, 'data/runtime-chat/v1/blocks/' + qid + '/' + run_id)
                        write(folder / 'RESULT.json', {'question_id': qid, 'question_reference': reference(root, qid),
                            'status': 'BLOCKED', 'finding': issue, 'run_id': run_id})
                        seal(folder, 'bot-chat-admission-block-1.0')
                        status = 'BLOCKED'
                        return value
                raise ValueError('NATIVE_BOT_STAGE_BLOCKED_NO_AUTOMATIC_RETRY')
            # No stdout/stderr bodies, arguments, owner statement or credentials
            # enter this trace. Underlying accepted diagnostics retain their seals.
            value=json.loads(result.stdout.splitlines()[-1])
            if value.get('question_id')!=qid or value.get('mode')!=mode:
                raise ValueError('NATIVE_BOT_DISPATCH_IDENTITY_MISMATCH')
            if value.get('status'):
                trace.emit('NEXT_STAGE_READINESS','BLOCKED' if 'REQUIRED' in value['status'] or 'BLOCKED' in value['status'] else 'COMPLETED',
                           detail={'readiness':value['status']})
            status='COMPLETED'
            return value
    finally:
        trace.finish(status)
