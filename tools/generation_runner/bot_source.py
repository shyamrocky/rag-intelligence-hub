"""Bot source resolution for the SAME native runner and existing review workflow."""
from pathlib import Path

from tools.bot_runtime.store import ID, question_record, reference, verify_reference
from tools.preflight_suite.artifacts import CONFIG
from tools.quality_dashboard.artifacts import ArtifactError, Store, digest

QUALIFICATIONS = 'data/runtime-qualifications/v1'
SCHEMA = 'bot-model-qualification-1.0'


def local(root, manifest_path):
    """Read a sealed real local package. Never qualify a simulation or detached text."""
    from tools.bot_runtime.projection import discover
    data = discover(root)
    if data['rejected']:
        raise ArtifactError('UNVERIFIED_BOT_HISTORY')
    for record in data['records'].values():
        for row in record['attempts']:
            if row.get('manifest_path') != manifest_path:
                continue
            if (row['mode'] != 'local-check' or row.get('fixture_only')
                    or row.get('source_integrity') != 'LIVE_M8_VALIDATED'
                    or row.get('application_outcome') != 'LOCAL_ASSEMBLED_NOT_MODEL_QUALIFIED'):
                raise ArtifactError('REAL_LOCAL_BOT_CHECK_REQUIRED')
            store = Store(root)
            store.manifest(manifest_path, schema='runtime-execution-1.0')
            base = manifest_path.rsplit('/', 1)[0]
            value = store.json(base + '/REQUEST_PACKAGE.json')
            if digest(value['request']) != row['request_sha256']:
                raise ArtifactError('BOT_LOCAL_REQUEST_CHANGED')
            question = verify_reference(root, row['question_id'], row['question_reference'])
            return question, row, value, store
    raise ArtifactError('BOT_LOCAL_CHECK_NOT_FOUND')


def assemble(evidence, gate, question, result):
    from tools.evidence.contract import validate_candidates
    if (question['question_sha256'] != result['query_sha256']
            or result['retrieval_mode'] != 'hybrid'
            or result['parameters'] != {k:v for k,v in CONFIG.items() if k not in {'mode','M8_BGE_budget'}}
            or not 0 <= len(result['candidates']) <= 30):
        raise ArtifactError('BOT_CANDIDATE_CONFIGURATION_CHANGED')
    validate_candidates(result, evidence.m7, evidence.inventory)
    package = evidence.assemble(result, token_budget=128000)
    prepared = gate.prepare(question['question'], package, result, model_configuration=None)
    if (prepared.payload is None or prepared.audit['source_integrity'] != 'LIVE_M8_VALIDATED'
            or prepared.audit['blocking_reasons'] != ['NO_OWNER_AUTHORIZED_GENERATOR_CONFIGURATION']):
        raise ArtifactError('BOT_FRESH_PREPARATION_BLOCKED')
    return package, prepared


def recipe(question, result, package, prepared, settings, profile, *, candidate_artifact, candidate_artifact_sha256):
    from tools.preflight_suite.runner import recipe as historical_recipe
    value, request = historical_recipe(question, result, package, prepared, settings, profile)
    value.update(schema='bot-request-reconstruction-1.0', question_source='BOT',
                 question_reference=question['question_reference'], candidate_artifact=candidate_artifact,
                 candidate_artifact_sha256=candidate_artifact_sha256)
    return value, request


def inventory_row(root, qid):
    return question_record(root, qid) | {'question_reference': reference(root, qid)}


