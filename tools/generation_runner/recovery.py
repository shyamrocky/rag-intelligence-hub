"""Explicit, allowlisted recovery of one sealed run. Never a general history waiver.

Only the native trusted policy supplies this contract. It preserves the original
run, consumed authorization and full reservation. Every other admission still
blocks, including a second use of this recovery and unknown provider outcomes.
"""
import re
from decimal import Decimal

from tools.quality_dashboard.artifacts import ArtifactError, Store, safe_path, sha

SCHEMA = 'native-generation-recovery-1.0'
CONTINUATION_SCHEMA = 'native-generation-continuation-1.1'
RETRY = 'RETRY_COMPLETED_REJECTED_RESPONSE'
CONTINUE = 'CONTINUE_NEVER_EXECUTED'
BASE = 'data/evals/generation-runner'


def validate_scope(contract, question_ids, requests=None):
    if isinstance(contract, dict) and contract.get('schema') == CONTINUATION_SCHEMA:
        return _validate_continuation(contract, question_ids, requests)
    required = {'schema', 'parent_manifest', 'parent_authorization_use', 'question_ids',
                'dispositions', 'requests', 'maximum_additional_requests_per_question',
                'automatic_retries', 'excluded_question_ids', 'owner_permission_record'}
    if (not isinstance(contract, dict) or set(contract) != required
            or contract['schema'] != SCHEMA
            or contract['question_ids'] != list(question_ids)
            or not question_ids or len(set(question_ids)) != len(question_ids)
            or set(contract['dispositions']) != set(question_ids)
            or set(contract['requests']) != set(question_ids)
            or any(v not in {RETRY, CONTINUE} for v in contract['dispositions'].values())
            or type(contract['maximum_additional_requests_per_question']) is not int
            or contract['maximum_additional_requests_per_question'] != 1
            or type(contract['automatic_retries']) is not int or contract['automatic_retries'] != 0
            or set(question_ids) & (set(contract['excluded_question_ids']) | {'M9-Q05'})
            or not isinstance(contract['owner_permission_record'], str)
            or not contract['owner_permission_record'].strip()
            or (requests is not None and contract['requests'] != requests)):
        raise ArtifactError('RECOVERY_SCOPE_OR_REQUEST_MISMATCH')


