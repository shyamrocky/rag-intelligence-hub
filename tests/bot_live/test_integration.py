"""Owned end-to-end Bot consent -> native runner -> existing owner review.

Every record/key/permission is in pytest's disposable root, with owned synthetic
source and provider boundaries. Real project questions and approvals are untouched.
"""
import copy
import json
import shutil
import socket
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip('tools')
pytest.importorskip('httpx')

from tools.bot_runtime import projection, store
from tools.generation_runner import (
    bot_consent,
    bot_preflight,
    bot_runtime,
    bot_source,
    runner,
    trust,
)
from tools.generation_runner.bot_fixture import answer, boundaries
from tools.generation_runner.tests.test_native_trust import owned as owned  # noqa: PLC0414
from tools.preflight_suite.artifacts import sha
from tools.quality_dashboard.artifacts import ArtifactError, digest

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*a,**kw):
        raise AssertionError('NO_REAL_NETWORK_OR_KEYS')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)
    monkeypatch.setattr('tools.preflight_suite.provider.load_key',denied)


def publish_policy(c,monkeypatch):
    base=(c.root/c.manifest).parent
    (base/'POLICY.json').write_text(json.dumps(c.policy))
    m=json.loads((base/'MANIFEST.json').read_text());m['files']['POLICY.json']=sha(base/'POLICY.json')
    (base/'MANIFEST.json').write_text(json.dumps(m))
    c.sha=sha(base/'MANIFEST.json')
    monkeypatch.setattr(trust,'TRUSTED_BASELINES',dict(trust.TRUSTED_BASELINES)|{c.manifest:c.sha})


@pytest.fixture
def bot(owned,monkeypatch):
    c=owned
    assert c.root!=ROOT
    for name in ['tools/human_review/POLICY.json','tools/human_review/local-poc-policy-1.0.json']:
        path=c.root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    monkeypatch.setattr('tools.bot_runtime.trust.verify_implementation',lambda root:{'path':c.manifest,'sha256':c.sha,'generation_authority':False})
    q=store.register(c.root,'Explain owned synthetic retrieval.',uuid4().hex)
    result,evidence=boundaries(q['question'],'answered');evidence.m7={}
    class Retrieval:
        def _request(self,*a): return {'result':[]}
        def search(self,*a,**kw):return result
        def check(self):pass
        def close(self):pass
    monkeypatch.setattr(bot_runtime,'local_services',lambda root:(Retrieval(),evidence))
    local=bot_runtime.execute(c.root,q['question_id'],mode='local-check')
    c.local=(local/'MANIFEST.json').relative_to(c.root).as_posix();c.q=q;c.result=result;c.evidence=evidence
    # Accepted-source boundary doubles ONLY in this disposable root.
    def init(self,*a,**kw):self.__dict__.update(evidence.__dict__)
    monkeypatch.setattr('tools.evidence.service.EvidenceService.__init__',init)
    monkeypatch.setattr('tools.evidence.contract.validate_candidates',lambda actual,*a:result['candidates'] if actual==result else (_ for _ in ()).throw(ValueError('SOURCE_CHANGED')))
    c.ctx,c.wire,c.config=bot_preflight.context(c.root,c.local)
    c.policy['bot_provider_preflight_allowlist']=[c.ctx]
    publish_policy(c,monkeypatch)
    return c


def preflight_approval(c):
    folder=bot_preflight.prepare(c.root,c.local,'workspace/bot-authorizations/count',trust_manifest=c.manifest,trust_sha=c.sha)
    path=bot_consent.issue(c.root,(folder/'MANIFEST.json').relative_to(c.root).as_posix(),sha(folder/'MANIFEST.json'),
        operation='model-preflight',owner_statement='SYNTHETIC TEST REVIEWER — COUNT ONLY',confirmed=True)
    return path.relative_to(c.root).as_posix(),sha(path)


def fake_count_provider(c,monkeypatch, *, fail=False):
    from tools.generation_runner.controls import OfflineAdapter
    calls=[]
    def factory(root,qdir,request,timeout):
        assert root!=ROOT
        receipts=[]
        row={'question_id':c.q['question_id'],'request_sha256':digest(request),'input_tokens':100}
        class CountAdapter(OfflineAdapter):
            def verify_model(self,model):
                if fail:raise ValueError('OWNED_METADATA_FAILURE')
                value=super().verify_model(model);calls.append('METADATA')
                receipts.append({'method':'GET','endpoint':'/v1/models/'+model})
                return value
            def count(self,request):
                value=super().count(request);calls.append('COUNT')
                receipts.append({'method':'POST','endpoint':'/v1/responses/input_tokens'})
                return value|{'method':'OPENAI_RESPONSES_INPUT_TOKENS',
                    'count_payload_sha256':digest({k:request[k] for k in ('model','input','text','reasoning','truncation')}),
                    'includes_messages_framing_and_response_schema':True}
            def invoke(self,*a):raise AssertionError('GENERATION_FORBIDDEN_DURING_PREFLIGHT')
        return CountAdapter(row,mode='mock',settings=c.config[0]),None,SimpleNamespace(receipts=receipts)
    monkeypatch.setattr('tools.preflight_suite.provider.adapter',factory)
    return calls


def qualified(c,monkeypatch):
    consent,h=preflight_approval(c)
    calls=fake_count_provider(c,monkeypatch)
    run=bot_preflight.execute(c.root,c.local,consent,h)
    assert store.read(run/'RESULT.json')['status']=='MODEL_QUALIFIED'
    assert calls==['METADATA','COUNT']
    c.qualification=(run/'MANIFEST.json').relative_to(c.root).as_posix()
    return c


def live_plan(c,monkeypatch):
    c.plan,_,_=bot_source.build_plan(c.root,selected=[c.q['question_id']],preflight=c.qualification,
        per_question_cap='0.03',aggregate_cap='0.03')
    ctx=trust.context(c.plan)
    contract=digest({k:v for k,v in c.plan.items() if k not in {'plan_sha256','created_for_date'}})
    old=(c.root/c.manifest).parent
    successor=c.root/'data/owned-live-trust';shutil.copytree(old,successor)
    c.manifest=(successor/'MANIFEST.json').relative_to(c.root).as_posix()
    c.policy.update(permitted_question_ids=ctx['question_ids'],model=c.plan['model'],prompt_version=c.plan['prompt_version'],
        response_schema=c.plan['response_schema'],request_bindings=ctx['requests'],approved_plan_contract_sha256=contract,
        bot_live_scope={'question_ids':ctx['question_ids'],'plan_contract_sha256':contract,'maximum_bot_total_usd':'0.03'})
    publish_policy(c,monkeypatch)
    folder=trust.prepare(c.root,c.plan,'workspace/bot-authorizations/live',trust_manifest=c.manifest,trust_sha=c.sha)
    consent=bot_consent.issue(c.root,(folder/'MANIFEST.json').relative_to(c.root).as_posix(),sha(folder/'MANIFEST.json'),
        operation='live',owner_statement='SYNTHETIC TEST REVIEWER — ONE OWNED CALL',confirmed=True)
    c.authorization=consent.relative_to(c.root).as_posix();c.authorization_sha=sha(consent)
    return c


