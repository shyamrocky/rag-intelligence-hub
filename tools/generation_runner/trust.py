"""Native trust boundary. No network, credentials, source projection or approval issuance.

The deployment registry is the bootstrap trust root, reviewed as source. A manifest
cannot authorize its own replacement; registry changes require a new owner-reviewed
code release. Receipts prove preservation only, never permission to generate.
"""
import importlib.util
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from tools.generation_trust_anchor import TRUSTED_BASELINES
from tools.preflight_suite.artifacts import now, save, sha
from tools.quality_dashboard.artifacts import ArtifactError, digest, read_json, safe_path

AUTH_SCHEMA = 'grounded-generation-authorization-2.0'
RECEIPT_SCHEMA = 'generation-preservation-receipt-1.0'
MAX_AGE_SECONDS = 900


def bound(root, name, expected):
    path = safe_path(root, name)
    if sha(path) != expected:
        raise ArtifactError('TRUST_BINDING_MISMATCH')
    return read_json(path)


def load_trust(root, manifest_path, expected):
    """The path AND hash must be in the deployment allowlist, not caller assertions."""
    safe_path(root, 'tools/generation_trust_anchor.py')  # Required even in an already imported process.
    if TRUSTED_BASELINES.get(manifest_path) != expected:
        raise ArtifactError('UNTRUSTED_BASELINE')
    manifest = bound(root, manifest_path, expected)
    if manifest.get('schema') != 'generation-trust-baseline-1.0':
        raise ArtifactError('INVALID_TRUST_BASELINE')
    base = manifest_path.rsplit('/', 1)[0]
    values = {name: bound(root, base + '/' + name, h) for name, h in manifest['files'].items()}
    policy = values['POLICY.json']
    if (policy['schema'] != 'generation-preservation-policy-3.0'
            or policy['generation_authority'] is not False):
        raise ArtifactError('INVALID_PRESERVATION_POLICY')
    checker = manifest['checker']
    path = safe_path(root, checker['path'], prefix='workspace')
    if sha(path) != checker['sha256']:
        raise ArtifactError('PRESERVATION_CHECKER_CHANGED')
    spec = importlib.util.spec_from_file_location('pinned_preservation_evaluator', path)
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    result = evaluator.evaluate(root, values['BASELINE_BINDINGS.json'],
        values['CRITICAL_BINDINGS.json'], policy['absence_exceptions'],
        policy['closed_code_configuration_scopes'])
    # Audit-only, exact historical tool metadata inventory. Not a blanket .git waiver.
    for name, expected_hash in policy['historical_transient_audit_only'].items():
        p = evaluator.path_in(root, name)
        if p.exists() and (not p.is_file() or evaluator.digest_file(p) != expected_hash):
            raise ArtifactError('HISTORICAL_TRANSIENT_REFERENCE_CHANGED')
        if not p.exists():
            result['findings'].append({'path': name, 'blocking': False,
                'status': 'HISTORICAL_TRANSIENT_METADATA_ABSENT', 'expected_sha256': expected_hash})
    if result['blocking_findings']:
        raise ArtifactError('PRESERVATION_BLOCKED')
    if policy.get('native_recovery') is not None:
        from .recovery import parent
        parent(root, policy['native_recovery'])
    return manifest, policy, result


def context(plan):
    if plan.get('plan_sha256') != digest({k: v for k, v in plan.items() if k != 'plan_sha256'}):
        raise ArtifactError('PLAN_HASH_MISMATCH')
    questions = plan['questions']
    ids = [q['question_id'] for q in questions]
    if not ids or len(set(ids)) != len(ids) or 'M9-Q05' in ids:
        raise ArtifactError('DUPLICATE_OR_HISTORICAL_QUESTION')
    return {'plan_sha256': plan['plan_sha256'], 'question_ids': ids,
            'preflight_sha256': plan['preflight_sha256'],
            'requests': {q['question_id']: {k: q[k] for k in
                ('request_sha256', 'M7_result_sha256', 'M8_package_sha256', 'question_sha256')}
                for q in questions},
            'aggregate_cap_usd': plan['aggregate_cap_usd'],
            'per_question_caps_usd': {q['question_id']: q['per_question_cap_usd'] for q in questions}}


