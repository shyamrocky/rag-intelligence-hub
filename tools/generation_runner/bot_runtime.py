"""Native Bot source orchestration. Offline/local modes only; live is fail-closed.

Reuses accepted services. No provider import, credential loading or paid caller.
The UI and backend CLI both dispatch this module in the generation environment.
"""
import copy
from contextlib import ExitStack, contextmanager
from datetime import date
from pathlib import Path
from uuid import uuid4

from tools.bot_runtime.store import (
    RUNS,
    directory,
    locked,
    now,
    reference,
    seal,
    verify_reference,
    write,
)
from tools.quality_dashboard.artifacts import digest

from .bot_timing import BotTimer


@contextmanager
def observe_native(retriever, trace=None):
    """Instance-only observation: identical public search, no extra query or re-fusion."""
    original = retriever._request
    observations = {}
    def observed(kind, request):
        if trace is None:
            value = original(kind, request)
        else:
            with trace.span('SEARCH_WORKER',operation=kind+' worker initialization/request'):
                value = original(kind, request)
        if kind in {'bm25', 'vector'}:
            if kind in observations:
                raise ValueError('UNEXPECTED_DUPLICATE_NATIVE_SEARCH')
            observations[kind] = copy.deepcopy(value['result'])
        return value
    retriever._request = observed
    try:
        yield observations
    finally:
        del retriever._request


def local_services(root):
    from tools.evidence.contract import M7_SELECTOR, M7_SHA
    from tools.evidence.service import EvidenceService
    from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA
    from tools.retrieval.service import RetrievalService
    retrieval = RetrievalService(root, selector=M7_SELECTOR, selector_sha256=M7_SHA)
    try:
        evidence = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
    except Exception:
        retrieval.close()
        raise
    return retrieval, evidence