def fake_generator(c,monkeypatch,scenario='success',response_status='ANSWERED'):
    from tools.generation.response_capture import ResponseCapture
    from tools.generation_runner.controls import OfflineAdapter
    calls=[]
    def factory(root,qdir,request,row,budget,settings,pricing,day,*,trust_guard):
        assert root!=ROOT
        trust_guard()
        receipts=[]
        class NativeBudget:
            def admit(self,qid,cost,request_hash,*,mode):
                budget.admit(qid,cost,request_hash,mode='live')
        capture=ResponseCapture(root,qdir,question_id=row['question_id'],run_id=qdir.parent.parent.name,
            request_sha256=digest(request),package_sha256=row['M8_package_sha256'],mode='live')
        class Adapter(OfflineAdapter):
            def verify_model(self,model):
                receipts.append('METADATA');return super().verify_model(model)
            def count(self,request):
                receipts.append('COUNT');return super().count(request)
            def invoke(self,request):
                trust_guard();calls.append('OWNED_GENERATION');receipts.append('GENERATION')
                return super().invoke(request)
        return Adapter(row,mode='mock',request=request,settings=settings,pricing=pricing,day=day,
            budget=NativeBudget(),capture_sink=capture,answer=answer('partial') if response_status=='PARTIAL' else None if response_status=='ABSTAINED' else answer('answered'),scenario=scenario),None,SimpleNamespace(calls=receipts)
    monkeypatch.setattr('tools.generation_runner.live.create',factory)
    from tools.human_review import handoff
    monkeypatch.setattr(handoff,'inventory_context',lambda root:(None,{c.q['question_id']:store.question_record(root,c.q['question_id'])},{},{}))
    monkeypatch.setattr(handoff,'review_trust',lambda:{'path':c.manifest,'sha256':c.sha})
    return calls


def execute(c):
    return runner.execute(c.root,mode='live',selected=[c.q['question_id']],preflight=c.qualification,
        per_question_cap='0.03',aggregate_cap='0.03',owner_authorization=c.authorization,
        authorization_sha=c.authorization_sha,execute_approved_live=True,progress=lambda *a,**kw:None)


def test_preflight_consent_separate_from_generation_and_single_use(bot,monkeypatch):
    consent,h=preflight_approval(bot)
    auth=store.read(bot.root/consent)
    assert auth['allow_paid_inference'] is False
    calls=fake_count_provider(bot,monkeypatch)
    result=bot_preflight.execute(bot.root,bot.local,consent,h)
    assert store.read(result/'RESULT.json')['status']=='MODEL_QUALIFIED'
    assert calls==['METADATA','COUNT']
    assert not list(bot.root.rglob('LIVE_ATTEMPT.json'))
    with pytest.raises(FileExistsError):bot_preflight.execute(bot.root,bot.local,consent,h)


@pytest.mark.parametrize('fault',['untrusted-policy','missing-transfer','expired','changed-request','stale-preservation','unpublished','no-confirmation'])
def test_preflight_negative_controls(bot,monkeypatch,fault):
    if fault=='no-confirmation':
        folder=bot_preflight.prepare(bot.root,bot.local,'workspace/unsigned',trust_manifest=bot.manifest,trust_sha=bot.sha)
        with pytest.raises(ArtifactError):bot_consent.issue(bot.root,(folder/'MANIFEST.json').relative_to(bot.root).as_posix(),sha(folder/'MANIFEST.json'),operation='model-preflight',owner_statement='Fixture',confirmed=False)
        assert not list((bot.root/'workspace/bot-consents').rglob('MANIFEST.json'))
        return
    consent,h=preflight_approval(bot);auth=store.read(bot.root/consent)
    if fault=='untrusted-policy':auth['trust_manifest']='data/self-consistent/MANIFEST.json'
    if fault=='missing-transfer':auth['allow_source_transfer']=False
    if fault=='expired':auth['expires_at']='2000-01-01T00:00:00+00:00'
    if fault=='changed-request':auth['context']['request_sha256']='0'*64
    if fault=='stale-preservation':
        ref=auth['preservation_receipt'];p=bot.root/ref['path'];v=store.read(p);v['created_at']='2000-01-01T00:00:00+00:00';p.write_text(json.dumps(v));auth['preservation_receipt']['sha256']=sha(p)
    p=bot.root/consent;p.write_text(json.dumps(auth));h=sha(p)
    m=store.read(p.parent/'MANIFEST.json');m['files']['CONSENT.json']=h;m['consent_sha256']=digest(auth);(p.parent/'MANIFEST.json').write_text(json.dumps(m))
    if fault=='unpublished':
        new=bot.root/'workspace/pending.json';new.write_text(json.dumps(auth));consent=new.relative_to(bot.root).as_posix();h=sha(new)
    with pytest.raises((ArtifactError,ValueError,KeyError)):
        bot_preflight.execute(bot.root,bot.local,consent,h)
    assert not list(bot.root.rglob('TOKEN_COUNT_ATTEMPT.json'))


@pytest.mark.parametrize('scenario',['success','schema-error','api-failure'])
def test_real_native_bot_runner_and_review_handoff(bot,monkeypatch,scenario):
    c=live_plan(qualified(bot,monkeypatch),monkeypatch)
    calls=fake_generator(c,monkeypatch,scenario)
    run=execute(c)
    row=store.read(run/'questions'/c.q['question_id']/'RESULT.json')
    assert calls==['OWNED_GENERATION']
    assert row['question_source']=='BOT' and row['question_reference']==store.reference(c.root,c.q['question_id'])
    assert row['M7_result_sha256']==digest(c.result)
    assert row['provider_calls']==3
    assert list(run.rglob('LIVE_ATTEMPT.json')) # Synthetic root ONLY.
    data=projection.discover(c.root)
    assert not data['rejected'],data['rejected']
    assert data['summary']['real_generation_requests']==1
    assert len(data['records'][c.q['question_id']]['attempts'])==3
    if scenario=='success':
        assert row['response']['status']=='ANSWERED' and row['post_validation']['overall_status']=='REVIEW_REQUIRED'
        from tools.human_review.handoff import discover
        entries=discover(c.root)['entries'];assert len(entries)==1
        assert entries[0]['question']==c.q['question'] and entries[0]['coverage'] is None
        from tools.human_review import preparation
        prepared=preparation.discover(c.root,entries[0])
        assert prepared[0],prepared
    else:
        assert row['response'] is None and row['audit']['raw_response_capture']
    with pytest.raises(ArtifactError):execute(c)


def completed(c,monkeypatch):
    c=live_plan(qualified(c,monkeypatch),monkeypatch)
    fake_generator(c,monkeypatch)
    c.run=execute(c)
    from tools.human_review import handoff, preparation
    c.entry=handoff.discover(c.root)['entries'][0]
    c.receipt=preparation.discover(c.root,c.entry)[0][-1]
    return c


