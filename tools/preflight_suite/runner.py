"""Permanent orchestration around accepted M7/M8, current prompt and GenerationService."""
import hashlib
import json
import time
from pathlib import Path

from tools.evidence.contract import validate_candidates
from tools.evidence.service import EvidenceService
from tools.generation.current import GenerationService, load_settings, resolve
from tools.generation.openai_adapter import wire_request
from tools.generation.telemetry import estimate_max_cost, load_pricing
from tools.pre_generation_gate.current import DEFAULT_TEMPLATE_VERSION, PromptAssemblyGate
from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA
from tools.quality_dashboard.artifacts import ArtifactError, digest

from .artifacts import (
    COMPLETION,
    CONFIG,
    baseline,
    create_run,
    dependencies,
    now,
    read_run,
    save,
    seal,
    sha,
    verify_bindings,
)

STAGES = ['M7 input verification', 'M8 live assembly and validation', DEFAULT_TEMPLATE_VERSION + ' assembly',
          'Model metadata/token/context/cost qualification']
MODULES = ['tools.evidence.contract.validate_candidates', 'tools.evidence.service.EvidenceService.assemble',
           'tools.evidence.service.EvidenceService.validate',
           'tools.pre_generation_gate.current.PromptAssemblyGate.prepare',
           'tools.generation.current.GenerationService.dry_run']
SETTINGS_EXPECTED = {'provider': 'openai', 'model': 'gpt-6-luna',
                     'prompt_version': DEFAULT_TEMPLATE_VERSION,
                     'response_schema': 'grounded-response-2.0', 'max_output_tokens': 4096,
                     'safety_margin_tokens': 1024, 'service_tier': 'default', 'region': 'global'}


def select(rows, *, ids=None, cohorts=None, pending=False, completed=()):
    if ids and (cohorts or pending):
        raise ValueError('CHOOSE_IDS_OR_COHORT_OR_PENDING')
    if ids and (len(set(ids)) != len(ids) or set(ids) - set(rows)):
        raise ValueError('UNKNOWN_OR_DUPLICATE_QUESTION')
    if cohorts and set(cohorts) - set('ABCD'):
        raise ValueError('UNKNOWN_COHORT')
    chosen = set(ids) if ids else set(rows)
    if cohorts:
        chosen &= {q for q, r in rows.items() if r['cohort_id'] in cohorts}
    if pending:
        chosen -= set(completed)
    if not chosen:
        raise ValueError('EMPTY_QUESTION_SELECTION')
    return sorted(chosen)


def completed_questions(root):
    # Selection-only historical telemetry. It never enters runtime prompt construction.
    from tools.quality_dashboard.completion_adapter import load_completed

    data = load_completed(root)
    if data['rejected']:
        raise ArtifactError('UNVERIFIED_GENERATION_INVENTORY')
    return {q for q, r in data['records'].items() if r['latest']}


def configuration(root, *, day):
    settings = load_settings()
    if any(getattr(settings, k) != v for k, v in SETTINGS_EXPECTED.items()):
        raise ValueError('EXPERIMENT_CONFIGURATION_MISMATCH')
    profile = resolve(settings, as_of=day)
    pricing = load_pricing()
    # Validate policy, date, categories and tier BEFORE transmitting source content.
    estimate = estimate_max_cost(settings.model, 0, settings.max_output_tokens, pricing,
                                 tier=settings.service_tier, region=settings.region, as_of=day)
    if estimate['status'] != 'ESTIMATED_MAX_API_COST':
        raise ValueError('CURRENT_PRICING_UNAVAILABLE')
    return settings, profile, pricing


