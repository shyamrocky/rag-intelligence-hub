"""Reuse trusted components. No provider imports or credential access in offline modes."""
import fcntl
import json
import os
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from tools.preflight_suite.artifacts import COMPLETION, now, save, sha, verify_bindings
from tools.quality_dashboard.artifacts import ArtifactError, read_json, safe_path

from .controls import Budget, OfflineAdapter, durable
from .plan import BASE, VERSION, build_plan
from .timing import StageTimer


def persist_question(qdir, record, timer):
    """Seal result writes first; the run manifest subsequently binds the timing sidecar.

    A persistence exception still publishes partial timing if storage permits,
    then propagates unchanged. Never retry or repair a result write.
    """
    try:
        with timer.span('ARTIFACT_PERSISTENCE'):
            save(qdir / 'RESULT.json', record)
            save(qdir / 'QUESTION_RESULT_MANIFEST.json', {
                'schema': 'grounded-generation-question-result-1.0',
                'question_id': record['question_id'], 'run_id': timer.run_id,
                'files': {p.name: sha(p) for p in qdir.iterdir() if p.is_file()}})
    finally:
        timing = timer.finish(request_sha256=record['request_sha256'],
                              package_sha256=record['M8_package_sha256'],
                              usage=record.get('audit', {}).get('usage'))
        save(qdir / 'STAGE_TIMINGS.json', timing)


def implementation(root):
    return {p.relative_to(root).as_posix(): sha(p)
            for p in [*(Path(root) / 'tools/generation_runner').glob('*.py'),
                      *(Path(root) / 'tools/answer_quality').glob('*.py'),
                      Path(root) / 'tools/quality_dashboard/post_generation.py',
                      Path(root) / 'tools/generation/qualifications.py',
                      Path(root) / 'tools/generation_trust_anchor.py'] if p.is_file()}


def authorize(root, plan, path, expected_sha):
    """A local attestation is not a cryptographic signature or blanket permission."""
    file = safe_path(root, path, prefix='workspace')
    if sha(file) != expected_sha:
        raise ArtifactError('OWNER_AUTHORIZATION_HASH_MISMATCH')
    auth = read_json(file)
    if plan.get('question_source') == 'BOT':
        from .bot_consent import verify_publication
        verify_publication(root, path, expected_sha, operation='live')
    return validate_authorization_fields(root, plan, auth)


def validate_authorization_fields(root, plan, auth):
    """Pure native field/preservation checks; does not issue or execute permission."""
    required = {'schema', 'plan_sha256', 'question_ids', 'preflight_sha256', 'requests',
                'implementation_bindings', 'aggregate_cap_usd', 'per_question_caps_usd',
                'owner_statement', 'allow_paid_inference', 'allow_source_transfer',
                'maximum_generation_requests_per_question', 'expires_at',
                'trust_manifest', 'trust_manifest_sha256', 'preservation_receipt'}
    if set(auth) != required:
        raise ArtifactError('NATIVE_AUTHORIZATION_2_REQUIRED_NO_LEGACY_BYPASS')
    expiry = datetime.fromisoformat(auth['expires_at'])
    if (expiry.tzinfo is None or expiry <= datetime.fromisoformat(now())
            or auth.get('schema') != 'grounded-generation-authorization-2.0'
            or auth.get('plan_sha256') != plan['plan_sha256']
            or auth.get('question_ids') != [r['question_id'] for r in plan['questions']]
            or auth.get('implementation_bindings') != implementation(root)
            or auth.get('preflight_sha256') != plan['preflight_sha256']
            or auth.get('aggregate_cap_usd') != plan['aggregate_cap_usd']
            or auth.get('per_question_caps_usd') != {q['question_id']: q['per_question_cap_usd']
                                                   for q in plan['questions']}
            or not isinstance(auth.get('owner_statement'), str) or not auth['owner_statement'].strip()
            or auth.get('allow_paid_inference') is not True
            or auth.get('allow_source_transfer') is not True
            or type(auth.get('maximum_generation_requests_per_question')) is not int
            or auth['maximum_generation_requests_per_question'] != 1):
        raise ArtifactError('EXPLICIT_CURRENT_OWNER_EXECUTION_APPROVAL_REQUIRED')
    from .trust import context, validate_receipt

    if any(auth.get(k) != v for k, v in context(plan).items()):
        raise ArtifactError('AUTHORIZATION_REQUEST_BINDING_MISMATCH')
    validate_receipt(root, plan, auth)
    return auth