def execute(root, qid, *, mode, scenario='abstained'):
    # No path/hash/name can turn this reviewed offline capability into paid authority.
    if mode not in {'local-check', 'mock'}:
        raise ValueError('BOT_LIVE_REQUIRES_SEPARATE_NATIVE_POLICY_AND_OWNER_BUDGET_APPROVAL')
    if mode != 'mock' and scenario != 'abstained':
        raise ValueError('SCENARIO_REQUIRES_MOCK_MODE')
    root = Path(root).resolve(strict=True)
    from tools.bot_runtime.store import question_record
    question = question_record(root, qid)
    from tools.bot_runtime.trust import verify_implementation
    trust_ref = verify_implementation(root)
    qref = reference(root, qid)
    run_id = 'bot-' + uuid4().hex
    base = directory(root, RUNS)
    # Each ID is one submission, no replay/retry even after interruption. New local
    # check/mock executions require an explicit new submission/nonce.
    with locked(base):
        claimdir = directory(root, RUNS + '/claims')
        write(claimdir / (qid + '-' + mode + '.json'), {'question_id': qid, 'run_id': run_id, 'mode': mode, 'question_reference': qref})
        run = directory(root, RUNS + '/' + run_id)
        write(run / 'START.json', {'schema': 'runtime-start-1.0', 'question_id': qid,
            'question_reference': qref, 'mode': mode, 'run_id': run_id, 'created_at': now(),
            'generation_authorized': False, 'trust': trust_ref})
    timer = BotTimer(qid, run_id, mode)
    from tools.bot_runtime.trace import RequestTrace, failure
    trace=RequestTrace(root,run,question_id=qid,run_id=run_id,mode=mode,question_reference=qref)
    trace.attach(timer)
    from tools.answer_quality.current import policy_reference
    validation_policy = policy_reference(Path(__file__).resolve().parents[2])
    row = {'validation_policy': validation_policy, 'validation_policy_sha256': validation_policy['sha256'],
        'schema': 'runtime-question-result-1.0', 'question_id': qid,
        'question_reference': qref, 'question_sha256': question['question_sha256'],
        'question_source': 'BOT', 'run_id': run_id, 'mode': mode, 'fixture_only': mode == 'mock',
        'execution_status': 'PREPARING', 'application_outcome': None, 'model_status': None,
        'response_contract_status': 'NOT_RUN', 'validation_status': 'NOT_RUN',
        'semantic_status': 'NOT_EVALUATED', 'owner_review_status': 'PENDING_REVIEW',
        'generation_executed': False, 'provider_calls': 0, 'generation_calls': 0,
        'response': None, 'audit': {}, 'post_validation': None, 'failure_stage': None,
        'diagnostics': [], 'usage': None, 'cost_usd': None, 'request_sha256': None,
        'M7_result_sha256': None, 'M8_package_sha256': None,
        'source_integrity': 'NOT_CHECKED', 'trust': trust_ref}
    retriever = None
    stage = 'LIVE_RETRIEVAL'
    try:
        from tools.pre_generation_gate.current import PromptAssemblyGate
        with timer.span(stage):
            if mode == 'mock':
                from .bot_fixture import boundaries
                result, evidence = boundaries(question['question'], scenario)
                native = {'status': 'SYNTHETIC_SERVICE_BOUNDARY', 'lists': None}
            else:
                with trace.span('SERVICE_BINDING_CHECK',operation='Source/index/evidence service initialization'):
                    retriever, evidence = local_services(root)
                with observe_native(retriever,trace) as lists:
                    result = retriever.search(question['question'], mode='hybrid', top_k=30,
                                              candidate_depth=50, rrf_k=60)
                native = {'status': 'MEASURED' if set(lists) == {'bm25', 'vector'} else 'UNAVAILABLE',
                          'lists': lists if set(lists) == {'bm25', 'vector'} else None}
            if result['query_sha256'] != question['question_sha256']:
                raise ValueError('RETRIEVAL_QUESTION_BINDING_CHANGED')
            if mode == 'mock':
                row['measurement_kind'] = 'OWNED_SYNTHETIC_NOT_SOURCE_AUTHORITY'
            row['M7_result_sha256'] = digest(result)
            write(run / 'CANDIDATES.json', result)
            write(run / 'RETRIEVAL_OBSERVATIONS.json', native)
            trace.emit('RETRIEVAL_COUNTS','COMPLETED',detail={'selected_chunks':len(result['candidates']),
                'bm25_candidates':len(lists['bm25']) if mode!='mock' and 'bm25' in lists else None,
                'vector_candidates':len(lists['vector']) if mode!='mock' and 'vector' in lists else None})
        stage = 'M8_EVIDENCE_ASSEMBLY'
        with timer.span(stage):
            package = evidence.assemble(result, token_budget=128000)
        stage = 'M8_SOURCE_VALIDATION'
        with timer.span(stage):
            if evidence.validate(package, result) is not True:
                raise ValueError('SOURCE_VALIDATION_NOT_CONFIRMED')
        row['evidence_summary'] = {'counts': package['counts'], 'budget': package['budget'],
            'included_evidence_unit_ids': [p['evidence']['unit_id'] for p in package['parents']],
            'omitted': package.get('diagnostics', {}).get('omitted', []),
            'candidate_to_evidence': package.get('diagnostics', {}).get('deduplicated', [])}
        row['M8_package_sha256'] = digest(package)
        trace.emit('EVIDENCE_COUNTS','COMPLETED',detail={'included_units':package['counts'].get('selected_parents'),
            'excluded_units':package['counts'].get('omitted_parents'),
            'evidence_BGE_tokens':package['budget'].get('exact_llm_evidence_tokens')})
        row['source_integrity'] = 'OWNED_SYNTHETIC_NOT_SOURCE_AUTHORITY' if mode == 'mock' else 'LIVE_M8_VALIDATED'
        # Protected evidence has the same private permissions as raw captures.
        write(run / 'EVIDENCE_PACKAGE.json', package)
        stage = 'PROMPT_ASSEMBLY'
        with timer.span(stage):
            gate = PromptAssemblyGate(evidence)
            prepared = gate.prepare(question['question'], package, result, model_configuration=None)
        write(run / 'LOCAL_VALIDATION.json', prepared.audit if mode != 'mock' else prepared.audit | {
            'source_integrity': 'OWNED_SYNTHETIC_NOT_SOURCE_AUTHORITY', 'fixture_only': True})
        trace.emit('PROMPT_GATE','BLOCKED' if prepared.payload is None else 'COMPLETED')
        if prepared.payload is None:
            row.update(execution_status='BLOCKED', diagnostics=prepared.audit['blocking_reasons'])
            if 'NO_INCLUDED_AUTHORIZED_EVIDENCE' in row['diagnostics']:
                row['application_outcome'] = 'INSUFFICIENT_EVIDENCE'
        else:
            row['request_sha256'] = prepared.audit['request_sha256']
            write(run / 'REQUEST_PACKAGE.json', prepared.payload)
            row.update(execution_status='AWAITING_AUTHORIZATION', application_outcome='LOCAL_ASSEMBLED_NOT_MODEL_QUALIFIED')
            if mode == 'mock':
                stage = 'MODEL_PREFLIGHT'
                _mock(root, run, row, question, result, package, prepared, gate, evidence, timer, scenario)
        stage = 'FINAL_SOURCE_CHECK'
        with timer.span(stage):
            evidence.check()
            if retriever:
                retriever.check()
            verify_reference(root, qid, qref)
            verify_implementation(root)
    except Exception as error:  # noqa: BLE001 - never echo arbitrary source/private exception text
        trace.error(stage,error)
        row.update(execution_status='FAILED', failure_stage=stage,
                   diagnostics=['BOT_STAGE_FAILED_' + type(error).__name__],
                   failure_code=failure(error,root)['error_code'])
    finally:
        if retriever:
            retriever.close()
    # A write failure leaves START and the durable claim. Discovery reports
    # INCOMPLETE/RECOVERY_REQUIRED, never silently reruns the question.
    try:
        with timer.span('ARTIFACT_PERSISTENCE'):
            write(run / 'RESULT.json', row)
    finally:
        # Preserve partial source-free accounting if result persistence fails;
        # absence of the completion seal still prevents treating it as complete.
        timing = timer.finish(row['request_sha256'], row['M8_package_sha256'])
        write(run / 'STAGE_TIMINGS.json', timing)
    trace.finish(row['execution_status'],request_sha256=row['request_sha256'],package_sha256=row['M8_package_sha256'])
    seal(run, 'runtime-execution-1.0', run_id=run_id, question_id=qid, mode=mode,
         generation_authority=False, created_at=now())
    return run