@pytest.mark.parametrize('decision',['APPROVE','REJECT','REQUEST_CHANGES'])
def test_bot_existing_owner_review_and_duplicate_lock(bot,monkeypatch,decision):
    from tools.human_review import local_poc, preparation
    c=completed(bot,monkeypatch)
    monkeypatch.setattr(local_poc,'local_access',lambda:{'bind':'127.0.0.1','headers':{'host':'127.0.0.1:8516'},'peer':'127.0.0.1'})
    assessment=copy.deepcopy(c.receipt['prepared'][1]['assessment_draft'])
    refs=c.receipt['materials']['source_field_references']
    assessment.update(answer_claim_inventory_complete=True,question_requirements_reviewed=True,
        response_status_appropriate=True,uncertainty=[])
    for claim in assessment['claims']:
        claim.update(outcome='SUPPORTED',rationale='Owned source explicitly contains the fixture claim.',passages=refs[:1])
    for requirement in assessment['requirements']:
        requirement.update(outcome='COMPLETE',rationale='Owned fixture requirement covered.',claim_indices=[0],passages=refs[:1])
    for name in ['qualifications','conflicts']:
        assessment[name].update(outcome='SATISFIED',rationale='Synthetic source reviewed; no material undisclosed issue.',passages=[])
    args={'manifest':c.receipt['manifest'],'expected_sha':c.receipt['manifest_sha256'],
        'reviewer_label':'SYNTHETIC TEST REVIEWER','decision':decision,'confirmed':True,
        'assessment':assessment,'additional_assertions':[]}
    path=preparation.owner_decide(c.root,**args)
    value=local_poc.read_record(c.root,path)
    assert value['status']=={'APPROVE':'OWNER_APPROVED_POC','REJECT':'OWNER_REJECTED_POC','REQUEST_CHANGES':'OWNER_REQUESTED_CHANGES_POC'}[decision]
    assert not value['authenticated'] and not value['fully_validated']
    with pytest.raises(ArtifactError):preparation.owner_decide(c.root,**args)
    data=projection.discover(c.root)
    assert data['records'][c.q['question_id']]['attempts'][-1]['owner_review_status']==value['status']
    # Local POC decisions never rewrite the original generated verdict or become
    # authenticated answer-quality acceptance.
    assert store.read(c.run/'questions'/c.q['question_id']/'RESULT.json')['post_validation']['overall_status']=='REVIEW_REQUIRED'


@pytest.mark.parametrize('fault',['missing-bot-scope','wrong-question','stage-cap','bot-total-cap','legacy-path'])
def test_native_bot_authorization_cannot_bypass_guards(bot,monkeypatch,fault):
    c=live_plan(qualified(bot,monkeypatch),monkeypatch)
    auth=store.read(c.root/c.authorization)
    if fault=='missing-bot-scope':
        policy=copy.deepcopy(c.policy);policy.pop('bot_live_scope')
        with pytest.raises(ArtifactError):trust.verify_plan_policy(c.plan,policy)
    elif fault=='stage-cap':
        policy=copy.deepcopy(c.policy);policy['maximum_stage_cap_usd']='0.00000001'
        with pytest.raises(ArtifactError):trust.verify_plan_policy(c.plan,policy)
    elif fault=='bot-total-cap':
        c.policy['bot_live_scope']['maximum_bot_total_usd']='0.00000001';publish_policy(c,monkeypatch)
        with pytest.raises(ArtifactError,match='BOT_CUMULATIVE'):
            trust.preservation_receipt(c.root,c.plan,c.manifest,c.sha)
    else:
        if fault=='wrong-question':auth['question_ids']=['BOT-999999']
        path=c.root/'workspace/unpublished-attestation.json';path.write_text(json.dumps(auth))
        with pytest.raises(ArtifactError):runner.authorize(c.root,c.plan,path.relative_to(c.root).as_posix(),sha(path))
    assert not list(c.root.rglob('LIVE_ATTEMPT.json'))


def test_preflight_failure_seals_block_and_does_not_generate(bot,monkeypatch):
    consent,h=preflight_approval(bot);calls=fake_count_provider(bot,monkeypatch,fail=True)
    run=bot_preflight.execute(bot.root,bot.local,consent,h)
    assert store.read(run/'RESULT.json')['status']!='MODEL_QUALIFIED'
    assert calls==[] and not list(bot.root.rglob('LIVE_ATTEMPT.json'))
    with pytest.raises(ArtifactError):
        bot_source.build_plan(bot.root,selected=[bot.q['question_id']],preflight=(run/'MANIFEST.json').relative_to(bot.root).as_posix(),
            per_question_cap='0.03',aggregate_cap='0.03')


@pytest.mark.parametrize('target',['source','candidate','evidence','request','model-receipt'])
def test_changed_bindings_block_before_native_provider(bot,monkeypatch,target):
    c=live_plan(qualified(bot,monkeypatch),monkeypatch)
    calls=fake_generator(c,monkeypatch)
    base=c.root/c.local.rsplit('/',1)[0]
    file={'source':c.root/'owned/source.json','candidate':base/'CANDIDATES.json',
          'evidence':base/'EVIDENCE_PACKAGE.json','request':base/'REQUEST_PACKAGE.json',
          'model-receipt':c.root/c.qualification.rsplit('/',1)[0]/'MODEL_PREFLIGHT.json'}[target]
    file.write_text('{}')
    with pytest.raises((ArtifactError,ValueError,KeyError)):execute(c)
    assert calls==[] and not list(c.root.rglob('LIVE_ATTEMPT.json'))


@pytest.mark.parametrize('status',['PARTIAL','ABSTAINED'])
def test_native_bot_model_outcomes_are_not_semantic_acceptance(bot,monkeypatch,status):
    c=live_plan(qualified(bot,monkeypatch),monkeypatch)
    fake_generator(c,monkeypatch,response_status=status)
    run=execute(c);row=store.read(run/'questions'/c.q['question_id']/'RESULT.json')
    assert row['response']['status']==status and row['post_validation']['overall_status']=='REVIEW_REQUIRED'
    assert not row['post_validation']['fully_validated']
    from tools.human_review import handoff
    entry=handoff.discover(c.root)['entries'][0]
    assert entry['coverage'] is None and entry['independent_semantic_acceptance'] is False