def assemble(evidence, gate, row, result):
    """No benchmark groups, relevance labels or answerability fields accepted here."""
    question = row['question']
    if hashlib.sha256(question.encode()).hexdigest() != row['question_sha256']:
        raise ValueError('QUESTION_TEXT_CHANGED')
    if (result['query_sha256'] != row['question_sha256']
            or result['retrieval_mode'] != 'hybrid'
            or result['parameters'] != {k: v for k, v in CONFIG.items() if k not in {'mode', 'M8_BGE_budget'}}
            or len(result['candidates']) != 30):
        raise ValueError('M7_QUESTION_OR_CONFIGURATION_MISMATCH')
    validate_candidates(result, evidence.m7, evidence.inventory)
    package = evidence.assemble(result, token_budget=128000)
    prepared = gate.prepare(question, package, result, model_configuration=None)
    audit = prepared.audit
    if (prepared.payload is None or audit['source_integrity'] != 'LIVE_M8_VALIDATED'
            or audit['template_version'] != SETTINGS_EXPECTED['prompt_version']
            or audit['response_schema_version'] != SETTINGS_EXPECTED['response_schema']
            or audit['blocking_reasons'] != ['NO_OWNER_AUTHORIZED_GENERATOR_CONFIGURATION']):
        raise ValueError('LOCAL_PROMPT_OR_SOURCE_VALIDATION_BLOCKED')
    return package, prepared


def recipe(row, result, package, prepared, settings, profile):
    request = wire_request(prepared.payload['request'], settings, profile)
    value = {'schema': 'rag-request-reconstruction-1.0', 'question_id': row['question_id'],
             'question_sha256': row['question_sha256'], 'candidate_artifact': COMPLETION + '/m7/' + row['question_id'] + '.json',
             'M7_result_sha256': digest(result), 'M8_package_sha256': digest(package),
             'M8_BGE_budget': 128000, 'neutral_request_sha256': prepared.audit['request_sha256'],
             'request_sha256': digest(request), 'template_version': settings.prompt_version,
             'template_sha256': prepared.audit['template_sha256'],
             'response_schema_version': settings.response_schema,
             'response_schema_sha256': prepared.audit['response_schema_sha256'],
             'settings_sha256': digest(settings.model_dump()), 'profile_sha256': digest(profile),
             'reconstruct_with': 'fresh accepted M8 assembly -> current PromptAssemblyGate.prepare -> existing wire_request',
             'source_payload_persisted': False, 'generation_authorized': False,
             'reuse': 'REVALIDATE_ALL_DEPENDENCIES_AND_EXACT_HASHES_BEFORE_EVERY_USE'}
    return value, request


def equivalence(previous, current):
    if previous != current:
        raise ValueError('LOCAL_REQUEST_RECONSTRUCTION_OR_CONFIGURATION_CHANGED')


def source_transfer_check(package):
    """Honor explicit native machine-readable prohibitions; do not reclassify sources.

    Current accepted contracts authorize LLM context within published allowed-use
    restrictions. Full unchanged obligations travel with each parent. No new QA
    permission is conferred here. Explicit owner opt-in remains separately required.
    """
    for p in package['parents']:
        parent = p['evidence']['verified_parent']
        if parent['admission_status'] != 'ADMITTED' or not parent['consumer']['llm_context']:
            raise ValueError('SOURCE_LLM_CONTEXT_NOT_AUTHORIZED')
        for context in (parent['consumer'], parent['consumer']['llm_context']):
            if context.get('external_transfer_allowed') is False or context.get('provider_transfer_allowed') is False:
                raise ValueError('SOURCE_PROVIDER_TRANSFER_FORBIDDEN')


