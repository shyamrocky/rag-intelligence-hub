"""Request observations only: owned fixtures, no source search/provider activity."""
import json
import subprocess
from uuid import uuid4

import pytest

pytest.importorskip('tools')

from tools.bot_runtime import dispatch, store, trace, trace_read
from tools.generation_runner import bot_runtime
from tools.quality_dashboard.artifacts import ArtifactError


def question(root):
    return store.register(root,'Explain this owned trace fixture.',uuid4().hex)


def observed(root):
    q=question(root);run=store.directory(root,'data/runtime-executions/v1/bot-owned')
    value=trace.RequestTrace(root,run,question_id=q['question_id'],run_id=run.name,mode='local-check',question_reference=store.reference(root,q['question_id']))
    return q,run,value


def test_failure_records_safe_code_and_frames_without_locals(tmp_path):
    q,run,value=observed(tmp_path)
    with pytest.raises(ValueError),value.span('LIVE_RETRIEVAL',operation='encode worker'):
        raise ValueError('m7_worker_failure_no_fallback:ValueError:m7_forged_query_binding')
    ref=value.finish('FAILED');assert ref['status']=='SEALED'
    rows=trace.events(run/'REQUEST_TRACE',question_id=q['question_id'],run_id=run.name,question_reference=store.reference(tmp_path,q['question_id']))
    error=next(x['detail'] for x in rows if x['status']=='FAILED')
    assert error['error_code'].endswith('m7_forged_query_binding')
    assert error['frames'] and all(set(f)=={'file','function','line'} for f in error['frames'])


@pytest.mark.parametrize('message',['Bearer secret-test-value','api_key=owner-secret','sk-proj-secret-test-value','arbitrary publisher passage and private data'])
def test_untrusted_error_text_or_credentials_never_enter_trace(tmp_path,message):
    _q,run,value=observed(tmp_path)
    try:raise ValueError(message)
    except ValueError as error:value.error('LLM_GENERATION',error)
    value.finish('FAILED')
    body=''.join(p.read_text() for p in (run/'REQUEST_TRACE').glob('*.json'))
    assert message not in body and 'UNTRUSTED_TEXT_OMITTED' in body


def test_observation_preserves_call_arguments_result_and_count(tmp_path):
    _,_,value=observed(tmp_path);calls=[]
    class Service:
        def action(self,*args,**kwargs):calls.append((args,kwargs));return object_result
    service=Service();object_result=object()
    with value.observe(service,'action','MODEL_TOKEN_COUNT'):
        assert service.action('owned',x=1) is object_result
    assert calls==[(('owned',),{'x':1})] and 'action' not in vars(service)


@pytest.mark.parametrize('part',['event','manifest','identity','inventory'])
def test_changed_or_missing_trace_fails_closed(tmp_path,part):
    q,run,value=observed(tmp_path);value.finish('COMPLETED');folder=run/'REQUEST_TRACE'
    if part=='event':(folder/'000000.json').write_text('{}')
    elif part=='manifest':(folder/'SEAL.json').unlink()
    elif part=='identity':q['question_id']='BOT-999999'
    else:store.write(folder/'000002.json',{})
    with pytest.raises((ArtifactError,OSError,KeyError)):
        trace.events(folder,question_id=q['question_id'],run_id=run.name,question_reference=store.reference(tmp_path,'BOT-000001'))


def test_progress_is_not_completion_authority(tmp_path):
    q,run,value=observed(tmp_path);value.emit('LIVE_RETRIEVAL','RUNNING')
    result=trace_read.discover(tmp_path,q['question_id'],progress=True)
    assert not result['rejected'] and len(result['traces'])==1
    assert result['traces'][0]['execution_seal_verified'] is False
    assert result['traces'][0]['observation']=='UNSEALED_PROGRESS_NOT_COMPLETION_AUTHORITY'
    assert not (run/'MANIFEST.json').exists()


