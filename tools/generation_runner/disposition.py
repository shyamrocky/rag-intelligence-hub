"""Output quality never substitutes for execution safety; no retry or admission waiver."""
from decimal import Decimal, InvalidOperation


def disposition(row, plan_row, settings, *, capture_verified):
    audit = row.get('audit', {})
    usage = audit.get('usage', {})
    reasons = []
    if (row.get('status') in {'BLOCKED_OR_FAILED', 'BLOCKED_INTEGRITY', 'RAW_RESPONSE_CAPTURE_FAILED', 'PROVIDER_ERROR'}
            or not audit.get('generation_executed')):
        reasons.append('EXECUTION_OR_INTEGRITY_FAILURE')
    if not capture_verified:
        reasons.append('RAW_CAPTURE_UNVERIFIED')
    if (not isinstance(audit.get('model'), str) or audit.get('model') != getattr(settings, 'model', None) or audit.get('request_sha256') != plan_row['request_sha256']
            or audit.get('M8_package_sha256') != plan_row['M8_package_sha256']
            or any(d.get('code') == 'RESPONSE_MODEL_MISMATCH' for d in audit.get('response_diagnostics', []))):
        reasons.append('MODEL_OR_REQUEST_BINDING_FAILURE')
    if audit.get('response_status') not in {'completed', 'incomplete'}:
        reasons.append('UNRESOLVED_PROVIDER_STATUS')
    counts = [usage.get(k) for k in ('input_tokens', 'output_tokens', 'total_tokens')]
    if (any(type(v) is not int or v < 0 for v in counts)
            or counts[0] != plan_row['input_tokens'] or counts[1] > settings.max_output_tokens
            or (all(type(v) is int for v in counts) and counts[0] + counts[1] != counts[2])):
        reasons.append('USAGE_OR_CONTEXT_MISMATCH')
    try:
        cost = Decimal(usage.get('total_estimated_cost_usd', 'NaN'))
        if (usage.get('cost_status') != 'ESTIMATED_API_COST' or not cost.is_finite() or cost < 0
                or cost > Decimal(plan_row['maximum_cost_usd'])
                or cost > Decimal(plan_row['per_question_cap_usd'])):
            reasons.append('UNKNOWN_OR_EXCEEDED_BILLING')
    except (InvalidOperation, TypeError, ValueError):
        reasons.append('UNKNOWN_OR_EXCEEDED_BILLING')
    if row.get('post_validation', {}).get('source_integrity') == 'FAIL':
        reasons.append('SOURCE_INTEGRITY_FAILURE')
    return {'schema': 'generation-batch-disposition-1.0',
            'action': 'STOP_SAFETY' if reasons else 'CONTINUE_INDEPENDENT_QUESTIONS',
            'reasons': reasons, 'answer_accepted': False, 'automatic_retry': False}