def execute(root, *, mode, selected, authorization=None, local_manifest=None, progress=print):
    root = Path(root).resolve(strict=True)
    store, inventory = baseline(root)
    if selected != sorted(set(selected)) or set(selected) - set(inventory):
        raise ValueError('INVALID_ORDERED_QUESTION_SELECTION')
    day = __import__('datetime').datetime.fromisoformat(now()).date()
    settings, profile, pricing = configuration(root, day=day)
    previous = None
    if mode == 'model-preflight':
        if not authorization or not local_manifest:
            raise ValueError('EXPLICIT_QUESTION_SET_SOURCE_TRANSFER_AUTHORIZATION_AND_LOCAL_RUN_REQUIRED')
        original, values, local_store = read_run(root, local_manifest)
        if original['mode'] != 'local-check':
            raise ValueError('LOCAL_CHECK_RUN_REQUIRED')
        previous = {r['question_id']: r for r in values['questions']}
        if any(q not in previous or previous[q]['status'] != 'LOCAL_VALIDATED' for q in selected):
            raise ValueError('ONLY_LOCALLY_VALIDATED_REQUESTS_MAY_BE_QUALIFIED')
        store.verified.update(local_store.verified)
    elif mode != 'local-check':
        raise ValueError('INVALID_EXECUTION_MODE')
    bindings = dependencies(root, store)
    run = create_run(root, mode)
    auth = {'owner_statement': authorization, 'question_ids': selected,
            'provider_metadata_and_token_count_only': mode == 'model-preflight',
            'complete_verified_evidence_transfer': mode == 'model-preflight',
            'generation': False, 'per_question_metadata_limit': 1, 'per_question_token_count_limit': 1,
            'automatic_retries': 0}
    save(run / 'RUN_START.json', {'schema': 'rag-preflight-suite-1.0', 'mode': mode,
         'created_at': now(), 'question_ids': selected, 'configuration': CONFIG,
         'stages': STAGES, 'modules': MODULES, 'authorization': auth})
    save(run / 'DEPENDENCIES.json', bindings)
    evidence = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
    # Live source/publication contracts, including source bytes and tokenizer files.
    bindings.update(evidence.files)
    gate = PromptAssemblyGate(evidence)
    rows = []
    for qid in selected:
        qdir = run / 'questions' / qid
        row = inventory[qid]
        started = time.perf_counter()
        observation = {'question_id': qid, 'cohort_id': row['cohort_id'], 'status': 'BLOCKED_INTEGRITY',
                       'local_validated': False, 'input_tokens': None, 'maximum_cost_usd': None,
                       'request_sha256': None, 'prompt_version': settings.prompt_version,
                       'schema_version': settings.response_schema, 'model': settings.model,
                       'reserved_output_tokens': settings.max_output_tokens,
                       'safety_margin_tokens': settings.safety_margin_tokens,
                       'generation_executed': False}
        local_audit = {'status': 'BLOCKED_INTEGRITY', 'blocking_reasons': ['LOCAL_CHECK_NOT_COMPLETED']}
        model_audit = {'status': 'NOT_RUN', 'reason': 'LOCAL_ONLY', 'generation_executed': False}
        reconstruction = {'status': 'UNAVAILABLE', 'request_sha256': None}
        transport, client = None, None
        try:
            verify_bindings(store, bindings)
            result = store.json(COMPLETION + f'/m7/{qid}.json')
            package, prepared = assemble(evidence, gate, row, result)
            historical = store.json(COMPLETION + f'/m8/{qid}.json')
            if digest(package) != historical['M8_package_sha256']:
                raise ArtifactError('LIVE_M8_PACKAGE_DIFFERS_FROM_SEALED_MEASUREMENT')
            reconstruction, request = recipe(row, result, package, prepared, settings, profile)
            if previous is not None:
                previous_path = local_manifest.rsplit('/', 1)[0] + f'/questions/{qid}/REQUEST_PACKAGE.json'
                equivalence(store.json(previous_path), reconstruction)
            local_audit = prepared.audit
            observation.update(status='LOCAL_VALIDATED', local_validated=True,
                               request_sha256=reconstruction['request_sha256'],
                               M7_result_sha256=digest(result), M8_package_sha256=digest(package),
                               included_parents=package['counts']['selected_parents'],
                               omitted_parents=package['counts']['omitted_parents'],
                               evidence_BGE_tokens=package['budget']['exact_llm_evidence_tokens'],
                               source_integrity=prepared.audit['source_integrity'],
                               context_fit='UNVERIFIED', model_status='NOT_RUN',
                               source_obligation_hashes=[digest(p['evidence']['verified_parent']['consumer'])
                                                         for p in package['parents']])
            if mode == 'model-preflight':
                source_transfer_check(package)
                from .provider import adapter

                safe_adapter, client, transport = adapter(root, qdir, request, settings.timeout_seconds)
                service = GenerationService(gate, safe_adapter, settings=settings, pricing=pricing, as_of=day)
                outcome = service.dry_run(prepared, row['question'], package, result,
                                          allow_provider_preflight=True, allow_source_transfer=True)
                model_audit = outcome.audit
                observation.update(status='MODEL_QUALIFIED' if model_audit['status'] == 'READY'
                                   else model_audit['status'], model_status=model_audit['status'],
                                   input_tokens=model_audit.get('generator_input_tokens'),
                                   context_fit=model_audit.get('context_fit'),
                                   maximum_cost_usd=model_audit.get('cost_estimate', {}).get('estimated_max_cost_usd'),
                                   pricing_version=pricing['version'],
                                   blocking_reasons=model_audit['blocking_reasons'])
                model_audit['schema_compatibility_scope'] = 'DOCUMENTED_PROFILE_AND_COUNT_ENDPOINT_ACCEPTANCE_ONLY_NO_GENERATION_VALIDATION'
            observation.setdefault('blocking_reasons', [])
        except Exception as error:  # noqa: BLE001 - redact arbitrary source/provider exception bodies
            # Exceptions may contain source material. Only types, never messages or tracebacks.
            known = {'SOURCE_PROVIDER_TRANSFER_FORBIDDEN', 'SOURCE_LLM_CONTEXT_NOT_AUTHORIZED',
                     'KEY_CONFIGURATION_INVALID', 'CURRENT_PRICING_UNAVAILABLE',
                     'LOCAL_REQUEST_RECONSTRUCTION_OR_CONFIGURATION_CHANGED',
                     'LIVE_M8_PACKAGE_DIFFERS_FROM_SEALED_MEASUREMENT'}
            reason = str(error) if str(error) in known else 'QUESTION_CHECK_FAILED_' + type(error).__name__
            integrity = (not observation['local_validated']) or isinstance(error, ArtifactError) or reason in {
                'LOCAL_REQUEST_RECONSTRUCTION_OR_CONFIGURATION_CHANGED',
                'LIVE_M8_PACKAGE_DIFFERS_FROM_SEALED_MEASUREMENT'}
            observation.update(status='BLOCKED_INTEGRITY' if integrity else 'BLOCKED_CONFIGURATION',
                               blocking_reasons=[reason])
            model_audit = {'status': observation['status'], 'blocking_reasons': observation['blocking_reasons'],
                           'generation_executed': False}
        finally:
            if client is not None:
                client.close()
        calls = transport.receipts if transport else []
        observation['provider_calls'] = len(calls)
        observation['duration_ms'] = (time.perf_counter() - started) * 1000
        save(qdir / 'REQUEST_PACKAGE.json', reconstruction)
        save(qdir / 'LOCAL_VALIDATION.json', local_audit)
        save(qdir / 'MODEL_PREFLIGHT.json', model_audit)
        save(qdir / 'PROVIDER_CALLS.json', calls)
        save(qdir / 'QUESTION_MANIFEST.json', {'question_id': qid, 'question_sha256': row['question_sha256'],
             'request_sha256': observation['request_sha256'], 'configuration': CONFIG,
             'created_at': now(), 'files': {p.name: sha(p) for p in qdir.iterdir() if p.is_file()}})
        rows.append(observation)
        progress(json.dumps({'run_id': run.name, 'question_id': qid, 'status': observation['status'],
                             'completed': len(rows), 'selected': len(selected), 'provider_calls': len(calls)}), flush=True)
    verify_bindings(store, bindings)
    evidence.check()
    manifest = seal(run, mode=mode, selected=selected, bindings=bindings, rows=rows,
                    authorization=auth, local_run=local_manifest)
    return run, manifest