@contextmanager
def live_admission(root, enabled):
    # Serialize authorization/history/admission across processes. No offline writes.
    if not enabled:
        yield
        return
    folder = Path(root) / BASE
    if any(p.is_symlink() for p in [folder, *folder.parents]):
        raise ArtifactError('UNSAFE_ADMISSION_DIRECTORY')
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(folder / 'ADMISSION.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _execute(root, *, mode='dry-run', selected=None, cohorts=None, preflight=None,
            per_question_cap='0.03', aggregate_cap='1.00', scenario='success',
            owner_authorization=None, authorization_sha=None, execute_approved_live=False,
            progress=print):
    # Check mode/permission before creating records, loading credentials or clients.
    if mode not in {'dry-run', 'mock', 'live'}:
        raise ValueError('UNKNOWN_RUN_MODE')
    if mode == 'live' and not (owner_authorization and authorization_sha and execute_approved_live):
        raise ValueError('LIVE_BUILD_ONLY_NOT_AUTHORIZED')
    if scenario not in {'success', 'api-failure', 'schema-error'}:
        raise ValueError('UNKNOWN_MOCK_SCENARIO')
    if mode != 'mock' and scenario != 'success':
        raise ValueError('MOCK_SCENARIO_REQUIRES_MOCK_MODE')
    root = Path(root).resolve(strict=True)
    args = {'selected': selected, 'cohorts': cohorts, 'per_question_cap': per_question_cap,
            'aggregate_cap': aggregate_cap}
    if preflight:
        args['preflight'] = preflight
    plan, store, inventory = build_plan(root, **args)
    with live_admission(root, mode == 'live'):
        auth = authorize(root, plan, owner_authorization, authorization_sha) if mode == 'live' else None
        run = root / BASE / (datetime.fromisoformat(now()).strftime('%Y%m%dT%H%M%S')
                              + '-' + mode + '-' + uuid4().hex[:12])
        run.mkdir(parents=True, mode=0o700)
        bindings = dict(store.verified) | implementation(root)
        if auth is not None:
            bindings[owner_authorization] = authorization_sha
            receipt = auth['preservation_receipt']
            bindings[receipt['path']] = receipt['sha256']
            bindings[auth['trust_manifest']] = auth['trust_manifest_sha256']
            durable(root / BASE / 'authorization-use' / (authorization_sha + '.json'),
                    {'run_id': run.name, 'authorization_sha256': authorization_sha,
                     'question_ids': [q['question_id'] for q in plan['questions']]})
        save(run / 'PLAN.json', plan)
        save(run / 'START.json', {'mode': mode, 'created_at': now(), 'generation_authorized': bool(auth),
             'authorization_sha256': authorization_sha if auth else None, 'scenario': scenario})
    rows, budget = [], Budget(run, plan)
    safety_stop = None
    if mode != 'dry-run':
        from tools.answer_quality.validator_abstention import PostGenerationValidator
        from tools.evidence.service import EvidenceService
        from tools.generation.current import GenerationService
        from tools.pre_generation_gate.current import PromptAssemblyGate
        from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA
        from tools.preflight_suite import runner as preparation
        from tools.preflight_suite.runner import (
            assemble,
            configuration,
            equivalence,
            recipe,
            source_transfer_check,
        )

        day = date.today()
        settings, profile, pricing = configuration(root, day=day)
        evidence = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
        gate, validator = PromptAssemblyGate(evidence), PostGenerationValidator(evidence)
        bindings.update(evidence.files)
    for row in plan['questions']:
        qid = row['question_id']
        if safety_stop is not None:
            break
        timer = StageTimer(qid, run.name, mode)
        qdir = run / 'questions' / qid
        request_trace=None
        if row.get('question_source')=='BOT':
            from tools.bot_runtime.trace import RequestTrace
            request_trace=RequestTrace(root,qdir,question_id=qid,run_id=run.name,mode=mode,
                                       question_reference=row['question_reference'])
            request_trace.attach(timer)
            request_trace.emit('OWNER_AUTHORIZATION','COMPLETED' if auth else 'NOT_RUN')
        client, transport = None, None
        record = dict(row, mode=mode, status='PLANNED_NOT_EXECUTED', provider_calls=0,
                      generation_executed=False, semantic_status='NOT_EVALUATED',
                      source_integrity='SEALED_BINDINGS_VERIFIED_NOT_FRESHLY_ASSEMBLED')
        record['stage_timings'] = f'questions/{qid}/STAGE_TIMINGS.json'
        observers = ExitStack()
        try:
            with timer.span('SAVED_INPUT_VERIFICATION'):
                verify_bindings(store, bindings)
            if mode != 'dry-run':
                for owner, method, stage in [
                    (preparation, 'validate_candidates', 'SAVED_INPUT_VERIFICATION'),
                    (evidence, 'assemble', 'M8_EVIDENCE_ASSEMBLY'),
                    (evidence, 'validate', 'M8_SOURCE_VALIDATION'),
                    (gate, 'prepare', 'PROMPT_ASSEMBLY'),
                    (gate, 'validate_preparation', 'PROMPT_ASSEMBLY'),
                ]:
                    observers.enter_context(timer.observe(owner, method, stage))
                with timer.span('SAVED_INPUT_VERIFICATION'):
                    result = store.json(row.get('candidate_artifact', COMPLETION + f'/m7/{qid}.json'))
                if row.get('question_source') == 'BOT':
                    from .bot_source import assemble as source_assemble
                    package, prepared = source_assemble(evidence, gate, inventory[qid], result)
                else:
                    package, prepared = assemble(evidence, gate, inventory[qid], result)
                with timer.span('REQUEST_BINDING_AND_POLICY'):
                    if row.get('question_source') == 'BOT':
                        from .bot_source import recipe as source_recipe
                        reconstructed, request = source_recipe(inventory[qid], result, package, prepared, settings, profile,
                                                               candidate_artifact=row['candidate_artifact'],
                                                               candidate_artifact_sha256=row['candidate_artifact_sha256'])
                    else:
                        reconstructed, request = recipe(inventory[qid], result, package, prepared, settings, profile)
                    previous = store.json(plan['preflight_manifest'].rsplit('/', 1)[0]
                                          + f'/questions/{qid}/REQUEST_PACKAGE.json')
                    equivalence(previous, reconstructed)
                    source_transfer_check(package)
                if mode == 'mock':
                    from tools.generation.response_capture import ResponseCapture
                    capture = ResponseCapture(root, qdir, question_id=qid, run_id=run.name,
                        request_sha256=row['request_sha256'], package_sha256=row['M8_package_sha256'], mode=mode)
                    adapter = OfflineAdapter(row, mode='mock', scenario=scenario, request=request,
                        settings=settings, pricing=pricing, day=day, budget=budget, capture_sink=capture)
                else:
                    from .live import create
                    from .trust import execution_guard
                    guard = lambda: execution_guard(root, plan, auth, owner_authorization, authorization_sha)
                    guard()
                    adapter, client, transport = create(root, qdir, request, row, budget,
                                                         settings, pricing, day, trust_guard=guard)
                service = GenerationService(gate, adapter, settings=settings, pricing=pricing, as_of=day)
                for owner, method, stage in [
                    (service, 'dry_run', 'MODEL_PREFLIGHT'),
                    (adapter, 'verify_model', 'MODEL_METADATA'),
                    (adapter, 'count', 'MODEL_TOKEN_COUNT'),
                    (adapter, 'invoke', 'LLM_GENERATION'),
                ]:
                    observers.enter_context(timer.observe(owner, method, stage))
                with timer.span('GENERATION_SERVICE_OVERHEAD'):
                    outcome = service.generate(prepared, inventory[qid]['question'], package, result,
                        allow_paid_inference=True, allow_source_transfer=True)
                record.update(audit=outcome.audit, response=outcome.response,
                              generation_executed=mode == 'live' and outcome.audit.get('generation_executed', False))
                from tools.generation.observation import persist as persist_observation
                observation = getattr(service, 'last_observation', None)
                if observation is not None:
                    with timer.span('POST_GENERATION_VALIDATION'):
                        record['response_observation'] = persist_observation(root, qdir, observation, row, package,
                            capture=outcome.audit.get('raw_response_capture'))
                from .review_material import retain
                with timer.span('ARTIFACT_PERSISTENCE'):
                    record['review_material'] = retain(root, qdir, row, package, result)
                post = {'status': 'NOT_RUN_NO_VALID_RESPONSE', 'semantic_status': 'PENDING_REVIEW'}
                if observation is not None and outcome.response is None:
                    post = record['response_observation']['field_checks'] | {
                        'overall_status': 'VALIDATION_FAILED', 'structural_validation': 'FAIL',
                        'source_integrity': 'LIVE_M8_VALIDATED',
                        'diagnoses': ['INVALID_RESPONSE_CONTRACT'],
                        'qualification_status': 'QUALIFICATION_APPLICABILITY_UNDETERMINED'}
                if outcome.response is not None:
                    with timer.span('POST_GENERATION_VALIDATION'):
                        post = validator.validate(outcome.response, package, result,
                                                  question=inventory[qid]['question'], request_binding=row)
                record.update(status=outcome.audit['status'], audit=outcome.audit,
                              post_validation=post, response=outcome.response,
                              generation_executed=mode == 'live' and outcome.audit['generation_executed'],
                              mock_invocations=len([c for c in getattr(adapter, 'calls', []) if c == 'generation']),
                              source_integrity='LIVE_M8_VALIDATED',
                              semantic_status='PENDING_REVIEW' if mode == 'live' else 'SYNTHETIC_NOT_SCORED',
                              included_parents=package['counts']['selected_parents'],
                              evidence_BGE_tokens=package['budget']['exact_llm_evidence_tokens'],
                              fixture_only=mode == 'mock')
                if transport:
                    record['provider_calls'] = len(transport.calls)
                with timer.span('ARTIFACT_PERSISTENCE'):
                    save(qdir / 'LOCAL_VALIDATION.json', prepared.audit)
                with timer.span('FINAL_SOURCE_CHECK'):
                    evidence.check()
        except Exception as error:  # noqa: BLE001 - never store publisher/provider exception text
            if request_trace:
                request_trace.error(timer.error_stage or 'EXECUTION',error)
            record.update(status='BLOCKED_OR_FAILED', error_type=type(error).__name__,
                          no_automatic_retry=True)
        finally:
            observers.close()
            if transport is not None:
                record['provider_calls'] = len(transport.calls)
                record['generation_attempted'] = 'GENERATION' in transport.calls
            if client:
                client.close()
        if mode == 'live':
            from tools.generation.response_capture import verify_capture

            from .disposition import disposition
            capture_verified = False
            receipt = record.get('audit', {}).get('raw_response_capture')
            if receipt:
                try:
                    capture_verified = verify_capture(root, receipt, record, run_id=run.name) is not None
                except (ArtifactError, ValueError, KeyError, OSError):
                    capture_verified = False
            decision = disposition(record, row, settings, capture_verified=capture_verified)
            record['batch_disposition'] = decision
            with timer.span('ARTIFACT_PERSISTENCE'):
                save(qdir / 'BATCH_DISPOSITION.json', decision)
            if decision['action'] == 'STOP_SAFETY':
                safety_stop = qid
        persist_question(qdir, record, timer)
        if request_trace:
            request_trace.finish(record['status'],request_sha256=record['request_sha256'],
                                 package_sha256=record['M8_package_sha256'])
        rows.append(record)
        progress(json.dumps({'run_id': run.name, 'question_id': qid, 'mode': mode,
                             'status': record['status'], 'provider_calls': record['provider_calls']}), flush=True)
    verify_bindings(store, bindings)
    save(run / 'RESULTS.json', {'mode': mode, 'questions': rows,
         'selected': len(plan['questions']), 'completed': len(rows),
         'provider_calls': sum(q['provider_calls'] for q in rows),
         'live_generation_calls': sum(q['generation_executed'] for q in rows),
         'live_generation_attempts': sum(q.get('generation_attempted', False) for q in rows),
         'mock_invocations': sum(q.get('mock_invocations', 0) for q in rows),
         'reserved_estimated_usd': str(budget.reserved),
         'planned_outcomes': [{'question_id': q['question_id'],
             'status': 'RECORDED' if q['question_id'] in {r['question_id'] for r in rows}
                       else 'NOT_RUN_SAFETY_STOP', 'stopped_after': safety_stop}
             for q in plan['questions']]})
    manifest = {'schema': VERSION, 'run_id': run.name, 'mode': mode,
                'status': 'SEALED_PENDING_OWNER_REVIEW', 'created_at': now(),
                'plan_sha256': plan['plan_sha256'], 'input_bindings': bindings,
                'question_ids': [r['question_id'] for r in rows],
                'generation_authorized': bool(auth), 'authorization_sha256': authorization_sha if auth else None,
                'files': {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}}
    save(run / 'MANIFEST.json', manifest)
    if mode == 'live':
        from tools.human_review.handoff import after_generation
        after_generation(root, (run / 'MANIFEST.json').relative_to(root).as_posix())
    return run


def execute(root, **kwargs):
    """Offline commands also deny sockets, even if an underlying dependency changes."""
    if kwargs.get('mode', 'dry-run') == 'live':
        return _execute(root, **kwargs)
    from contextlib import ExitStack
    from unittest.mock import patch

    def denied(*args, **kw):
        raise RuntimeError('NETWORK_FORBIDDEN_IN_DRY_RUN_AND_MOCK')

    with ExitStack() as guards:
        for name in ('socket.socket.connect', 'socket.socket.connect_ex',
                     'socket.create_connection', 'socket.getaddrinfo'):
            guards.enter_context(patch(name, denied))
        return _execute(root, **kwargs)