def test_all_live_bot_operational_views_are_read_only(bot,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from streamlit.util import calc_hash

    from apps.knowledge_preparation import bot_records
    from tools.human_review import local_poc
    c=completed(bot,monkeypatch)
    monkeypatch.setattr(bot_records,'ROOT',c.root)
    monkeypatch.setattr(local_poc,'local_access',lambda:{'bind':'127.0.0.1','headers':{'host':'127.0.0.1:8516'},'peer':'127.0.0.1'})
    def denied(*a,**kw):raise AssertionError('NO_EXECUTION_ON_REFRESH')
    monkeypatch.setattr(runner,'execute',denied)
    monkeypatch.setattr(bot_preflight,'execute',denied)
    before={str(p):p.read_bytes() for base in ['data','workspace'] for p in (c.root/base).rglob('*') if p.is_file()}
    for route in ['knowledge-retrieval','pre-generation','generation','post-generation-evaluation-human-review','human-review']:
        app=AppTest.from_file(str(ROOT/'apps/knowledge_preparation/app.py'),default_timeout=60)
        app._page_hash=calc_hash(route)
        app.session_state['workspace-question-source']='Bot questions'
        app.session_state['bot-shared-question']=c.q['question_id']
        app.run()
        assert not app.exception and not app.error,(route,app.exception,app.error)
        assert any(s.label=='Bot question' and s.value==c.q['question_id'] for s in app.selectbox)
        assert any('COMPLETED' in m.value for m in app.markdown),route
        if route=='human-review':
            assert any('LOCAL_POC_REVIEW' in h.value for h in app.subheader)
            assert app.form
        app.run()
        assert not app.exception and not app.error,(route,app.exception,app.error)
    after={str(p):p.read_bytes() for base in ['data','workspace'] for p in (c.root/base).rglob('*') if p.is_file()}
    assert before==after


def test_live_consent_ui_is_explicit_and_does_not_execute_on_render(bot,monkeypatch):
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import bot_live
    from tools.bot_runtime import dispatch
    from tools.human_review import local_poc
    c=live_plan(qualified(bot,monkeypatch),monkeypatch)
    monkeypatch.setattr(bot_live,'ROOT',c.root)
    monkeypatch.setattr(local_poc,'local_access',lambda:{'bind':'127.0.0.1','headers':{'host':'127.0.0.1:8516'},'peer':'127.0.0.1'})
    calls=[]
    monkeypatch.setattr(dispatch,'native',lambda *a,**kw:calls.append((a,kw)))
    app=AppTest.from_string('from apps.knowledge_preparation.bot_live import render\nrender()').run()
    assert not app.exception
    assert len(bot_live.pending(c.root))==1
    assert app.form and not calls
    app.run()
    assert not calls


@pytest.mark.parametrize('part',['MODEL_PREFLIGHT.json','PROVIDER_CALLS.json','START.json'])
def test_qualification_tamper_fails_closed(bot,monkeypatch,part):
    c=qualified(bot,monkeypatch)
    base=c.root/c.qualification.rsplit('/',1)[0]
    (base/part).write_text('{}')
    with pytest.raises((ArtifactError,ValueError,KeyError)):
        bot_source.build_plan(c.root,selected=[c.q['question_id']],preflight=c.qualification,
            per_question_cap='0.03',aggregate_cap='0.03')


def test_failed_consent_preparation_never_publishes_owner_permission(bot,monkeypatch):
    folder=bot_preflight.prepare(bot.root,bot.local,'workspace/bot-authorizations/unsigned',trust_manifest=bot.manifest,trust_sha=bot.sha)
    monkeypatch.setattr(bot_preflight,'validate_value',lambda *a,**kw:(_ for _ in ()).throw(ArtifactError('SOURCE_CHANGED')))
    with pytest.raises(ArtifactError):
        bot_consent.issue(bot.root,(folder/'MANIFEST.json').relative_to(bot.root).as_posix(),sha(folder/'MANIFEST.json'),
            operation='model-preflight',owner_statement='SYNTHETIC COUNT APPROVAL',confirmed=True)
    assert not list((bot.root/'workspace/bot-consents/approved').rglob('CONSENT.json'))


def test_unsealed_native_bot_is_visible_without_accepting_output(bot,monkeypatch):
    c=completed(bot,monkeypatch)
    (c.run/'MANIFEST.json').unlink()  # Disposable interruption fixture only.
    data=projection.discover(c.root)
    assert not data['rejected'],data['rejected']
    row=data['records'][c.q['question_id']]['attempts'][-1]
    assert row['execution_status']=='INCOMPLETE' and row['response'] is None
    assert row['cost_usd'] is None and data['summary']['unresolved_native_runs']==1
    with pytest.raises(ArtifactError):execute(c)


def test_ui_confirmation_uses_native_consent_and_runner_in_owned_root(bot,monkeypatch):
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import bot_live
    from tools.bot_runtime import dispatch
    from tools.human_review import local_poc
    c=live_plan(qualified(bot,monkeypatch),monkeypatch)
    calls=fake_generator(c,monkeypatch)
    monkeypatch.setattr(bot_live,'ROOT',c.root)
    monkeypatch.setattr(local_poc,'local_access',lambda:{'bind':'127.0.0.1','headers':{'host':'127.0.0.1:8516'},'peer':'127.0.0.1'})
    operations=[]
    def native(root,qid,mode,*,arguments,progress=None):
        assert root!=ROOT and qid==c.q['question_id']
        operations.append(mode)
        flags={arguments[i]:arguments[i+1] for i in range(len(arguments)-1) if arguments[i].startswith('--') and not arguments[i+1].startswith('--')}
        if mode=='issue-live-consent':
            text=store.read(root/flags['--owner-statement-file'])['statement']
            path=bot_consent.issue(root,flags['--preparation-manifest'],flags['--preparation-sha'],operation='live',owner_statement=text,confirmed=True)
            return {'question_id':qid,'mode':mode,'consent':path.relative_to(root).as_posix(),'consent_sha256':sha(path)}
        assert mode=='live'
        c.authorization=flags['--owner-authorization'];c.authorization_sha=flags['--authorization-sha']
        run=execute(c)
        return {'question_id':qid,'mode':mode,'run':run.relative_to(root).as_posix()}
    monkeypatch.setattr(dispatch,'native',native)
    app=AppTest.from_string('from apps.knowledge_preparation.bot_live import render\nrender()').run()
    app.selectbox[0].select(0).run()
    app.text_area[0].set_value('SYNTHETIC LOCAL TEST OWNER — this exact fixture only.')
    app.checkbox[0].check()
    next(b for b in app.button if b.label=='Approve generation').click().run()
    assert not app.exception and not app.error,(app.exception,[e.value for e in app.error],operations,[a.value for a in app.text_area],[a.value for a in app.checkbox])
    assert operations==['issue-live-consent','live'] and calls==['OWNED_GENERATION']
    assert app.session_state['bot-active-id']==c.q['question_id']
    assert not bot_live.pending(c.root)


def test_question_flow_prepares_unsigned_count_only(bot):
    from tools.generation_runner.bot_flow import prepare_next
    value=prepare_next(bot.root,bot.q['question_id'],'workspace/bot-authorizations/next-count')
    assert value['status']=='AWAITING_OWNER_CONSENT' and value['stage']=='model-preflight'
    template=store.read(bot.root/value['manifest'].rsplit('/',1)[0]/'PREFLIGHT_CONSENT_TEMPLATE.json')
    assert not template['allow_source_transfer'] and not template['allow_provider_preflight'] and not template['allow_paid_inference']
    assert not list((bot.root/'workspace/bot-consents').rglob('CONSENT.json'))


def test_question_flow_cannot_self_allowlist(bot,monkeypatch):
    from tools.generation_runner.bot_flow import prepare_next
    bot.policy['bot_provider_preflight_allowlist']=[];publish_policy(bot,monkeypatch)
    result=prepare_next(bot.root,bot.q['question_id'],'workspace/bot-authorizations/denied')
    assert result=={'status':'POLICY_REVIEW_REQUIRED','stage':'model-preflight'}
    assert not (bot.root/'workspace/bot-authorizations/denied').exists()


def test_question_flow_qualified_does_not_grant_paid_scope(bot,monkeypatch):
    from tools.generation_runner.bot_flow import prepare_next
    c=qualified(bot,monkeypatch)
    assert prepare_next(c.root,c.q['question_id'],'workspace/bot-authorizations/no-paid')=={
        'status':'POLICY_REVIEW_REQUIRED','stage':'live'}
    assert not list(c.root.rglob('LIVE_ATTEMPT.json'))


def test_question_flow_prepares_exact_live_without_execution(bot,monkeypatch):
    from tools.generation_runner.bot_flow import prepare_next
    c=live_plan(qualified(bot,monkeypatch),monkeypatch)
    value=prepare_next(c.root,c.q['question_id'],'workspace/bot-authorizations/next-live')
    assert value['stage']=='live' and value['status']=='AWAITING_OWNER_CONSENT'
    template=store.read(c.root/value['manifest'].rsplit('/',1)[0]/'AUTHORIZATION_TEMPLATE.json')
    assert template['question_ids']==[c.q['question_id']]
    assert template['allow_paid_inference'] is False and template['allow_source_transfer'] is False
    assert not list(c.root.rglob('LIVE_ATTEMPT.json'))


def test_question_flow_failure_or_interruption_cannot_retry(bot,monkeypatch):
    from tools.generation_runner.bot_flow import prepare_next
    consent,h=preflight_approval(bot);fake_count_provider(bot,monkeypatch,fail=True)
    run=bot_preflight.execute(bot.root,bot.local,consent,h)
    assert store.read(run/'RESULT.json')['status']=='BLOCKED_INTEGRITY'
    for sealed in [True,False]:
        if not sealed:(run/'MANIFEST.json').unlink()
        value=prepare_next(bot.root,bot.q['question_id'],'workspace/bot-authorizations/no-retry')
        assert value['status']=='PREFLIGHT_RECORDED_NO_AUTOMATIC_RETRY'
    assert not list(bot.root.rglob('LIVE_ATTEMPT.json'))


def test_question_flow_completed_cannot_prepare_duplicate(bot,monkeypatch):
    from tools.generation_runner.bot_flow import prepare_next
    c=completed(bot,monkeypatch)
    assert prepare_next(c.root,c.q['question_id'],'workspace/bot-authorizations/no-duplicate')['status']=='EXECUTION_ALREADY_RECORDED'


def test_triage_mode_never_submits_from_disabled_chat_box(bot,monkeypatch):
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import bot_live
    from tools.bot_runtime import dispatch
    from tools.human_review import local_poc
    c=bot
    monkeypatch.setattr(bot_live,'ROOT',c.root)
    monkeypatch.setattr(local_poc,'local_access',lambda:{'bind':'127.0.0.1','headers':{'host':'127.0.0.1:8516'},'peer':'127.0.0.1'})
    calls=[]
    monkeypatch.setattr(store,'register',lambda *a,**kw:calls.append('register'))
    monkeypatch.setattr(dispatch,'native',lambda *a,**kw:calls.append('dispatch'))
    app=AppTest.from_file(str(ROOT/'apps/knowledge_preparation/app.py')).run()
    next(r for r in app.radio if r.label=='Request mode').set_value('Request Approvals / Triage').run()
    assert app.chat_input[0].disabled
    from streamlit.testing.v1.errors import AppTestError
    with pytest.raises(AppTestError, match='disabled'):
        app.chat_input[0].set_value(c.q['question'])
    assert not app.exception and not app.error,(app.exception,app.error)
    assert not calls and 'bot-active-id' not in app.session_state
    assert not list(c.root.rglob('TOKEN_COUNT_ATTEMPT.json')) and not list(c.root.rglob('LIVE_ATTEMPT.json'))


def test_ui_count_approval_stops_before_paid_without_scope(bot,monkeypatch):
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import bot_live
    from tools.bot_runtime import dispatch
    from tools.generation_runner.bot_flow import prepare_next
    from tools.human_review import local_poc
    c=bot;prepare_next(c.root,c.q['question_id'],'workspace/bot-authorizations/ui-count')
    provider=fake_count_provider(c,monkeypatch)
    monkeypatch.setattr(bot_live,'ROOT',c.root)
    monkeypatch.setattr(local_poc,'local_access',lambda:{'bind':'127.0.0.1','headers':{'host':'127.0.0.1:8516'},'peer':'127.0.0.1'})
    operations=[]
    def native(root,qid,mode,*,arguments,progress=None):
        assert root!=ROOT;operations.append(mode)
        flags={arguments[i]:arguments[i+1] for i in range(len(arguments)-1) if arguments[i].startswith('--') and not arguments[i+1].startswith('--')}
        value={'question_id':qid,'mode':mode}
        if mode=='issue-preflight-consent':
            path=bot_consent.issue(root,flags['--preparation-manifest'],flags['--preparation-sha'],operation='model-preflight',
                owner_statement=store.read(root/flags['--owner-statement-file'])['statement'],confirmed=True)
            return value|{'consent':path.relative_to(root).as_posix(),'consent_sha256':sha(path)}
        if mode=='model-preflight':
            run=bot_preflight.execute(root,flags['--local-manifest'],flags['--preflight-consent'],flags['--preflight-consent-sha'])
            return value|{'run':run.relative_to(root).as_posix()}
        assert mode=='prepare-next'
        return value|prepare_next(root,qid,flags['--output'])
    monkeypatch.setattr(dispatch,'native',native)
    app=AppTest.from_string('from apps.knowledge_preparation.bot_live import render\nrender()').run()
    assert not provider
    app.text_area[0].set_value('SYNTHETIC COUNT ONLY APPROVAL')
    app.checkbox[0].check()
    next(b for b in app.button if b.label=='Approve token/cost preflight').click().run()
    assert not app.exception and not app.error
    assert provider==['METADATA','COUNT'] and operations==['issue-preflight-consent','model-preflight','prepare-next']
    assert app.session_state['bot-next-step']=={'question_id':c.q['question_id'],'mode':'prepare-next','status':'POLICY_REVIEW_REQUIRED','stage':'live'}
    app.run();assert len(provider)==2 and not app.form
    assert not list(c.root.rglob('LIVE_ATTEMPT.json'))


def test_question_flow_mock_cannot_be_qualified(bot):
    from tools.generation_runner.bot_flow import prepare_next
    q=store.register(bot.root,'A different owned simulation question.',uuid4().hex)
    bot_runtime.execute(bot.root,q['question_id'],mode='mock')
    assert prepare_next(bot.root,q['question_id'],'workspace/bot-authorizations/not-real')=={
        'status':'LOCAL_CHECK_REQUIRED','stage':'local-check'}
    assert not list(bot.root.rglob('TOKEN_COUNT_ATTEMPT.json'))


def test_chat_nonlocal_cannot_register_or_prepare(bot,monkeypatch):
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import bot_chat as chat_ui
    from tools.bot_runtime import dispatch
    def denied(*a,**kw):raise ArtifactError('LOCALHOST_REQUIRED')
    monkeypatch.setattr('tools.human_review.local_poc.require_localhost',denied)
    monkeypatch.setattr(store,'register',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('NO_NONLOCAL_REGISTRATION')))
    monkeypatch.setattr(dispatch,'native',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('NO_NONLOCAL_EXECUTION')))
    monkeypatch.setattr(chat_ui,'state',lambda *a:{'enabled':True,'settings':{'per_question_cap_usd':'0.03','total_bot_cap_usd':'1.00'},'budget':None,'blocked':False})
    app=AppTest.from_file(str(ROOT/'apps/knowledge_preparation/app.py')).run()
    app.chat_input[0].set_value('An unauthorized nonlocal question.').run()
    assert not app.exception and app.error
    assert 'bot-active-id' not in app.session_state


