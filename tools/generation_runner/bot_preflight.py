"""Explicitly consented Bot token/count qualification. No generation endpoint.

Unsigned preparation is safe offline. Execution requires an exact allowlisted
native policy AND a fresh owner source-transfer attestation. Neither enables paid
answering. Live generation later uses the existing native authorization contract.
"""
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from tools.bot_runtime.store import directory, now, seal, write
from tools.preflight_suite.artifacts import sha
from tools.quality_dashboard.artifacts import ArtifactError, Store, digest, safe_path

from .bot_source import QUALIFICATIONS, SCHEMA, inventory_row, local, recipe
from .trust import MAX_AGE_SECONDS, bound, load_trust

AUTH_SCHEMA = 'bot-provider-preflight-consent-1.0'


def context(root, local_manifest):
    from datetime import date

    from tools.generation.openai_adapter import wire_request
    from tools.preflight_suite.runner import configuration
    question, row, payload, _ = local(root, local_manifest)
    settings, profile, pricing = configuration(root, day=date.today())
    request = wire_request(payload['request'], settings, profile)
    ctx = {'question_id':question['question_id'], 'question_reference':row['question_reference'],
        'local_manifest':local_manifest, 'local_manifest_sha256':sha(Path(root)/local_manifest),
        'question_sha256':question['question_sha256'], 'M7_result_sha256':row['M7_result_sha256'],
        'M8_package_sha256':row['M8_package_sha256'], 'request_sha256':digest(request),
        'settings_sha256':digest(settings.model_dump()), 'profile_sha256':digest(profile),
        'pricing_sha256':digest(pricing),
        'count_payload_sha256':digest({k:request[k] for k in ('model','input','text','reasoning','truncation')}), 'model':settings.model,
        'prompt_version':settings.prompt_version,'response_schema':settings.response_schema}
    return ctx, request, (settings,profile,pricing)


def policy_check(root, ctx, trust_manifest, trust_sha):
    _, policy, preservation = load_trust(root,trust_manifest,trust_sha)
    if ctx not in policy.get('bot_provider_preflight_allowlist', []):
        from .bot_chat import check_context
        check_context(root, ctx, policy)
    return preservation


def prepare(root, local_manifest, output, *, trust_manifest, trust_sha):
    """Only unsigned templates. Never obtains evidence-transfer or paid permission."""
    from .runner import implementation
    if not output.startswith('workspace/') or '..' in output.split('/'):
        raise ArtifactError('PRIVATE_PREFLIGHT_PREPARATION_REQUIRED')
    if (Path(root)/output).exists():
        raise ArtifactError('NEW_PREPARATION_DIRECTORY_REQUIRED')
    ctx,_,_ = context(root,local_manifest)
    preservation = policy_check(root,ctx,trust_manifest,trust_sha)
    folder=directory(root,output)
    receipt={'schema':'bot-preservation-receipt-1.0','created_at':now(),
        'context':ctx,'trust_manifest':trust_manifest,'trust_sha256':trust_sha,
        'preservation':preservation,'generation_authority':False}
    write(folder/'PRESERVATION.json',receipt)
    template={'schema':AUTH_SCHEMA,'context':ctx,'trust_manifest':trust_manifest,
        'trust_sha256':trust_sha,'implementation_bindings':implementation(root),
        'preservation_receipt':{'path':output+'/PRESERVATION.json','sha256':sha(folder/'PRESERVATION.json')},
        'owner_statement':'','allow_source_transfer':False,'allow_provider_preflight':False,
        'allow_paid_inference':False,'maximum_metadata_calls':1,'maximum_token_count_calls':1,
        'retries':0,'expires_at':'1970-01-01T00:00:00+00:00'}
    write(folder/'PREFLIGHT_CONSENT_TEMPLATE.json',template)
    seal(folder,'bot-unsigned-preflight-preparation-1.0',generation_authority=False)
    return folder


def validate(root, local_manifest, path, expected):
    from .bot_consent import verify_publication
    safe_path(root,path,prefix='workspace')
    auth=bound(root,path,expected)
    verify_publication(root,path,expected,operation='model-preflight')
    return validate_value(root,local_manifest,auth)


