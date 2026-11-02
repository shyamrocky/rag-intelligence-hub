"""Owned offline HTTP bodies only; no credentials, corpus or provider access."""
import copy
import json
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from tools.generation.current import GenerationService, load_settings, resolve
from tools.generation.diagnostics import ResponseValidationError
from tools.generation.openai_adapter import OpenAIAdapter, ProviderError
from tools.generation.response_capture import ResponseCapture, verify_capture
from tools.generation.service import parse_response
from tools.generation.telemetry import load_pricing
from tools.generation.tests.test_adapter import request, sdk_fixture, sdk_response
from tools.pre_generation_gate.response_v2 import synthetic_example
from tools.quality_dashboard.artifacts import ArtifactError


def sink(tmp_path, qid='OWNED-Q', run='owned-run'):
    return ResponseCapture(tmp_path, tmp_path / 'data/evals/generation-runner' / run / 'questions' / qid,
        question_id=qid, run_id=run, request_sha256='a'*64, package_sha256='b'*64, mode='MOCK')


def row(qid='OWNED-Q'):
    return {'question_id': qid, 'request_sha256': 'a'*64, 'M8_package_sha256': 'b'*64, 'mode': 'mock'}


def engine(tmp_path, body, *, status=200, capture=None):
    calls = []
    def handler(req):
        calls.append((req.url.path, req.content))
        if '/models/' in req.url.path:
            return httpx.Response(200, json={'id':'gpt-6-luna','created':0,'object':'model','owned_by':'owned'})
        if req.url.path.endswith('/input_tokens'):
            return httpx.Response(200, json={'input_tokens':100,'object':'response.input_tokens'})
        return httpx.Response(status, content=body, headers={'content-type':'application/json'})
    adapter = OpenAIAdapter(client=sdk_fixture(handler), capture_sink=capture or sink(tmp_path))
    service = GenerationService.__new__(GenerationService)
    service.adapter, service.settings = adapter, load_settings()
    service.pricing, service.as_of = load_pricing(), date(2026,10,30)
    service.gate = SimpleNamespace(validate_preparation=lambda *a: None)
    wire, profile = request(), resolve(service.settings, as_of=service.as_of)
    prepared = SimpleNamespace(audit={'request_sha256':'c'*64})
    service._request = lambda *a: (prepared, profile, wire)
    service.assess_response = lambda *a: {'status':'QUALIFICATIONS_VALID'}
    return service, adapter, calls, prepared


def generate(service, prepared):
    return service.generate(prepared, 'Owned?', {'parents': []}, {},
                            allow_paid_inference=True, allow_source_transfer=True)


@pytest.mark.parametrize('body', [b'not-json', b'{"outer":', b'{"output":[]}'])
def test_bytes_saved_before_outer_json_and_usage(tmp_path, body):
    service, adapter, calls, prepared = engine(tmp_path, body)
    outcome = generate(service, prepared)
    path = verify_capture(tmp_path, adapter.last_capture, row(), run_id='owned-run')
    assert path.read_bytes() == body
    assert outcome.response is None
    assert len(calls) == 3
    assert outcome.audit['raw_response_capture']['status'] == 'RAW_RESPONSE_CAPTURED'


@pytest.mark.parametrize('kind,code', [
    ('inner-json','MALFORMED_RESPONSE_JSON'), ('duplicate','DUPLICATE_RESPONSE_JSON_KEY'),
    ('schema','SCHEMA_OR_RELATIONSHIP_INVALID'), ('relationship','SCHEMA_OR_RELATIONSHIP_INVALID'),
    ('unauthorized','UNAUTHORIZED_EVIDENCE_REFERENCE'), ('model','RESPONSE_MODEL_MISMATCH'),
    ('refusal','REFUSAL_OR_UNSUPPORTED_RESPONSE_CONTENT'), ('incomplete','PROVIDER_RESPONSE_NOT_COMPLETED'),
])
def test_precise_rejection_retains_body_and_usage(tmp_path, kind, code):
    raw = sdk_response()
    if kind == 'inner-json': raw['output'][0]['content'][0]['text'] = 'SECRET-PASSAGE not json'
    if kind == 'duplicate': raw['output'][0]['content'][0]['text'] = '{"status":"ABSTAINED","status":"ANSWERED"}'
    if kind == 'schema': raw['output'][0]['content'][0]['text'] = json.dumps({'answer':'SECRET-PASSAGE'})
    if kind == 'relationship':
        answer=json.loads(raw['output'][0]['content'][0]['text']); answer['answer']='SECRET-PASSAGE'
        raw['output'][0]['content'][0]['text']=json.dumps(answer)
    if kind == 'unauthorized': raw['output'][0]['content'][0]['text']=json.dumps(synthetic_example())
    if kind == 'model': raw['model']='owned-wrong-model'
    if kind == 'refusal': raw['output'][0]['content']=[{'type':'refusal','refusal':'SECRET-PASSAGE'}]
    if kind == 'incomplete': raw['status']='incomplete'
    body=json.dumps(raw).encode()
    service,adapter,calls,prepared=engine(tmp_path,body)
    value=generate(service,prepared)
    assert value.response is None and value.audit['status']=='INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE'
    assert code in {i['code'] for i in value.audit['response_diagnostics']}
    assert 'SECRET-PASSAGE' not in json.dumps(value.audit)
    assert value.audit['usage']['input_tokens']==raw['usage']['input_tokens']
    path=verify_capture(tmp_path,adapter.last_capture,row(),run_id='owned-run')
    assert path.read_bytes()==body and len(calls)==3
    if kind=='unauthorized':
        assert any(i['path']==['claims',0,'evidence_unit_ids',0] for i in value.audit['response_diagnostics'])