def build_plan(root, *, selected=None, cohorts=None, preflight=None,
               per_question_cap=None, aggregate_cap=None, as_of=None, check_history=True):
    """Native plan shape, existing cost arithmetic; no paid execution authorization."""
    from datetime import date
    from decimal import Decimal

    from tools.generation.profiles import check_fit
    from tools.generation.telemetry import estimate_max_cost
    from tools.preflight_suite.artifacts import sha
    from tools.preflight_suite.runner import configuration

    from .plan import VERSION, money
    from .trust import history
    if (cohorts or not selected or len(selected) != 1 or not ID.fullmatch(selected[0])
            or not preflight or not preflight.startswith(QUALIFICATIONS + '/')
            or not per_question_cap or not aggregate_cap):
        raise ArtifactError('EXACT_SINGLE_BOT_AND_EXPLICIT_CAPS_REQUIRED')
    store = Store(root)
    manifest, observation, model, request = validate_qualification(root, preflight, store)
    qid = selected[0]
    if (manifest.get('question_id') != qid or observation['status'] != 'MODEL_QUALIFIED'
            or observation.get('generation_executed') is not False):
        raise ArtifactError('BOT_MODEL_QUALIFICATION_REQUIRED')
    question = inventory_row(root, qid)
    if observation['question_reference'] != question['question_reference']:
        raise ArtifactError('BOT_QUALIFICATION_QUESTION_CHANGED')
    store.bind(request['candidate_artifact'], request['candidate_artifact_sha256'])
    if digest(store.json(request['candidate_artifact'])) != request['M7_result_sha256']:
        raise ArtifactError('BOT_CANDIDATE_LOGICAL_IDENTITY_CHANGED')
    day = as_of or date.today()
    settings, profile, pricing = configuration(root, day=day)
    if request['settings_sha256'] != digest(settings.model_dump()) or request['profile_sha256'] != digest(profile):
        raise ArtifactError('BOT_MODEL_OR_SETTINGS_CHANGED')
    cost = estimate_max_cost(settings.model, observation['input_tokens'], settings.max_output_tokens,
                            pricing, tier=settings.service_tier, region=settings.region, as_of=day)
    fit = check_fit(profile, settings, observation['input_tokens'])
    if not fit['fits'] or cost['status'] != 'ESTIMATED_MAX_API_COST' or cost != model['cost_estimate']:
        raise ArtifactError('BOT_FRESH_CONTEXT_OR_PRICE_REQUIRED')
    cap, aggregate = money(per_question_cap), money(aggregate_cap)
    maximum = money(cost['estimated_max_cost_usd'])
    if maximum > cap or maximum > aggregate:
        raise ArtifactError('BOT_COST_CAP_EXCEEDED')
    if check_history:
        history(root, [qid])  # Includes unsealed native attempts and permanent reservations.
    row = {'question_id':qid, 'question_source':'BOT', 'cohort_id':None,
        'question_reference':question['question_reference'], 'candidate_artifact':request['candidate_artifact'],
        'candidate_artifact_sha256':request['candidate_artifact_sha256'],
        'question_sha256':question['question_sha256'],
        **{k:request[k] for k in ('M7_result_sha256','M8_package_sha256','request_sha256')},
        'input_tokens':observation['input_tokens'], 'context_fit':fit,
        'maximum_cost_usd':str(maximum), 'per_question_cap_usd':str(cap),
        'readiness':'SEALED_PREFLIGHT_VERIFIED_FRESH_EXECUTION_CHECKS_REQUIRED'}
    plan = {'schema':VERSION, 'question_source':'BOT', 'preflight_manifest':preflight,
        'preflight_sha256':sha(Path(root)/preflight), 'created_for_date':day.isoformat(), 'questions':[row],
        'model':settings.model,'prompt_version':settings.prompt_version,'response_schema':settings.response_schema,
        'pricing_version':pricing['version'],'settings_sha256':digest(settings.model_dump()),
        'profile_sha256':digest(profile),'pricing_sha256':digest(pricing),
        'aggregate_cap_usd':str(aggregate),'aggregate_maximum_estimated_cost_usd':str(Decimal(maximum)),
        'expected_future_calls':{'model_metadata':1,'token_count':1,'generation_maximum':1,'retries':0},
        'generation_authorized':False,'Q05_excluded':True,'evidence_completeness_used_for_selection':False}
    # Only a verified Send under a currently enabled native chat policy can use
    # dynamic question scope. Legacy exact-question plans retain their old shape.
    if (Path(root) / 'data/runtime-chat/v1/submissions' / qid).exists():
        from tools.bot_runtime.trust import verify_implementation

        from .bot_chat import submission
        from .trust import load_trust
        ref = verify_implementation(root)
        _, policy, _ = load_trust(root, ref['path'], ref['sha256'])
        send = submission(root, qid, policy, trust_ref=ref)
        plan['chat_submission'] = send['reference']
    plan['plan_sha256']=digest(plan)
    return plan,store,{qid:question}