def test_native_and_qualification_traces_bind_existing_sources_and_calls(bot,monkeypatch):
    from tools.bot_runtime.trace_read import discover
    c=completed(bot,monkeypatch)
    traces=discover(c.root,c.q['question_id'])
    assert not traces['rejected'],traces['rejected']
    assert len(traces['traces'])==3 and all(t['execution_seal_verified'] for t in traces['traces'])
    assert {t['mode'] for t in traces['traces']}=={'local-check','model-preflight','live'}
    live=next(t for t in traces['traces'] if t['mode']=='live')
    stages={e['stage'] for e in live['events']}
    assert {'OWNER_AUTHORIZATION','MODEL_METADATA','MODEL_TOKEN_COUNT','LLM_GENERATION','POST_GENERATION_VALIDATION','ARTIFACT_PERSISTENCE'}<=stages
    row=store.read(c.run/'questions'/c.q['question_id']/'RESULT.json')
    assert row['provider_calls']==3 and row['request_sha256']==c.plan['questions'][0]['request_sha256']

# Native simple-chat controls reuse the same synthetic boundary fixtures above.
@pytest.fixture
def chat(bot, monkeypatch):
    from tools.generation_runner import bot_chat
    c = bot
    bindings = {k: c.ctx[k] for k in ['model', 'prompt_version', 'response_schema',
                                    'settings_sha256', 'profile_sha256', 'pricing_sha256']}
    c.policy.update(model=c.config[0].model, prompt_version=c.config[0].prompt_version,
                    response_schema=c.config[0].response_schema, bot_live_scope=None,
                    bot_provider_preflight_allowlist=[])
    c.policy['bot_chat'] = {'schema': bot_chat.VERSION, 'per_question_cap_usd': '0.03',
        'total_bot_cap_usd': '1.00', 'generation_calls_per_submission': 1, 'retries': 0,
        'fallback': None, 'budget_scope': 'ALL_BOT_NATIVE_RESERVATIONS',
        'disclosure_sha256': digest(bot_chat.DISCLOSURE), 'configuration_bindings': bindings}
    publish_policy(c, monkeypatch)
    assert bot_chat.active(c.root) is None
    bot_chat.enable(c.root, owner_statement='SYNTHETIC OWNER ENABLEMENT ONLY', confirmed=True)
    c.q = store.register(c.root, c.q['question'], uuid4().hex)
    return c