def _mock(root, run, row, question, result, package, prepared, gate, evidence, timer, scenario):
    from tools.answer_quality.validator_abstention import PostGenerationValidator
    from tools.generation.current import GenerationService, load_settings, resolve
    from tools.generation.openai_adapter import wire_request
    from tools.generation.response_capture import ResponseCapture
    from tools.generation.telemetry import load_pricing

    from .bot_fixture import answer
    from .controls import Budget, OfflineAdapter

    day = date.today()
    settings = load_settings()
    profile, pricing = resolve(settings, as_of=day), load_pricing()
    request = wire_request(prepared.payload['request'], settings, profile)
    row['request_sha256'] = digest(request)
    # Synthetic counts are never presented as real preflight or billing observations.
    planrow = {'question_id': row['question_id'], 'input_tokens': 100,
        'per_question_cap_usd': '0.03', 'maximum_cost_usd': '0.03', 'request_sha256': digest(request)}
    budget = Budget(run, {'aggregate_cap_usd': '0.03', 'questions': [planrow]})
    capture = ResponseCapture(root, run, question_id=row['question_id'], run_id=row['run_id'],
                              request_sha256=digest(request), package_sha256=digest(package), mode='mock')
    class SyntheticAdapter(OfflineAdapter):
        def count(self, request):
            return super().count(request) | {'method': 'OWNED_SYNTHETIC_NOT_PROVIDER_COUNTED'}
        def verify_model(self, model):
            return super().verify_model(model) | {'status': 'OWNED_MOCK_NOT_PROVIDER_VERIFIED'}
    write(run / 'WIRE_REQUEST.json', request)
    adapter = SyntheticAdapter(planrow, mode='mock', scenario=scenario if scenario in {'api-failure', 'schema-error'} else 'success',
        request=request, settings=settings, pricing=pricing, day=day, budget=budget,
        answer=answer(scenario), capture_sink=capture)
    service = GenerationService(gate, adapter, settings=settings, pricing=pricing, as_of=day)
    with ExitStack() as stack:
        for owner, method, name in [(service, 'dry_run', 'MODEL_PREFLIGHT'),
            (adapter, 'verify_model', 'MODEL_METADATA'), (adapter, 'count', 'MODEL_TOKEN_COUNT'),
            (adapter, 'invoke', 'LLM_GENERATION')]:
            stack.enter_context(timer.observe(owner, method, name))
        with timer.span('GENERATION_SERVICE_OVERHEAD'):
            outcome = service.generate(prepared, question['question'], package, result,
                                       allow_paid_inference=True, allow_source_transfer=True)
    row.update(audit=outcome.audit | {'mode': 'MOCK', 'generation_executed': False,
            'source_integrity': 'OWNED_SYNTHETIC_NOT_SOURCE_AUTHORITY'}, response=outcome.response, mock_operations=adapter.calls,
        execution_status='COMPLETED' if outcome.response else 'FAILED',
        response_contract_status='ACCEPTED' if outcome.response else 'REJECTED',
        model_status=outcome.response['status'] if outcome.response else None,
        simulated_cost_usd=outcome.audit.get('usage', {}).get('total_estimated_cost_usd'),
        raw_capture=adapter.last_capture,
        diagnostics=outcome.audit.get('response_diagnostics') or outcome.audit.get('blocking_reasons', []))
    if not outcome.response:
        row['failure_stage'] = timer.timer.error_stage or ('RESPONSE_CONTRACT'
            if outcome.audit.get('generation_executed') else 'MODEL_PREFLIGHT')
    if service.last_observation is not None:
        write(run / 'RESPONSE_OBSERVATION.json', service.last_observation)
    if outcome.response:
        with timer.span('POST_GENERATION_VALIDATION'):
            value = PostGenerationValidator(evidence).validate(outcome.response, package, result,
                question=question['question'], request_binding=row)
        # No manufactured source object confers source authority or human acceptance.
        value['source_integrity'] = 'OWNED_SYNTHETIC_NOT_SOURCE_AUTHORITY'
        value['fully_validated'] = False
        row.update(post_validation=value, validation_status=value['overall_status'],
                   response_sha256=digest(outcome.response), semantic_status='PENDING_REVIEW')
        write(run / 'POST_VALIDATION.json', value)