def validate_qualification(root, manifest_path, store=None):
    """Verify historical qualification provenance without provider calls or expiry waiver.

    Fresh source/model/count/pricing checks are still required by native live mode.
    This validates the original transfer-only consent and exact provider observations.
    """
    from .bot_consent import verify_publication
    from .trust import TRUSTED_BASELINES, bound
    store=store or Store(root)
    m=store.manifest(manifest_path,schema=SCHEMA)
    base=manifest_path.rsplit('/',1)[0]
    row=store.json(base+'/RESULT.json');start=store.json(base+'/START.json')
    audit=store.json(base+'/MODEL_PREFLIGHT.json');calls=store.json(base+'/PROVIDER_CALLS.json')
    ctx=start['context'];ref=start['consent_reference']
    auth=verify_publication(root,ref['path'],ref['sha256'],operation='model-preflight')
    if (TRUSTED_BASELINES.get(auth['trust_manifest'])!=auth['trust_sha256']
            or auth['context']!=ctx or auth['allow_source_transfer'] is not True
            or auth['allow_provider_preflight'] is not True or auth['allow_paid_inference'] is not False
            or auth['maximum_metadata_calls']!=1 or auth['maximum_token_count_calls']!=1 or auth['retries']!=0):
        raise ArtifactError('UNTRUSTED_BOT_QUALIFICATION_CONSENT')
    trust_manifest=bound(root,auth['trust_manifest'],auth['trust_sha256'])
    policy_base=auth['trust_manifest'].rsplit('/',1)[0]
    policy=bound(root,policy_base+'/POLICY.json',trust_manifest['files']['POLICY.json'])
    if ctx not in policy.get('bot_provider_preflight_allowlist',[]):
        from .bot_chat import historical_context
        historical_context(root, ctx, policy, auth['trust_manifest'], auth['trust_sha256'])
    store.manifest(ctx['local_manifest'],expected=ctx['local_manifest_sha256'],schema='runtime-execution-1.0')
    local_base=ctx['local_manifest'].rsplit('/',1)[0]
    saved=store.json(local_base+'/RESULT.json')
    if saved['M8_package_sha256']!=ctx['M8_package_sha256'] or saved['M7_result_sha256']!=ctx['M7_result_sha256']:
        raise ArtifactError('QUALIFIED_BOT_LOCAL_SOURCE_CHANGED')
    preserved=bound(root,auth['preservation_receipt']['path'],auth['preservation_receipt']['sha256'])
    if preserved['context']!=ctx or preserved['trust_manifest']!=auth['trust_manifest']:
        raise ArtifactError('QUALIFIED_BOT_PRESERVATION_CHANGED')
    qid=row['question_id'];verify_reference(root,qid,row['question_reference'])
    request=store.json(base+f'/questions/{qid}/REQUEST_PACKAGE.json')
    if request['candidate_artifact']!=local_base+'/CANDIDATES.json' or request['candidate_artifact_sha256']!=store.verified[request['candidate_artifact']]:
        raise ArtifactError('QUALIFIED_BOT_CANDIDATE_REFERENCE_CHANGED')
    token=audit.get('token_count_receipt',{})
    if (m['question_id']!=qid or start['question_id']!=qid or ctx['question_id']!=qid
            or row['question_reference']!=ctx['question_reference'] or row['status']!='MODEL_QUALIFIED'
            or row['generation_executed'] is not False or audit.get('generation_executed') is not False
            or audit.get('status')!='READY' or audit.get('model_access')!='ACCOUNT_MODEL_ACCESS_VERIFIED'
            or audit.get('source_integrity')!='LIVE_M8_VALIDATED'
            or token.get('method')!='OPENAI_RESPONSES_INPUT_TOKENS'
            or token.get('request_sha256')!=ctx['request_sha256']
            or token.get('count_payload_sha256')!=ctx['count_payload_sha256']
            or token.get('includes_messages_framing_and_response_schema') is not True
            or type(token.get('input_tokens')) is not int or token['input_tokens']<0
            or row['input_tokens']!=token['input_tokens'] or audit.get('generator_input_tokens')!=token['input_tokens']
            or row.get('request_sha256')!=ctx['request_sha256'] or audit.get('request_sha256')!=ctx['request_sha256']
            or any(request.get(k)!=ctx[k] for k in ('question_reference','request_sha256','M7_result_sha256','M8_package_sha256','settings_sha256','profile_sha256'))
            or row['provider_calls']!=2 or len(calls)!=2
            or {(c['method'],c['endpoint']) for c in calls}!={('GET','/v1/models/'+ctx['model']),('POST','/v1/responses/input_tokens')}):
        raise ArtifactError('BOT_QUALIFICATION_RECEIPTS_INCONSISTENT')
    return m,row,audit,request