def verify_plan_policy(plan, policy, *, root=None):
    ctx = context(plan)
    chat = bool(plan.get('chat_submission'))
    if chat:
        if root is None or plan.get('question_source') != 'BOT' or len(ctx['question_ids']) != 1:
            raise ArtifactError('CHAT_NATIVE_VERIFICATION_REQUIRED')
        from .bot_chat import check_plan
        settings = check_plan(root, plan, policy)
        # The dynamic scope is derived only after independent source-bound Send
        # and exact qualification reconstruction, never from caller path/hash.
        contract = digest({k:v for k,v in plan.items() if k not in {'plan_sha256','created_for_date'}})
        policy = policy | {'permitted_question_ids': ctx['question_ids'],
            'request_bindings': ctx['requests'], 'approved_plan_contract_sha256': contract,
            'bot_live_scope': {'question_ids': ctx['question_ids'], 'plan_contract_sha256': contract,
                               'maximum_bot_total_usd': settings['total_bot_cap_usd']},
            'maximum_question_cap_usd': settings['per_question_cap_usd'],
            'maximum_stage_cap_usd': settings['per_question_cap_usd']}
    if plan.get('question_source') == 'BOT':
        from tools.bot_runtime.store import ID
        scope = policy.get('bot_live_scope') or {}
        if (scope.get('question_ids') != ctx['question_ids'] or len(ctx['question_ids']) != 1
                or not ID.fullmatch(ctx['question_ids'][0])
                or scope.get('plan_contract_sha256') != digest({k:v for k,v in plan.items() if k not in {'plan_sha256','created_for_date'}})
                or not isinstance(scope.get('maximum_bot_total_usd'), str)):
            raise ArtifactError('EXACT_REVIEWED_BOT_LIVE_SCOPE_REQUIRED')
        bot_cap=Decimal(scope['maximum_bot_total_usd'])
        if not bot_cap.is_finite() or bot_cap <= 0:
            raise ArtifactError('EXPLICIT_BOT_CUMULATIVE_CAP_REQUIRED')
    if policy.get('native_recovery') is not None:
        from .recovery import validate_scope
        validate_scope(policy['native_recovery'], ctx['question_ids'], ctx['requests'])
    contract = {k: v for k, v in plan.items() if k not in {'plan_sha256', 'created_for_date'}}
    if (digest(contract) != policy['approved_plan_contract_sha256']
            or plan.get('created_for_date') != date.today().isoformat()
            or not set(ctx['question_ids']) <= set(policy['permitted_question_ids'])
            or plan['model'] != policy['model'] or plan['prompt_version'] != policy['prompt_version']
            or plan['response_schema'] != policy['response_schema']
            or plan['expected_future_calls'] != {'model_metadata': len(ctx['question_ids']),
                'token_count': len(ctx['question_ids']), 'generation_maximum': len(ctx['question_ids']),
                'retries': 0}):
        raise ArtifactError('TRUST_POLICY_PLAN_SCOPE_MISMATCH')
    maximum = Decimal(plan['aggregate_maximum_estimated_cost_usd'])
    cap = Decimal(ctx['aggregate_cap_usd'])
    if (not maximum.is_finite() or not cap.is_finite() or maximum <= 0 or cap <= 0
            or maximum > cap or cap > Decimal(policy['maximum_stage_cap_usd'])):
        raise ArtifactError('TRUST_POLICY_COST_CAP')
    total = Decimal(0)
    for q in plan['questions']:
        amount, limit = Decimal(q['maximum_cost_usd']), Decimal(q['per_question_cap_usd'])
        if (not amount.is_finite() or not limit.is_finite() or amount <= 0 or limit <= 0
                or amount > limit or limit > Decimal(policy['maximum_question_cap_usd'])
                or policy['request_bindings'].get(q['question_id']) != ctx['requests'][q['question_id']]):
            raise ArtifactError('TRUST_POLICY_REQUEST_OR_COST_MISMATCH')
        total += amount
    if total != maximum:
        raise ArtifactError('PLAN_COST_RECONCILIATION_FAILED')
    return ctx


