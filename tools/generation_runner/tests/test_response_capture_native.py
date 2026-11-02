"""Native admission/sealing with disposable synthetic authorization and response boundaries."""
import json
from types import SimpleNamespace

import pytest
from test_stage_policies import fake_pipeline, run_synthetic, synthetic_approval
from test_stage_policies import owned as owned  # noqa: PLC0414
from test_stage_policies import stages as stages  # noqa: PLC0414


@pytest.mark.parametrize('capture_failure',[False,True])
def test_native_rejection_seals_diagnostic_and_stops_without_next_question(stages,monkeypatch,capture_failure):
    from tools.generation.response_capture import ResponseCapture, verify_capture
    from tools.generation.service import parse_response
    from tools.generation.tests.test_adapter import sdk_response
    from tools.generation_runner import live
    from tools.generation_runner.dashboard import discover
    from tools.pre_generation_gate.contract import digest
    s=stages['pilot']
    path,h=synthetic_approval(s,'owned-capture-test')
    fake_pipeline(monkeypatch,s)
    calls=[]
    def denied(*a,**kw):raise AssertionError('OFFLINE_NATIVE_CONTROL_NO_NETWORK_OR_KEYS')
    monkeypatch.setattr('socket.create_connection',denied)
    monkeypatch.setattr('tools.preflight_suite.provider.load_key',denied)
    if capture_failure:
        from tools.generation import response_capture
        original=response_capture._write
        def write(p,body):
            if p.name=='RAW_RESPONSE.body':raise OSError('Owned storage failure')
            return original(p,body)
        monkeypatch.setattr(response_capture,'_write',write)
    class Adapter:
        def __init__(self,capture):self.capture=capture
        def verify_model(self):pass
        def count(self):pass
        def invoke(self):
            calls.append('OWNED_SYNTHETIC_RESPONSE')
            body=json.dumps(sdk_response() | {'output':[{'type':'message','content':[{'type':'output_text','text':'not-json'}]}]}).encode()
            return self.capture.capture(body,http_status=200),json.loads(body)
    def create(root,qdir,request,row,budget,*a,trust_guard,**kw):
        trust_guard()
        capture=ResponseCapture(root,qdir,question_id=row['question_id'],run_id=qdir.parent.parent.name,
            request_sha256=row['request_sha256'],package_sha256=row['M8_package_sha256'],mode='live')
        return Adapter(capture),None,None
    class Service:
        def __init__(self,gate,adapter,**kw):self.adapter=adapter
        def dry_run(self):pass
        def generate(self,*a,**kw):
            capture,raw=self.adapter.invoke()
            diagnostics=[]
            if capture['status']=='RAW_RESPONSE_CAPTURED':
                with pytest.raises(ValueError) as info:parse_response(raw,set())
                diagnostics=info.value.diagnostics
            return SimpleNamespace(response=None,audit={'status':'RAW_RESPONSE_CAPTURE_FAILED'
                if capture_failure else 'INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE','generation_executed':True,
                'response_sha256':digest(raw),'raw_response_capture':capture,'response_diagnostics':diagnostics,
                'usage':{'cost_status':'ESTIMATED_API_COST','input_tokens':100,'output_tokens':10,
                         'total_estimated_cost_usd':'0.001'}})
    monkeypatch.setattr(live,'create',create)
    monkeypatch.setattr('tools.generation.current.GenerationService',Service)
    run=run_synthetic(s,path,h)
    values=json.loads((run/'RESULTS.json').read_bytes())
    assert values['selected']==4 and values['completed']==1 and len(calls)==1
    record=values['questions'][0]
    receipt=record['audit']['raw_response_capture']
    telemetry=next(r for r in discover(s.root)['runs'] if r['manifest']['run_id']==run.name)
    if capture_failure:
        assert receipt['artifact'] is None and record['status']=='RAW_RESPONSE_CAPTURE_FAILED'
    else:
        assert f"questions/{record['question_id']}/RAW_RESPONSE_CAPTURE.json" in telemetry['manifest']['files']
        assert verify_capture(s.root,receipt,record,run_id=run.name).is_file()
    assert not record['response'] and record['post_validation']['status']=='NOT_RUN_NO_VALID_RESPONSE'
    assert not list(s.root.rglob('LIVE_ATTEMPT.json'))