def test_chat_send_uses_native_pipeline_and_stops_after_one(chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = chat
    counts = fake_count_provider(c, monkeypatch)
    generates = fake_generator(c, monkeypatch)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    outcome = store.read(run / 'RESULT.json')
    assert outcome['status'] == 'COMPLETED', outcome
    assert counts == ['METADATA', 'COUNT'] and generates == ['OWNED_GENERATION']
    assert outcome['references'].keys() == {'local', 'qualification', 'generation'}
    assert projection.discover(c.root)['records'][c.q['question_id']]['chat_execution']['status'] == 'COMPLETED'
    with pytest.raises(ArtifactError, match='DUPLICATE'):
        bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert len(generates) == 1


@pytest.mark.parametrize('decision', ['missing', 'disabled', 'tampered', 'wrong_send'])
def test_chat_enablement_is_explicit_and_bound(chat, monkeypatch, decision):
    from tools.generation_runner import bot_chat
    c = chat
    if decision == 'missing':
        with pytest.raises(ArtifactError):
            bot_chat.execute(c.root, c.q['question_id'], confirmed=False)
    elif decision == 'disabled':
        bot_chat.enable(c.root, owner_statement='SYNTHETIC DISABLE', confirmed=True, enabled=False)
        with pytest.raises(ArtifactError):
            bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    elif decision == 'tampered':
        path = next((c.root / bot_chat.BASE / 'control').glob('*/CONTROL.json'))
        path.write_text('{}')
        with pytest.raises(ArtifactError):
            bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    else:
        # A registered question, active owner and valid policy alone grant no Send.
        with pytest.raises(ArtifactError):
            bot_chat.check_context(c.root, c.ctx, c.policy)
    assert not list((c.root / 'workspace/bot-consents').glob('approved/*'))


def test_chat_budget_blocks_after_count_without_generation(chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = chat
    counts = fake_count_provider(c, monkeypatch)
    generates = fake_generator(c, monkeypatch)
    original = bot_preflight.execute
    def expensive(*args, **kw):
        folder = original(*args, **kw)
        # Boundary control: no altered receipt is admitted to the native runner.
        result = store.read(folder / 'RESULT.json')
        result['maximum_cost_usd'] = '0.10'
        (folder / 'RESULT.json').write_text(json.dumps(result))
        return folder
    monkeypatch.setattr(bot_preflight, 'execute', expensive)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    value = store.read(run / 'RESULT.json')
    assert counts == ['METADATA', 'COUNT'] and not generates
    assert value['finding']['code'] == 'BUDGET_LIMIT_EXCEEDED'
    assert value['finding']['estimated_maximum_cost_usd'] == '0.10'
    assert value['finding']['applicable_limit_usd'] == '0.03'
    assert value['generation_attempted'] is False
    assert '$0.10' in value['finding']['message'] and '$0.03' in value['finding']['message']


def test_chat_source_failure_never_contacts_provider(chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = chat
    counts = fake_count_provider(c, monkeypatch)
    monkeypatch.setattr(bot_runtime, 'local_services', lambda *a: (_ for _ in ()).throw(ValueError('SOURCE_CHANGED')))
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert not counts
    assert store.read(run / 'RESULT.json')['finding']['code'] == 'SOURCE_VALIDATION_FAILED'


@pytest.mark.parametrize('scenario', ['schema-error', 'api-failure'])
def test_chat_failed_output_retains_native_diagnostics(chat, monkeypatch, scenario):
    from tools.generation_runner import bot_chat
    c = chat
    fake_count_provider(c, monkeypatch)
    calls = fake_generator(c, monkeypatch, scenario=scenario)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    value = store.read(run / 'RESULT.json')
    assert calls == ['OWNED_GENERATION']
    assert value['finding'], value
    generation = c.root / value['references']['generation']
    assert generation.exists()
    row = store.read(generation.parent / 'RESULTS.json')['questions'][0]
    assert row['audit'].get('raw_response_capture')
    assert value['generation_attempted'] is True


def test_chat_disable_preserves_historical_qualification(chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = chat
    fake_count_provider(c, monkeypatch)
    fake_generator(c, monkeypatch)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    value = store.read(run / 'RESULT.json')
    bot_chat.enable(c.root, owner_statement='SYNTHETIC DISABLE', confirmed=True, enabled=False)
    bot_source.validate_qualification(c.root, value['references']['qualification'])
    assert not bot_chat.active(c.root)
    assert not projection.discover(c.root)['rejected']


def test_chat_budget_persists_across_enablement(chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = chat
    fake_count_provider(c, monkeypatch)
    fake_generator(c, monkeypatch)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert store.read(run / 'RESULT.json')['status'] == 'COMPLETED'
    before = bot_chat.budget_state(c.root, c.policy['bot_chat'])
    assert before['reserved_usd'] != '0'
    bot_chat.enable(c.root, owner_statement='SYNTHETIC DISABLE', confirmed=True, enabled=False)
    bot_chat.enable(c.root, owner_statement='SYNTHETIC REENABLE', confirmed=True)
    assert bot_chat.budget_state(c.root, c.policy['bot_chat']) == before
    with pytest.raises(ArtifactError, match='TOTAL_BUDGET'):
        bot_chat.budget_state(c.root, c.policy['bot_chat'], additional='1.00')


def test_chat_ui_refresh_never_enables_or_dispatches(chat, monkeypatch):
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import bot_chat as ui
    from tools.generation_runner import bot_chat
    c = chat
    monkeypatch.setattr(ui, 'ROOT', c.root)
    def denied(*a, **kw):
        raise AssertionError('NO_EXECUTION_ON_REFRESH')
    monkeypatch.setattr(bot_chat, 'enable', denied)
    monkeypatch.setattr(bot_chat, 'execute', denied)
    app = AppTest.from_string('from apps.knowledge_preparation.bot_chat import controls\ncontrols()').run()
    assert not app.exception
    assert any('Live chat enabled' in v.value for v in app.success)
    app.run()
    assert not app.exception

@pytest.mark.parametrize('status', ['ANSWERED', 'PARTIAL', 'ABSTAINED'])
def test_chat_model_status_and_unlabeled_bot_review_preserved(chat, monkeypatch, status):
    from tools.generation_runner import bot_chat
    c = chat
    fake_count_provider(c, monkeypatch)
    calls = fake_generator(c, monkeypatch, response_status=status)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    value = store.read(run / 'RESULT.json')
    assert value['status'] == 'COMPLETED' and len(calls) == 1, value
    rows = store.read(c.root / value['references']['generation'].replace('MANIFEST.json', 'RESULTS.json'))
    assert rows['questions'][0]['response']['status'] == status
    record = projection.discover(c.root)['records'][c.q['question_id']]
    assert record['reference']['answerability'] == 'UNASSESSED'
    assert record['reference']['mandatory_evidence_group_ids'] is None
    assert record['attempts'][-1]['owner_review_status'] == 'PENDING_REVIEW'


def test_chat_busy_admission_never_dispatches_provider(chat, monkeypatch):
    import fcntl

    from tools.generation_runner import bot_chat
    c = chat
    calls = fake_count_provider(c, monkeypatch)
    with (c.root / bot_chat.BASE / 'EXECUTION.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ArtifactError, match='ALREADY_PROCESSING'):
            bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert not calls
    assert not (c.root / bot_chat.BASE / 'submissions' / c.q['question_id']).exists()


def test_chat_prior_unknown_billing_blocks_next_send(chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = chat
    fake_count_provider(c, monkeypatch)
    calls = fake_generator(c, monkeypatch, scenario='api-failure')
    bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    q = store.register(c.root, 'A new owned question.', uuid4().hex)
    run = bot_chat.execute(c.root, q['question_id'], confirmed=True)
    value = store.read(run / 'RESULT.json')
    assert value['finding']['code'] == 'BILLING_STATUS_UNKNOWN'
    assert value['stage'] == 'BUDGET_ADMISSION' and len(calls) == 1


def test_chat_missing_evidence_is_not_a_model_abstention(chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = chat
    calls = fake_count_provider(c, monkeypatch)
    folder = c.root / 'owned/empty-local'
    folder.mkdir()
    store.write(folder / 'RESULT.json', {'application_outcome': 'INSUFFICIENT_EVIDENCE'})
    monkeypatch.setattr(bot_runtime, 'execute', lambda *a, **kw: folder)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    value = store.read(run / 'RESULT.json')
    assert value['finding']['code'] == 'INSUFFICIENT_EVIDENCE'
    assert not calls and not value.get('model_status')


@pytest.mark.parametrize('failure,code', [
    ('CHAT_TOTAL_BUDGET_EXCEEDED', 'BUDGET_LIMIT_EXCEEDED'),
    ('MODEL_CONTEXT_OVERSIZED', 'CONTEXT_LIMIT_EXCEEDED'),
    ('PRICING_STALE', 'PRICING_OR_COST_UNAVAILABLE'),
    ('SOURCE_CHANGED', 'SOURCE_VALIDATION_FAILED'),
    ('CHAT_DUPLICATE_SUBMISSION_NO_RETRY', 'DUPLICATE_SUBMISSION'),
    ('RAW_RESPONSE_CAPTURE_FAILED', 'RAW_RESPONSE_CAPTURE_FAILED'),
    ('secret publisher passage must not be displayed', 'EXECUTION_BLOCKED'),
])
def test_chat_stop_messages_never_expose_exception_text(failure, code):
    from tools.generation_runner import bot_chat
    assert bot_chat.error_code(ValueError(failure)) == code
    value = bot_chat.finding(code, stage='OWNED_STAGE')
    assert failure not in value['message']
    assert value['generation_attempted'] is False


def test_chat_pending_config_and_confirmation_cannot_enable(bot, monkeypatch):
    from tools.generation_runner import bot_chat
    c = bot
    with pytest.raises(ArtifactError):
        bot_chat.enable(c.root, owner_statement='', confirmed=True)
    with pytest.raises(ArtifactError):
        bot_chat.enable(c.root, owner_statement='SYNTHETIC', confirmed=False)
    with pytest.raises(ArtifactError):
        bot_chat.enable(c.root, owner_statement='SYNTHETIC', confirmed=True)
    assert not (c.root / bot_chat.BASE).exists()


def test_chat_records_tamper_and_restart_fail_closed(chat, monkeypatch):
    from tools.bot_runtime.chat_records import record
    from tools.generation_runner import bot_chat
    c = chat
    fake_count_provider(c, monkeypatch)
    fake_generator(c, monkeypatch)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    first = record(c.root, c.q['question_id'])
    assert record(c.root, c.q['question_id']) == first
    (run / 'RESULT.json').write_text('{}')
    with pytest.raises(ArtifactError):
        record(c.root, c.q['question_id'])
    assert projection.discover(c.root)['rejected']


@pytest.fixture
def default_chat(chat, monkeypatch):
    """Reviewed successor in disposable root; old OFF event remains untouched."""
    from tools.generation_runner import bot_chat
    c = chat
    bot_chat.enable(c.root, owner_statement='SYNTHETIC LEGACY OFF', confirmed=True, enabled=False)
    c.policy['bot_chat']['send_authorization'] = bot_chat.SEND_AUTHORITY
    publish_policy(c, monkeypatch)
    assert bot_chat.active(c.root) is None
    c.controls_before = {p: p.read_bytes() for p in (c.root / bot_chat.BASE / 'control').rglob('*') if p.is_file()}
    return c


def test_default_chat_send_runs_native_end_to_end_without_enablement(default_chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = default_chat
    counts = fake_count_provider(c, monkeypatch)
    generates = fake_generator(c, monkeypatch)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    value = store.read(run / 'RESULT.json')
    assert value['status'] == 'COMPLETED', value
    assert counts == ['METADATA', 'COUNT'] and generates == ['OWNED_GENERATION']
    send = bot_chat.submission(c.root, c.q['question_id'], c.policy)
    assert send['schema'] == bot_chat.SEND_VERSION and 'activation' not in send
    assert send['trust'] == {'path': c.manifest, 'sha256': c.sha}
    assert send['config_sha256'] == digest(c.policy['bot_chat'])
    assert all(p.read_bytes() == raw for p, raw in c.controls_before.items())
    bot_source.validate_qualification(c.root, value['references']['qualification'])
    record = projection.discover(c.root)['records'][c.q['question_id']]
    assert record['chat_execution']['status'] == 'COMPLETED'
    assert record['attempts'][-1]['owner_review_status'] == 'PENDING_REVIEW'
    with pytest.raises(ArtifactError, match='DUPLICATE'):
        bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert len(generates) == 1


def test_default_chat_no_control_records_needed_but_send_is_required(default_chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = default_chat
    shutil.rmtree(c.root / bot_chat.BASE / 'control')  # disposable synthetic history only
    counts = fake_count_provider(c, monkeypatch)
    generates = fake_generator(c, monkeypatch)
    with pytest.raises(ArtifactError, match='EXPLICIT_CHAT_SEND_REQUIRED'):
        bot_chat.execute(c.root, c.q['question_id'], confirmed=False)
    with pytest.raises(ArtifactError):
        bot_chat.check_context(c.root, c.ctx, c.policy)
    assert not list((c.root / 'workspace/bot-consents').glob('approved/*'))
    assert not counts and not generates
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert store.read(run / 'RESULT.json')['status'] == 'COMPLETED'
    assert not (c.root / bot_chat.BASE / 'control').exists()


@pytest.mark.parametrize('field,value', [
    ('explicit_send', False), ('allow_source_transfer', False), ('allow_paid_inference', False),
    ('question_id', 'BOT-999999'), ('question_reference', {}), ('trust', {}),
    ('config_sha256', 'f' * 64), ('authority', 'UNREVIEWED'), ('activation', {}),
    ('disclosure_sha256', '0' * 64),
])
def test_default_chat_tampered_send_blocks_before_provider(default_chat, monkeypatch, field, value):
    from tools.generation_runner import bot_chat
    c = default_chat
    counts = fake_count_provider(c, monkeypatch)
    original = bot_preflight.prepare
    def change(*args, **kw):
        folder = c.root / bot_chat.BASE / 'submissions' / c.q['question_id']
        send = store.read(folder / 'SEND.json'); send[field] = value
        (folder / 'SEND.json').write_text(json.dumps(send))
        # Hash-sealing is not permission: even a self-consistent seal must fail.
        (folder / 'MANIFEST.json').unlink(); store.seal(folder, 'bot-chat-submission-1.0')
        return original(*args, **kw)
    monkeypatch.setattr(bot_preflight, 'prepare', change)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert store.read(run / 'RESULT.json')['finding'] and not counts
    assert not list((c.root / 'workspace/bot-consents').glob('approved/*'))


@pytest.mark.parametrize('failure', ['source', 'budget', 'unknown_billing', 'provider', 'context', 'pricing'])
def test_default_chat_existing_safety_stops_are_preserved(default_chat, monkeypatch, failure):
    from tools.generation_runner import bot_chat
    c = default_chat
    counts = fake_count_provider(c, monkeypatch, fail=failure == 'provider')
    generates = fake_generator(c, monkeypatch)
    if failure == 'source':
        monkeypatch.setattr(bot_runtime, 'local_services', lambda *a: (_ for _ in ()).throw(ValueError('SOURCE_CHANGED')))
    elif failure in {'budget', 'unknown_billing'}:
        code = 'CHAT_TOTAL_BUDGET_EXCEEDED' if failure == 'budget' else 'CHAT_PRIOR_BILLING_OR_OUTCOME_UNKNOWN'
        monkeypatch.setattr(bot_chat, 'budget_state', lambda *a, **kw: (_ for _ in ()).throw(ArtifactError(code)))
    elif failure in {'context', 'pricing'}:
        code = 'MODEL_CONTEXT_OVERSIZED' if failure == 'context' else 'PRICING_STALE'
        monkeypatch.setattr(bot_preflight, 'execute', lambda *a, **kw: (_ for _ in ()).throw(ArtifactError(code)))
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    result = store.read(run / 'RESULT.json')
    expected = {'source': 'SOURCE_VALIDATION_FAILED', 'budget': 'BUDGET_LIMIT_EXCEEDED',
                'unknown_billing': 'BILLING_STATUS_UNKNOWN',
                # Existing GenerationService deliberately reports failed count/access bindings as integrity failure.
                'provider': 'SOURCE_VALIDATION_FAILED',
                'context': 'CONTEXT_LIMIT_EXCEEDED', 'pricing': 'PRICING_OR_COST_UNAVAILABLE'}
    assert result['finding']['code'] == expected[failure], result
    assert not generates
    if failure != 'provider':
        assert not counts


@pytest.mark.parametrize('field,value', [('send_authorization', 'UNREVIEWED'),
    ('total_bot_cap_usd', '2.00'), ('per_question_cap_usd', '0.10'),
    ('retries', 1), ('fallback', 'another-model')])
def test_default_chat_unreviewed_contract_or_limits_rejected(default_chat, monkeypatch, field, value):
    from tools.generation_runner import bot_chat
    c = default_chat
    c.policy['bot_chat'][field] = value
    publish_policy(c, monkeypatch)
    with pytest.raises(ArtifactError):
        bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert not (c.root / bot_chat.BASE / 'submissions').exists()


def test_default_chat_state_is_ready_without_activation_and_refresh_does_nothing(default_chat, monkeypatch):
    from apps.knowledge_preparation import bot_chat as ui
    from tools.generation_runner import bot_chat
    c = default_chat
    monkeypatch.setattr(bot_chat, 'active', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('LEGACY_GATE_USED')))
    before = {p: p.read_bytes() for p in c.root.rglob('*') if p.is_file()}
    state = ui.state(c.root)
    assert state['enabled'] and not state['blocked'] and state['settings']['total_bot_cap_usd'] == '1.00'
    assert ui.state(c.root) == state
    assert {p: p.read_bytes() for p in c.root.rglob('*') if p.is_file()} == before


def test_default_chat_expensive_qualified_request_stops_before_generation(default_chat, monkeypatch):
    test_chat_budget_blocks_after_count_without_generation(default_chat, monkeypatch)


def test_default_chat_prior_unknown_outcome_blocks_next_question(default_chat, monkeypatch):
    test_chat_prior_unknown_billing_blocks_next_send(default_chat, monkeypatch)


def test_default_chat_concurrent_request_is_not_submitted(default_chat, monkeypatch):
    test_chat_busy_admission_never_dispatches_provider(default_chat, monkeypatch)


def test_default_chat_budget_survives_restart_and_cannot_reset(default_chat, monkeypatch):
    from tools.generation_runner import bot_chat
    c = default_chat
    fake_count_provider(c, monkeypatch); fake_generator(c, monkeypatch)
    run = bot_chat.execute(c.root, c.q['question_id'], confirmed=True)
    assert store.read(run / 'RESULT.json')['status'] == 'COMPLETED'
    first = bot_chat.budget_state(c.root, c.policy['bot_chat'])
    assert first['reserved_usd'] != '0'
    assert bot_chat.budget_state(c.root, c.policy['bot_chat']) == first
    with pytest.raises(ArtifactError, match='TOTAL_BUDGET'):
        bot_chat.budget_state(c.root, c.policy['bot_chat'], additional='1.00')