def parent(root, contract):
    """Authenticate exact parent bytes, completed billing and absence of hidden attempts."""
    from .trust import context

    validate_scope(contract, contract.get('question_ids', []))
    if contract['schema'] == CONTINUATION_SCHEMA:
        parents = [parent(root, _single_parent(contract, ref)) for ref in contract['parents']]
        return {'schema': CONTINUATION_SCHEMA, 'parent_run_ids': [p['parent_run_id'] for p in parents],
                'parent_authorization_uses': [p['parent_authorization_use'] for p in parents],
                'parents': parents, 'question_ids': contract['question_ids'],
                'dispositions': contract['dispositions'], 'reservation_released_usd': '0'}
    store = Store(root)
    ref = contract['parent_manifest']
    path = safe_path(root, ref['path'], prefix=BASE)
    manifest = store.manifest(ref['path'], expected=ref['sha256'],
                              schema='grounded-generation-runner-1.0')
    base = path.parent.relative_to(root).as_posix()
    actual = {p.relative_to(path.parent).as_posix() for p in path.parent.rglob('*') if p.is_file()}
    if (actual != set(manifest['files']) | {'MANIFEST.json'}
            or manifest.get('mode') != 'live' or manifest.get('generation_authorized') is not True
            or manifest.get('status') != 'SEALED_PENDING_OWNER_REVIEW'
            or manifest.get('run_id') != path.parent.name):
        raise ArtifactError('RECOVERY_PARENT_NOT_SEALED_OR_CHANGED')
    plan = store.json(base + '/PLAN.json')
    ctx = context(plan)
    start = store.json(base + '/START.json')
    result = store.json(base + '/RESULTS.json')
    use_ref = contract['parent_authorization_use']
    use_path = BASE + '/authorization-use/' + manifest['authorization_sha256'] + '.json'
    if (use_ref['path'] != use_path or sha(safe_path(root, use_path, prefix=BASE)) != use_ref['sha256']
            or start.get('mode') != 'live' or start.get('generation_authorized') is not True
            or start.get('authorization_sha256') != manifest['authorization_sha256']
            or manifest['plan_sha256'] != ctx['plan_sha256']
            or result.get('mode') != 'live'):
        raise ArtifactError('RECOVERY_PARENT_ADMISSION_MISMATCH')
    store.bind(use_path, use_ref['sha256'])
    use = store.json(use_path)
    if (use.get('run_id') != manifest['run_id'] or use.get('question_ids') != ctx['question_ids']
            or use.get('authorization_sha256') != manifest['authorization_sha256']):
        raise ArtifactError('RECOVERY_PARENT_AUTHORIZATION_MISMATCH')
    selected = contract['question_ids']
    if (not set(selected) <= set(ctx['question_ids'])
            or any(contract['requests'][q] != ctx['requests'][q] for q in selected)):
        raise ArtifactError('RECOVERY_PARENT_REQUEST_CHANGED')
    rows = {q['question_id']: q for q in result['questions']}
    if len(rows) != len(result['questions']) or manifest['question_ids'] != list(rows):
        raise ArtifactError('RECOVERY_PARENT_RESULT_INVENTORY_MISMATCH')
    # No unknown billing may be waived, even for an unrelated earlier parent row.
    for qid, row in rows.items():
        audit, usage = row.get('audit', {}), row.get('audit', {}).get('usage', {})
        measured = Decimal(usage.get('total_estimated_cost_usd') or 'NaN')
        limit = Decimal(row['maximum_cost_usd'])
        if (row != store.json(base + f'/questions/{qid}/RESULT.json')
                or row.get('generation_executed') is not True
                or audit.get('generation_executed') is not True
                or audit.get('response_status') != 'completed'
                or usage.get('usage_status') != 'MEASURED_API_USAGE'
                or usage.get('cost_status') != 'ESTIMATED_API_COST'
                or usage.get('usage_errors') or usage.get('cost_reasons')
                or usage.get('model') != plan['model']
                or usage.get('input_tokens') != row['input_tokens']
                or not measured.is_finite() or measured <= 0 or measured > limit):
            raise ArtifactError('RECOVERY_UNKNOWN_OR_INVALID_PARENT_BILLING')
    for qid in selected:
        row = rows.get(qid)
        if contract['dispositions'][qid] == CONTINUE:
            if row is not None or (path.parent / 'questions' / qid).exists():
                raise ArtifactError('RECOVERY_CONTINUATION_ALREADY_ATTEMPTED')
        else:
            if (not row or row.get('response') is not None
                    or row.get('status') != 'INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE'
                    or row.get('source_integrity') != 'LIVE_M8_VALIDATED'):
                raise ArtifactError('RECOVERY_RETRY_REQUIRES_COMPLETED_REJECTED_RESPONSE')
            attempt = store.json(base + f'/questions/{qid}/LIVE_ATTEMPT.json')
            http = store.json(base + f'/questions/{qid}/GENERATION_HTTP_ATTEMPT.json')
            if (attempt.get('question_id') != qid or attempt.get('mode') != 'live'
                    or attempt.get('request_sha256') != contract['requests'][qid]['request_sha256']
                    or http.get('request_sha256') != attempt['request_sha256']
                    or http.get('method') != 'POST' or http.get('endpoint') != '/v1/responses'):
                raise ArtifactError('RECOVERY_RETRY_ATTEMPT_BINDING_MISMATCH')
    return {'parent_run_id': manifest['run_id'], 'parent_manifest': ref,
            'parent_authorization_use': use_ref, 'question_ids': selected,
            'dispositions': contract['dispositions'], 'reservation_released_usd': '0'}


def _single_parent(contract, reference):
    return {k: v for k, v in contract.items() if k not in {'parents', 'schema'}} | {
        'schema': SCHEMA, 'parent_manifest': reference['parent_manifest'],
        'parent_authorization_use': reference['parent_authorization_use']}


def _validate_continuation(contract, question_ids, requests):
    """Only never-executed questions, and only individually authenticated admissions.

    The exact parent set is pinned by the allowlisted trust policy. No caller waiver,
    automatic retry or reservation release is introduced. Legacy validation is reused
    independently for every parent, including all unrelated parent billing records.
    """
    fields = {'schema', 'parents', 'question_ids', 'dispositions', 'requests',
              'maximum_additional_requests_per_question', 'automatic_retries',
              'excluded_question_ids', 'owner_permission_record'}
    refs = contract.get('parents')
    if set(contract) != fields or not isinstance(refs, list) or len(refs) < 2:
        raise ArtifactError('CONTINUATION_EXACT_PARENT_SET_REQUIRED')
    manifests, uses = [], []
    for reference in refs:
        if not isinstance(reference, dict) or set(reference) != {'parent_manifest', 'parent_authorization_use'}:
            raise ArtifactError('CONTINUATION_PARENT_REFERENCE_INVALID')
        for key in ('parent_manifest', 'parent_authorization_use'):
            value = reference[key]
            if (not isinstance(value, dict) or set(value) != {'path', 'sha256'}
                    or not isinstance(value['path'], str) or not isinstance(value['sha256'], str)
                    or not re.fullmatch(r'[0-9a-f]{64}', value['sha256'])):
                raise ArtifactError('CONTINUATION_PARENT_REFERENCE_INVALID')
        validate_scope(_single_parent(contract, reference), question_ids, requests)
        manifests.append(reference['parent_manifest']['path'])
        uses.append(reference['parent_authorization_use']['path'])
    if (manifests != sorted(set(manifests)) or len(uses) != len(set(uses))
            or any(v != CONTINUE for v in contract['dispositions'].values())):
        raise ArtifactError('CONTINUATION_REQUIRES_DISTINCT_ORDERED_NEVER_EXECUTED_PARENTS')