def validate_value(root, local_manifest, auth):
    from .runner import implementation
    required={'schema','context','trust_manifest','trust_sha256','implementation_bindings',
        'preservation_receipt','owner_statement','allow_source_transfer','allow_provider_preflight',
        'allow_paid_inference','maximum_metadata_calls','maximum_token_count_calls','retries','expires_at'}
    if (set(auth)!=required or auth['schema']!=AUTH_SCHEMA
            or auth['allow_source_transfer'] is not True or auth['allow_provider_preflight'] is not True
            or auth['allow_paid_inference'] is not False or not isinstance(auth['owner_statement'],str)
            or not auth['owner_statement'].strip() or auth['maximum_metadata_calls']!=1
            or type(auth['maximum_metadata_calls']) is not int or auth['maximum_token_count_calls']!=1
            or type(auth['maximum_token_count_calls']) is not int or auth['retries']!=0
            or type(auth['retries']) is not int or auth['implementation_bindings']!=implementation(root)):
        raise ArtifactError('EXPLICIT_BOT_PREFLIGHT_ONLY_CONSENT_REQUIRED')
    expiry=datetime.fromisoformat(auth['expires_at']); current=datetime.fromisoformat(now())
    if expiry.tzinfo is None or not current < expiry <= current+timedelta(seconds=MAX_AGE_SECONDS):
        raise ArtifactError('STALE_OR_UNBOUNDED_BOT_PREFLIGHT_CONSENT')
    ctx,request,config=context(root,local_manifest)
    if auth['context']!=ctx:
        raise ArtifactError('BOT_PREFLIGHT_CONSENT_REQUEST_CHANGED')
    ref=auth['preservation_receipt'];safe_path(root,ref['path'],prefix='workspace')
    receipt=bound(root,ref['path'],ref['sha256'])
    created=datetime.fromisoformat(receipt['created_at'])
    if created.tzinfo is None or not 0 <= (current-created).total_seconds() <= MAX_AGE_SECONDS:
        raise ArtifactError('STALE_BOT_PRESERVATION_RECEIPT')
    preservation=policy_check(root,ctx,auth['trust_manifest'],auth['trust_sha256'])
    expected_receipt={'schema':'bot-preservation-receipt-1.0','created_at':receipt['created_at'],
        'context':ctx,'trust_manifest':auth['trust_manifest'],'trust_sha256':auth['trust_sha256'],
        'preservation':preservation,'generation_authority':False}
    if receipt!=expected_receipt:
        raise ArtifactError('BOT_PREFLIGHT_PRESERVATION_CHANGED')
    return auth,ctx,request,config