def test_trace_write_failure_does_not_change_mock_result(tmp_path,monkeypatch):
    pytest.importorskip('httpx')
    q=question(tmp_path)
    monkeypatch.setattr('tools.bot_runtime.trust.verify_implementation',lambda root:{'path':'OWNED','sha256':'a'*64,'generation_authority':False})
    def failed(*a,**kw):raise OSError('Owned logging write failure')
    monkeypatch.setattr(trace,'write',failed)
    run=bot_runtime.execute(tmp_path,q['question_id'],mode='mock')
    assert store.read(run/'RESULT.json')['execution_status']=='COMPLETED'
    assert store.load(run,'runtime-execution-1.0')
    assert not list((run/'REQUEST_TRACE').glob('*.json'))


def test_partial_logging_write_stays_outside_execution_seal(tmp_path,monkeypatch):
    _,run,value=observed(tmp_path)
    def partial(file,body):
        file.write_text('{');raise OSError('Owned partial disk write')
    monkeypatch.setattr(trace,'write',partial)
    with value.span('LIVE_RETRIEVAL'):pass
    assert value.finish('COMPLETED')=={'status':'TRACE_CAPTURE_FAILED','artifact':None}
    assert all(json.loads(p.read_text()) for p in (run/'REQUEST_TRACE').glob('*.json'))
    assert list((tmp_path/'workspace/bot-trace-spool').glob('*.json'))


def test_dispatch_progress_cannot_repeat_or_change_child_result(tmp_path,monkeypatch):
    q=question(tmp_path);callbacks=[];processes=[]
    class Process:
        def __init__(self,command,**kwargs):self.returncode=0;self.calls=0;processes.append(command)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def communicate(self,timeout):
            self.calls+=1
            if self.calls==1:raise subprocess.TimeoutExpired('owned',timeout)
            return json.dumps({'question_id':q['question_id'],'mode':'local-check'}),''
    monkeypatch.setattr(dispatch.subprocess,'Popen',Process)
    def broken_progress():callbacks.append(True);raise ValueError('Display-only failure')
    result=dispatch.native(tmp_path,q['question_id'],'local-check',arguments=[],progress=broken_progress)
    assert result['mode']=='local-check' and len(processes)==1 and callbacks==[True]
    assert not trace_read.discover(tmp_path,q['question_id'])['rejected']


def test_historical_trace_absence_is_not_fabricated(tmp_path):
    q=question(tmp_path)
    assert trace_read.discover(tmp_path,q['question_id'])=={'traces':[],'rejected':[]}


def test_trace_ui_requires_localhost_for_failure_locations(tmp_path,monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import request_trace
    q,run,value=observed(tmp_path)
    with pytest.raises(ValueError),value.span('LIVE_RETRIEVAL'):
        raise ValueError('m7_worker_failure_no_fallback:ValueError:m7_forged_query_binding')
    value.finish('FAILED');store.seal(run,'runtime-execution-1.0')
    monkeypatch.setattr(request_trace,'discover',lambda root,qid,**kw:trace_read.discover(tmp_path,q['question_id'],**kw))
    app=AppTest.from_string('from apps.knowledge_preparation.request_trace import render\nrender(__import__("pathlib").Path("."),"BOT-000001")').run()
    assert not app.exception and any('m7_forged_query_binding' in e.value for e in app.error)
    assert not any('"frames"' in j.value for j in app.json)
    def denied():raise ValueError('NOT_LOCALHOST')
    monkeypatch.setattr('tools.human_review.local_poc.require_localhost',denied)
    app.checkbox[0].check().run()
    assert not app.exception and not any('"frames"' in j.value for j in app.json)
    assert any('require localhost' in e.value for e in app.error)


def test_trace_ui_refresh_is_read_only(tmp_path,monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import request_trace
    q,run,value=observed(tmp_path);value.finish('COMPLETED');store.seal(run,'runtime-execution-1.0')
    monkeypatch.setattr(request_trace,'discover',lambda root,qid,**kw:trace_read.discover(tmp_path,q['question_id'],**kw))
    before={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    app=AppTest.from_string('from apps.knowledge_preparation.request_trace import render\nrender(__import__("pathlib").Path("."),"BOT-000001")').run()
    app.run();assert not app.exception
    assert before=={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
