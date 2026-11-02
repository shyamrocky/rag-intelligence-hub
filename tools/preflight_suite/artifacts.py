"""Immutable, source-free preflight publications and exact dependency bindings."""
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from tools.quality_dashboard.artifacts import ArtifactError, Store, sha

VERSION = 'rag-preflight-suite-1.0'
BASE = 'data/evals/preflight-suite'
COMPLETION = 'data/evals/benchmark-completion/v1'
EXPANDED = 'data/evals/expanded-benchmark/v1/MANIFEST.json'
EXPANDED_SHA = 'dfddd4e1079c1de3d3dd637db1386f4b5638f594fd0d7cca590f974ef97119fe'
REVIEW_SHA = '30fb341b32e6a12cfc03421996c80576fe1903d3074aba917b1777ebc84ffff8'
CONFIG = {'mode': 'hybrid', 'top_k': 30, 'candidate_depth': 50, 'rrf_k': 60,
          'filters': {}, 'M8_BGE_budget': 128000}


def now():
    return datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()


def save(path, value):
    """Exclusive create: a partial or sealed execution can never be overwritten."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for p in (path.parent,):
        p.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def create_run(root, mode):
    if mode not in {'local-check', 'model-preflight'}:
        raise ValueError('INVALID_EXECUTION_MODE')
    identity = datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y%m%dT%H%M%S')
    run = Path(root) / BASE / f'{identity}-{mode}-{uuid4().hex[:12]}'
    run.mkdir(parents=True, mode=0o700)
    return run


def baseline(root):
    store = Store(root)
    store.manifest(EXPANDED, expected=EXPANDED_SHA)
    review = store.manifest(COMPLETION + '/REVIEW_MANIFEST.json', expected=REVIEW_SHA)
    for name, fingerprint in review.get('input_bindings', {}).items():
        store.bind(name, fingerprint)
    measurement = store.json(COMPLETION + '/MANIFEST.json')
    if measurement['configuration'] != CONFIG:
        raise ArtifactError('INCOMPATIBLE_BASELINE_CONFIGURATION')
    for name, fingerprint in measurement['input_bindings'].items():
        store.bind(name, fingerprint)
    # This execution inventory intentionally has no expected answers or evidence labels.
    questions = store.json(COMPLETION + '/QUESTIONS_ONLY.json')
    if questions['labels_supplied'] is not False:
        raise ArtifactError('QUESTION_ONLY_INVENTORY_REQUIRED')
    rows = {q['question_id']: q for q in questions['questions']}
    if len(rows) != 34:
        raise ArtifactError('INCOMPLETE_BENCHMARK_INVENTORY')
    for row in rows.values():
        import hashlib
        if hashlib.sha256(row['question'].encode()).hexdigest() != row['question_sha256']:
            raise ArtifactError('QUESTION_TEXT_BINDING_MISMATCH')
    return store, rows


def dependencies(root, store):
    """Pin source/index/publication contracts and exact orchestration/token/pricing code."""
    bindings = dict(store.verified)
    for folder in ('tools/preflight_suite', 'tools/pre_generation_gate', 'tools/generation',
                   'tools/evidence', 'tools/retrieval'):
        for path in (Path(root) / folder).rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.json', '.txt'} and not any(
                p in path.parts for p in ('.venv', '__pycache__', '.pytest_cache', '.ruff_cache')
            ):
                bindings[path.relative_to(root).as_posix()] = sha(path)
    return bindings


def verify_bindings(store, bindings):
    if not bindings:
        raise ArtifactError('MISSING_DEPENDENCY_BINDINGS')
    for name, fingerprint in bindings.items():
        store.bind(name, fingerprint)


def summarize(rows):
    qualified = [r for r in rows if r['status'] == 'MODEL_QUALIFIED']
    costs = [Decimal(r['maximum_cost_usd']) for r in qualified]
    return {'selected': len(rows), 'local_validated': sum(r.get('local_validated', False) for r in rows),
            'model_qualified': len(qualified),
            'blocked': sum(r['status'].startswith('BLOCKED') for r in rows),
            'exact_input_tokens': sum(r['input_tokens'] for r in qualified),
            'aggregate_maximum_estimated_cost_usd': str(sum(costs, Decimal(0))) if costs else None,
            'cost_label': 'ESTIMATED_MAX_API_COST_NOT_INVOICE_OR_BALANCE',
            'generation_calls': 0}


def seal(run, *, mode, selected, bindings, rows, authorization, local_run=None):
    summary = summarize(rows)
    cohorts = {c: summarize([r for r in rows if r['cohort_id'] == c]) for c in 'ABCD'}
    save(run / 'RESULTS.json', {'schema': VERSION, 'mode': mode, 'questions': rows,
                              'summary': summary, 'cohorts': cohorts})
    files = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    value = {'schema': VERSION, 'status': 'COMPLETED_SEALED_PENDING_OWNER_REVIEW',
             'run_id': run.name, 'mode': mode, 'created_at': now(), 'question_ids': selected,
             'expanded_benchmark_manifest_sha256': EXPANDED_SHA, 'configuration': CONFIG,
             'input_bindings': bindings, 'files': files, 'authorization': authorization,
             'local_run': local_run, 'generation_authorized': False,
             'generation_endpoints': 'DENIED_BY_TRANSPORT_ALLOWLIST',
             'packages': 'SOURCE_FREE_DETERMINISTIC_RECONSTRUCTION_RECIPES_NOT_BEARER_AUTHORIZATIONS'}
    save(run / 'MANIFEST.json', value)
    return value


def read_run(root, name):
    store = Store(root)
    manifest = store.manifest(name, schema=VERSION)
    if (manifest.get('status') != 'COMPLETED_SEALED_PENDING_OWNER_REVIEW'
            or manifest.get('expanded_benchmark_manifest_sha256') != EXPANDED_SHA
            or manifest.get('configuration') != CONFIG
            or manifest.get('mode') not in {'local-check', 'model-preflight'}
            or manifest.get('generation_authorized') is not False):
        raise ArtifactError('INCOMPATIBLE_PREFLIGHT_MANIFEST')
    verify_bindings(store, manifest['input_bindings'])
    base = name.rsplit('/', 1)[0]
    value = store.json(base + '/RESULTS.json')
    rows = value['questions']
    if ([r['question_id'] for r in rows] != manifest['question_ids']
            or len(set(manifest['question_ids'])) != len(rows)
            or value['summary'] != summarize(rows)):
        raise ArtifactError('PREFLIGHT_INVENTORY_OR_ACCOUNTING_MISMATCH')
    inventory = store.json(COMPLETION + '/QUESTIONS_ONLY.json')['questions']
    inventory = {q['question_id']: q for q in inventory}
    for r in rows:
        q = r['question_id']
        if q not in inventory or r['cohort_id'] != inventory[q]['cohort_id']:
            raise ArtifactError('UNKNOWN_OR_MISMATCHED_PREFLIGHT_QUESTION')
        if r['status'] not in {'LOCAL_VALIDATED', 'MODEL_QUALIFIED', 'BLOCKED_INPUT',
                              'BLOCKED_CONFIGURATION', 'BLOCKED_CONTEXT', 'BLOCKED_INTEGRITY'}:
            raise ArtifactError('INVALID_PREFLIGHT_STATUS')
        parts = {child: store.json(base + f'/questions/{q}/{child}')
                 for child in ('REQUEST_PACKAGE.json', 'LOCAL_VALIDATION.json', 'MODEL_PREFLIGHT.json')}
        calls = store.json(base + f'/questions/{q}/PROVIDER_CALLS.json')
        if len(calls) != r['provider_calls'] or len(calls) > 2:
            raise ArtifactError('PROVIDER_CALL_LIMIT_OR_LEDGER_MISMATCH')
        if manifest['mode'] == 'local-check' and calls:
            raise ArtifactError('LOCAL_RUN_CONTAINS_PROVIDER_CALLS')
        allowed = {('GET', '/v1/models/gpt-6-luna'), ('POST', '/v1/responses/input_tokens')}
        if len({(c['method'], c['endpoint']) for c in calls}) != len(calls) or any(
            (c['method'], c['endpoint']) not in allowed for c in calls
        ):
            raise ArtifactError('FORBIDDEN_PROVIDER_ENDPOINT')
        if r['local_validated']:
            from tools.quality_dashboard.artifacts import digest
            local, request = parts['LOCAL_VALIDATION.json'], parts['REQUEST_PACKAGE.json']
            if (local.get('source_integrity') != 'LIVE_M8_VALIDATED'
                    or request['request_sha256'] != r['request_sha256']
                    or request['M8_package_sha256'] != r['M8_package_sha256']
                    or request['M7_result_sha256'] != r['M7_result_sha256']
                    or request['neutral_request_sha256'] != local['request_sha256']
                    or request['template_sha256'] != local['template_sha256']
                    or request['response_schema_sha256'] != local['response_schema_sha256']
                    or local['audit_sha256'] != digest({k: v for k, v in local.items() if k != 'audit_sha256'})):
                raise ArtifactError('LOCAL_REQUEST_AUDIT_BINDING_MISMATCH')
        if r['status'] == 'MODEL_QUALIFIED':
            validate_qualification(r, parts['MODEL_PREFLIGHT.json'], manifest) 
        qm = store.json(base + f'/questions/{q}/QUESTION_MANIFEST.json')
        if (qm['question_id'] != q or qm['request_sha256'] != r.get('request_sha256')
                or qm['question_sha256'] != inventory[q]['question_sha256']):
            raise ArtifactError('QUESTION_MANIFEST_MISMATCH')
        for child, fingerprint in qm['files'].items():
            store.bind(base + f'/questions/{q}/' + child, fingerprint)
    return manifest, value, store


def validate_qualification(row, audit, manifest):
    """Independently reconcile stored context/cost qualification; no provider access."""
    from tools.generation.profiles import GenerationSettings, check_fit
    from tools.generation.telemetry import estimate_max_cost, load_pricing

    auth = manifest['authorization']
    count = audit.get('generator_input_tokens')
    if (manifest['mode'] != 'model-preflight' or not auth.get('owner_statement')
            or auth.get('question_ids') != manifest['question_ids']
            or auth.get('complete_verified_evidence_transfer') is not True
            or audit.get('status') != 'READY' or audit.get('generation_executed') is not False
            or audit.get('model_access') != 'ACCOUNT_MODEL_ACCESS_VERIFIED'
            or type(count) is not int or count < 0 or row['input_tokens'] != count
            or audit.get('request_sha256') != row['request_sha256']
            or audit.get('M8_package_sha256') != row['M8_package_sha256']
            or audit.get('token_count_receipt', {}).get('request_sha256') != row['request_sha256']):
        raise ArtifactError('MODEL_QUALIFICATION_BINDING_INVALID')
    raw_settings = dict(audit['settings'])
    raw_settings['schema'] = raw_settings.pop('schema_version')
    settings = GenerationSettings.model_validate(raw_settings)
    fit = check_fit(audit['model_profile'], settings, count)
    estimate = estimate_max_cost(settings.model, count, settings.max_output_tokens, load_pricing(),
                                 tier=settings.service_tier, region=settings.region,
                                 as_of=date.fromisoformat(manifest['created_at'][:10]))
    if (not fit['fits'] or fit != audit['context_fit'] or fit != row['context_fit']
            or estimate != audit['cost_estimate']
            or row['maximum_cost_usd'] != estimate['estimated_max_cost_usd']
            or estimate['status'] != 'ESTIMATED_MAX_API_COST'):
        raise ArtifactError('MODEL_QUALIFICATION_CONTEXT_OR_COST_INVALID')