def execute(root, local_manifest, consent, consent_sha):
    """One metadata + one count. Failed/interrupted grants cannot be replayed."""
    root=Path(root).resolve(strict=True)
    _auth,ctx,_request,config=validate(root,local_manifest,consent,consent_sha)
    from .bot_source import assemble
    from .runner import live_admission
    settings,profile,pricing=config
    qid=ctx['question_id']
    with live_admission(root,True):
        # Serialize and reserve BEFORE credentials. This is preflight consumption,
        # never a LIVE_ATTEMPT or generation authorization.
        claims=directory(root,QUALIFICATIONS+'/claims')
        uses=directory(root,QUALIFICATIONS+'/consent-use')
        write(claims/(qid+'.json'),{'question_id':qid,'consent_sha256':consent_sha,'local_manifest':local_manifest})
        write(uses/(consent_sha+'.json'),{'question_id':qid,'created_at':now()})
        run=directory(root,QUALIFICATIONS+'/qualification-'+uuid4().hex)
        write(run/'START.json',{'mode':'model-preflight','question_id':qid,'consent_sha256':consent_sha,
                                'created_at':now(),'context':ctx,'consent_reference':{'path':consent,'sha256':consent_sha},'generation_authorized':False})
    client=transport=None
    from tools.bot_runtime.trace import RequestTrace
    trace=RequestTrace(root,run,question_id=qid,run_id=run.name,mode='model-preflight',
                       question_reference=ctx['question_reference'])
    trace.emit('OWNER_AUTHORIZATION','COMPLETED',operation='Exact source-transfer-only consent verified')
    value={'question_id':qid,'question_reference':ctx['question_reference'],'status':'BLOCKED',
           'input_tokens':None,'maximum_cost_usd':None,'generation_executed':False,'provider_calls':0}
    audit={'status':'NOT_RUN','blocking_reasons':['PREFLIGHT_NOT_COMPLETED']}
    reconstruction={'status':'UNAVAILABLE'}
    try:
        from tools.evidence.service import EvidenceService
        from tools.generation.current import GenerationService
        from tools.pre_generation_gate.current import PromptAssemblyGate
        from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA
        from tools.preflight_suite.provider import adapter
        from tools.preflight_suite.runner import source_transfer_check
        question=inventory_row(root,qid)
        base=local_manifest.rsplit('/',1)[0]
        store=Store(root);store.manifest(local_manifest)
        result=store.json(base+'/CANDIDATES.json')
        with trace.span('SERVICE_BINDING_CHECK'):
            evidence=EvidenceService(root,selector=M8_SELECTOR,selector_sha256=M8_SHA)
            gate=PromptAssemblyGate(evidence)
        with ExitStack() as observations:
            for owner,method,stage in [(evidence,'assemble','M8_EVIDENCE_ASSEMBLY'),
                    (evidence,'validate','M8_SOURCE_VALIDATION'),(gate,'prepare','PROMPT_ASSEMBLY')]:
                observations.enter_context(trace.observe(owner,method,stage))
            package,prepared=assemble(evidence,gate,question,result)
        reconstruction,wire=recipe(question,result,package,prepared,settings,profile,
                                   candidate_artifact=base+'/CANDIDATES.json',
                                   candidate_artifact_sha256=store.verified[base+'/CANDIDATES.json'])
        if digest(package)!=ctx['M8_package_sha256'] or digest(wire)!=ctx['request_sha256']:
            raise ArtifactError('BOT_FRESH_EVIDENCE_OR_REQUEST_CHANGED')
        source_transfer_check(package)
        validate(root,local_manifest,consent,consent_sha)
        safe,client,transport=adapter(root,run,wire,settings.timeout_seconds)
        # The existing transport enforces exact endpoints/bodies/one attempt each.
        # Recheck native consent/preservation at each adapter operation as well.
        original_metadata,original_count=safe.verify_model,safe.count
        def metadata(*a,**kw):
            with trace.span('MODEL_METADATA'):
                validate(root,local_manifest,consent,consent_sha)
                return original_metadata(*a,**kw)
        def count(*a,**kw):
            with trace.span('MODEL_TOKEN_COUNT'):
                validate(root,local_manifest,consent,consent_sha)
                return original_count(*a,**kw)
        safe.verify_model,safe.count=metadata,count
        from datetime import date
        service=GenerationService(gate,safe,settings=settings,pricing=pricing,as_of=date.today())
        outcome=service.dry_run(prepared,question['question'],package,result,
                               allow_provider_preflight=True,allow_source_transfer=True)
        audit=outcome.audit
        value.update(status='MODEL_QUALIFIED' if audit['status']=='READY' else audit['status'],
            input_tokens=audit.get('generator_input_tokens'),
            maximum_cost_usd=audit.get('cost_estimate',{}).get('estimated_max_cost_usd'),
            request_sha256=ctx['request_sha256'],context_fit=audit.get('context_fit'))
        evidence.check()
    except Exception as error:  # noqa: BLE001 - private source/provider text stays out of telemetry
        trace.error('MODEL_PREFLIGHT',error)
        value.update(status='BLOCKED',error_type=type(error).__name__)
    finally:
        if client:
            client.close()
    value['provider_calls']=len(transport.receipts) if transport else 0
    qdir=directory(root,run.relative_to(root).as_posix()+f'/questions/{qid}')
    with trace.span('ARTIFACT_PERSISTENCE'):
        write(qdir/'REQUEST_PACKAGE.json',reconstruction)
        write(run/'MODEL_PREFLIGHT.json',audit)
        write(run/'RESULT.json',value)
        write(run/'PROVIDER_CALLS.json',transport.receipts if transport else [])
    trace.finish(value['status'],request_sha256=ctx['request_sha256'],package_sha256=ctx['M8_package_sha256'])
    # Standard Store manifests use recursive project-relative children.
    write(run/'MANIFEST.json',{'schema':SCHEMA,'question_id':qid,'mode':'model-preflight',
        'generation_authorized':False,'created_at':now(),
        'files':{p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file()}})
    return run