def history(root, question_ids, *, recovery=None):
    """Conservative native and legacy reconciliation, including unsealed attempts.

    Every admitted native live plan remains a reservation, even after failures.
    No automatic retry, reservation release or unknown-billing recovery is supported.
    """
    from tools.preflight_suite.runner import completed_questions

    recovered = None
    if recovery is not None:
        from .recovery import parent, validate_scope
        validate_scope(recovery, question_ids)
        recovered = parent(root, recovery)
    recovery_runs = set(recovered.get('parent_run_ids', [])) if recovered else set()
    recovery_uses = {ref['path'] for ref in recovered.get('parent_authorization_uses', [])} if recovered else set()
    if recovered and 'parent_run_id' in recovered:
        recovery_runs.add(recovered['parent_run_id'])
        recovery_uses.add(recovered['parent_authorization_use']['path'])
    done = completed_questions(root) | {'M9-Q05'}
    if set(question_ids) & done:
        raise ArtifactError('PRIOR_SUCCESSFUL_GENERATION')
    for p in sorted((Path(root) / 'data/evals/generation').glob('*/GENERATION_ATTEMPT.json')):
        attempt = read_json(safe_path(root, p.relative_to(root).as_posix()))
        if attempt.get('question_id') in question_ids:
            raise ArtifactError('LEGACY_PRIOR_ATTEMPT_NO_AUTOMATIC_RETRY')
    base = Path(root) / 'data/evals/generation-runner'
    for p in sorted(base.glob('*/MANIFEST.json')):
        record = read_json(safe_path(root, p.relative_to(root).as_posix()))
        if record.get('mode') == 'live' and not (p.parent / 'START.json').is_file():
            raise ArtifactError('LIVE_HISTORY_START_MISSING')
    reserved = Decimal(0)
    observations = []
    bot_reserved = Decimal(0)
    for p in sorted(base.glob('*/START.json')):
        start = read_json(safe_path(root, p.relative_to(root).as_posix()))
        if start.get('mode') != 'live':
            continue
        plan_path = p.parent / 'PLAN.json'
        prior = read_json(safe_path(root, plan_path.relative_to(root).as_posix()))
        ctx = context(prior)
        if (set(question_ids) & set(ctx['question_ids'])
                and not (recovered and p.parent.name in recovery_runs)):
            raise ArtifactError('PRIOR_LIVE_RUN_OR_UNRESOLVED_ATTEMPT')
        amount = Decimal(prior['aggregate_maximum_estimated_cost_usd'])
        if not amount.is_finite() or amount <= 0:
            raise ArtifactError('UNKNOWN_CROSS_RUN_BILLING')
        reserved += amount
        if prior.get('question_source') == 'BOT':
            bot_reserved += amount
        observations.append({'plan': plan_path.relative_to(root).as_posix(), 'sha256': sha(plan_path),
                             'reserved_usd': str(amount)})
    for p in sorted(base.rglob('*.json')):
        if p.name not in {'LIVE_ATTEMPT.json', 'GENERATION_HTTP_ATTEMPT.json'}:
            continue
        # Orphan attempts fail globally, even if a START or PLAN was lost.
        run = p.parents[2]
        if not (run / 'START.json').is_file() or not (run / 'PLAN.json').is_file():
            raise ArtifactError('ORPHAN_LIVE_ATTEMPT')
        if (any(q in p.parts for q in question_ids)
                and not (recovered and run.name in recovery_runs)):
            raise ArtifactError('UNRESOLVED_OR_PREVIOUS_LIVE_ATTEMPT')
    # A consumed authorization is permanent even if execution crashed before START.
    uses = base / 'authorization-use'
    for p in sorted(uses.glob('*.json')):
        prior = read_json(safe_path(root, p.relative_to(root).as_posix()))
        if (set(question_ids) & set(prior['question_ids']) and not (recovered
                and p.relative_to(root).as_posix() in recovery_uses)):
            raise ArtifactError('PREVIOUS_AUTHORIZATION_CONSUMPTION')
        if not (base / prior['run_id'] / 'START.json').is_file():
            raise ArtifactError('UNRESOLVED_AUTHORIZATION_CONSUMPTION')
    result = {'reserved_native_usd': str(reserved), 'observations': observations,
              'historical_Q05_excluded': True}
    if any(q.startswith('BOT-') for q in question_ids):
        result['reserved_bot_usd'] = str(bot_reserved)
    if recovered:
        result['explicit_recovery'] = recovered
    return result


def preservation_receipt(root, plan, manifest_path, manifest_sha):
    manifest, policy, result = load_trust(root, manifest_path, manifest_sha)
    ctx = verify_plan_policy(plan, policy, root=root)
    prior = history(root, ctx['question_ids'], recovery=policy.get('native_recovery'))
    if plan.get('chat_submission'):
        from .bot_chat import budget_state, config
        budget_state(root, config(policy), additional=plan['aggregate_maximum_estimated_cost_usd'])
    elif plan.get('question_source') == 'BOT' and (Decimal(prior['reserved_bot_usd']) + Decimal(plan['aggregate_maximum_estimated_cost_usd']) > Decimal(policy['bot_live_scope']['maximum_bot_total_usd'])):
        raise ArtifactError('BOT_CUMULATIVE_COST_CAP_EXCEEDED')
    if (not plan.get('chat_submission') and Decimal(prior['reserved_native_usd']) + Decimal(plan['aggregate_maximum_estimated_cost_usd'])
            > Decimal(policy['maximum_rollout_cap_usd'])):
        raise ArtifactError('CROSS_RUN_COST_CAP_EXCEEDED')
    return {'schema': RECEIPT_SCHEMA, 'created_at': now(), 'generation_authority': False,
            'trust_manifest': manifest_path, 'trust_manifest_sha256': manifest_sha,
            'policy_sha256': manifest['files']['POLICY.json'], 'context': ctx,
            'preservation': result, 'history': prior}