def test_success_keeps_both_original_body_and_structured_answer(tmp_path):
    raw=sdk_response(); body=json.dumps(raw,indent=3).encode()
    service,adapter,calls,prepared=engine(tmp_path,body)
    result=generate(service,prepared)
    assert result.response['status']=='ABSTAINED'
    assert result.audit['raw_response_capture']['status']=='RAW_RESPONSE_CAPTURED'
    assert verify_capture(tmp_path,adapter.last_capture,row(),run_id='owned-run').read_bytes()==body
    assert not result.audit['fully_validated'] and len(calls)==3
    assert json.loads(calls[-1][1])==request()
    with pytest.raises(ProviderError, match='ALREADY_ATTEMPTED'):
        adapter.invoke(request())
    assert len(calls)==3


def test_capture_failure_stops_and_preserves_measured_usage(tmp_path,monkeypatch):
    from tools.generation import response_capture
    cap=sink(tmp_path)
    def fail(*a): raise OSError('PRIVATE-PATH-OR-PASSAGE')
    monkeypatch.setattr(response_capture,'_write',fail)
    service,_adapter,calls,prepared=engine(tmp_path,json.dumps(sdk_response()).encode(),capture=cap)
    result=generate(service,prepared)
    assert result.audit['status']=='RAW_RESPONSE_CAPTURE_FAILED' and result.response is None
    assert result.audit['usage']['cost_status']=='ESTIMATED_API_COST'
    assert result.audit['raw_response_capture']['artifact'] is None
    assert len(calls)==3 and 'PRIVATE-PATH' not in json.dumps(result.audit)


@pytest.mark.parametrize('status',[401,429,500])
def test_provider_error_capture_is_honest_and_no_retry(tmp_path,status):
    body=b'{"error":{"message":"owned failure","type":"owned","code":"owned"}}'
    service,_adapter,calls,prepared=engine(tmp_path,body,status=status)
    result=generate(service,prepared)
    assert result.response is None and len(calls)==3
    assert result.audit['usage']['cost_status']=='COST_UNAVAILABLE'
    ref=result.audit['raw_response_capture']
    if status==401:
        assert ref['status']=='RAW_RESPONSE_UNAVAILABLE' and ref['artifact'] is None
    else:
        assert verify_capture(tmp_path,ref,row(),run_id='owned-run').read_bytes()==body


@pytest.mark.parametrize('change',['body','permissions','binding','path','symlink'])
def test_capture_tampering_and_privacy_fail_closed(tmp_path,change):
    cap=sink(tmp_path); ref=cap.capture(b'{"owned":"body"}',http_status=200)
    path=verify_capture(tmp_path,ref,row(),run_id='owned-run')
    ref=copy.deepcopy(ref)
    if change=='body':path.write_bytes(b'changed')
    if change=='permissions':path.chmod(0o644)
    if change=='binding':ref['context']['request_sha256']='c'*64
    if change=='path':ref['artifact']['path']='workspace/../.env'
    if change=='symlink':
        original=path.read_bytes();path.unlink(); target=tmp_path/'elsewhere';target.write_bytes(original);path.symlink_to(target)
    with pytest.raises((ArtifactError,ValueError)):
        verify_capture(tmp_path,ref,row(),run_id='owned-run')


def test_no_response_and_immutable_capture(tmp_path):
    cap=sink(tmp_path); ref=cap.capture(None,unavailable_reason='NO_PROVIDER_RESPONSE_RECEIVED')
    assert verify_capture(tmp_path,ref,row(),run_id='owned-run') is None
    with pytest.raises(ArtifactError,match='ALREADY_ATTEMPTED'):
        cap.capture(b'new')


@pytest.mark.parametrize('raw,path', [({'status':'completed','output':None},['output']),
    ({'status':'completed','output':[None]},['output',0]),
    ({'status':'completed','output':[{'type':'message','content':None}]},['output',0,'content'])])
def test_malformed_envelope_field_paths(raw,path):
    with pytest.raises(ResponseValidationError) as info:parse_response(raw,set())
    assert info.value.diagnostics[0]['path']==path


def test_timeout_records_absence_without_retry(tmp_path):
    cap=sink(tmp_path);calls=[]
    def handler(req):
        calls.append(req.url.path)
        raise httpx.ReadTimeout('Owned timeout',request=req)
    adapter=OpenAIAdapter(client=sdk_fixture(handler),capture_sink=cap)
    with pytest.raises(ProviderError,match='PROVIDER_TIMEOUT') as info:adapter.invoke(request())
    assert len(calls)==1
    assert info.value.capture['status']=='RAW_RESPONSE_UNAVAILABLE'
    assert info.value.capture['artifact'] is None


def test_usage_decode_failure_still_retains_original_body(tmp_path,monkeypatch):
    body=json.dumps(sdk_response()).encode()
    _,adapter,calls,_=engine(tmp_path,body)
    def fail(*a):raise ValueError('PRIVATE-PUBLISHER-TEXT')
    monkeypatch.setattr('tools.generation.openai_adapter.capture_usage',fail)
    with pytest.raises(ProviderError) as info:adapter.invoke(request())
    assert 'PRIVATE-PUBLISHER-TEXT' not in str(info.value)
    assert verify_capture(tmp_path,info.value.capture,row(),run_id='owned-run').read_bytes()==body
    assert len(calls)==1