def validate_receipt(root, plan, auth):
    """Native re-evaluation: a self-consistent receipt alone never establishes trust."""
    reference = auth.get('preservation_receipt', {})
    receipt = bound(root, reference['path'], reference['sha256'])
    created = datetime.fromisoformat(receipt['created_at'])
    current = datetime.fromisoformat(now())
    if created.tzinfo is None or not 0 <= (current - created).total_seconds() <= MAX_AGE_SECONDS:
        raise ArtifactError('STALE_PRESERVATION_RECEIPT')
    fresh = preservation_receipt(root, plan, auth['trust_manifest'], auth['trust_manifest_sha256'])
    if (receipt.get('schema') != RECEIPT_SCHEMA
            or {k: v for k, v in receipt.items() if k != 'created_at'}
            != {k: v for k, v in fresh.items() if k != 'created_at'}):
        raise ArtifactError('PRESERVATION_RECEIPT_BINDING_MISMATCH')
    return receipt


def prepare(root, plan, output, *, trust_manifest, trust_sha):
    """Native unsigned preparation only. No owner statement/permissions can be supplied."""
    from .runner import implementation

    if not output.startswith('workspace/') or '..' in output.split('/'):
        raise ArtifactError('PRIVATE_PREPARATION_DIRECTORY_REQUIRED')
    folder = Path(root) / output
    if folder.exists() or any(p.is_symlink() for p in [folder, *folder.parents]):
        raise ArtifactError('NEW_SAFE_PREPARATION_DIRECTORY_REQUIRED')
    receipt = preservation_receipt(root, plan, trust_manifest, trust_sha)
    folder.mkdir(parents=True, mode=0o700)
    save(folder / 'PRESERVATION_RECEIPT.json', receipt)
    save(folder / 'PLAN.json', plan)
    template = {'schema': AUTH_SCHEMA, **context(plan), 'trust_manifest': trust_manifest,
        'trust_manifest_sha256': trust_sha, 'implementation_bindings': implementation(root),
        'preservation_receipt': {'path': output + '/PRESERVATION_RECEIPT.json',
                                'sha256': sha(folder / 'PRESERVATION_RECEIPT.json')},
        'owner_statement': '', 'allow_paid_inference': False, 'allow_source_transfer': False,
        'maximum_generation_requests_per_question': 1, 'expires_at': '1970-01-01T00:00:00+00:00'}
    save(folder / 'AUTHORIZATION_TEMPLATE.json', template)
    save(folder / 'MANIFEST.json', {'schema': 'generation-unsigned-preparation-1.0',
        'generation_authorized': False,
        'files': {p.name: sha(p) for p in folder.iterdir() if p.is_file()}})
    return folder


def execution_guard(root, plan, auth, authorization_path, authorization_sha):
    """Recheck immediately before credentials and inference, after own admission.

    Does not re-admit the run or mistake its own durable reservation for a retry.
    Fresh provider qualification and the original Budget remain independently required.
    """
    from .runner import implementation

    if implementation(root) != auth['implementation_bindings']:
        raise ArtifactError('TRUSTED_IMPLEMENTATION_CHANGED_AFTER_ADMISSION')
    if sha(safe_path(root, authorization_path, prefix='workspace')) != authorization_sha:
        raise ArtifactError('OWNER_AUTHORIZATION_CHANGED_AFTER_ADMISSION')
    reference = auth['preservation_receipt']
    receipt = bound(root, reference['path'], reference['sha256'])
    created = datetime.fromisoformat(receipt['created_at'])
    if created.tzinfo is None or not 0 <= (datetime.fromisoformat(now()) - created).total_seconds() <= MAX_AGE_SECONDS:
        raise ArtifactError('STALE_PRESERVATION_RECEIPT')
    manifest, policy, result = load_trust(root, auth['trust_manifest'], auth['trust_manifest_sha256'])
    ctx = verify_plan_policy(plan, policy, root=root)
    if (receipt['context'] != ctx or receipt['preservation'] != result
            or receipt['policy_sha256'] != manifest['files']['POLICY.json']):
        raise ArtifactError('PRESERVATION_CHANGED_AFTER_ADMISSION')
