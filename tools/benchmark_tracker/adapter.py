"""Source-free run tracker built from existing verified readers, never execution."""
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store, digest

ROLLOUT = 'data/evals/generation-rollout/v1'
BATCHES = 'data/evals/generation-runner-reviews/seven-batch-qualification-v1'
STATUSES = {'ANSWERED', 'PARTIAL', 'ABSTAINED'}


def stages(root):
    store = Store(root)
    store.manifest(ROLLOUT + '/MANIFEST.json')
    rollout = store.json(ROLLOUT + '/ROLLOUT.json')
    groups = [('Historical', rollout['historical_completed'])]
    for name in ('canary', 'pilot'):
        plan = store.json(f'{ROLLOUT}/{name}/PLAN.json')
        groups.append((name.title(), [q['question_id'] for q in plan['questions']]))
    store.manifest(BATCHES + '/MANIFEST.json')
    for number in range(1, 8):
        plan = store.json(f'{BATCHES}/batch-{number:02}/PLAN_NOT_AUTHORIZED.json')
        groups.append((f'Batch {number}', [q['question_id'] for q in plan['questions']]))
    ids = [qid for _, questions in groups for qid in questions]
    if len(ids) != len(set(ids)):
        raise ArtifactError('TRACKER_DUPLICATE_STAGE_QUESTION')
    return groups


def selected_attempt(record):
    """Native history is ordered; legacy funded response remains selectable explicitly."""
    attempts = record['attempts']
    native = [a for a in attempts if a.get('run')]
    if native:
        return max(native, key=lambda a: (a['timestamp_or_version'], a['experiment']))
    # Legacy versions are not chronological timestamps. Never hide the funded Q05
    # response behind the lexical name of its earlier credit-balance failure.
    return record['latest'] or record.get('latest_attempt')


def returned_status(root, attempt):
    """Extract only a declaration from verified private data; never return source text."""
    if attempt.get('response') is not None:
        return attempt['response']['status'], 'ACCEPTED_STRUCTURED_RESPONSE', 'NOT_RECORDED'
    row = attempt.get('row', {})
    receipt = row.get('audit', {}).get('raw_response_capture')
    if not receipt:
        return 'UNAVAILABLE', 'CONTRACT_REJECTED', 'UNAVAILABLE_HISTORICAL'
    from tools.generation.response_capture import verify_capture
    try:
        raw = verify_capture(root, receipt, row, run_id=attempt['run']['manifest']['run_id'])
        if raw is None:
            return 'UNAVAILABLE', 'CONTRACT_REJECTED', receipt['status']
        # Reuse the existing pure observation parser, not a validator or generator.
        from tools.generation.observation import observe
        candidate = observe(json.loads(raw.read_bytes())).get('candidate')
        status = candidate.get('status') if isinstance(candidate, dict) else None
        return status if status in STATUSES else 'UNAVAILABLE', 'CONTRACT_REJECTED', 'CAPTURED_VERIFIED'
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        return 'UNAVAILABLE', 'CONTRACT_REJECTED', 'UNAVAILABLE_OR_UNVERIFIED'


def capture_status(root, attempt):
    row = attempt.get('row', {})
    receipt = row.get('audit', {}).get('raw_response_capture')
    if not receipt:
        return 'NOT_RECORDED_HISTORICAL'
    from tools.generation.response_capture import verify_capture
    try:
        raw = verify_capture(root, receipt, row, run_id=attempt['run']['manifest']['run_id'])
        return 'CAPTURED_VERIFIED' if raw else receipt['status']
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        return 'UNAVAILABLE_OR_UNVERIFIED'


def assessment_matches(assessment, attempt, question_hash):
    response = attempt.get('response')
    if response is None:
        return False
    expected = {'question_sha256': question_hash, 'response_sha256': digest(response),
                'request_sha256': attempt['audit']['request_sha256'],
                'M8_package_sha256': attempt['audit']['M8_package_sha256']}
    return all(assessment.get(key) == value for key, value in expected.items())


def reassessments(root, chosen, records):
    """Existing sealed technical assessments only; never import or invent a review."""
    found, rejected = {}, []
    candidates = [*(Path(root) / 'data/evals/human-review/preparations').glob('*/MANIFEST.json'),
                  *(Path(root) / 'data/evals/answer-quality').glob('*/MANIFEST.json')]
    for path in sorted(candidates):
        try:
            store = Store(root)
            ref = path.relative_to(root).as_posix()
            manifest = store.manifest(ref)
            files = manifest['files']
            base = ref.rsplit('/', 1)[0]
            if 'MATERIALS.json' in files:
                material = store.json(base + '/MATERIALS.json')
                assessment = material.get('fresh_technical_validation', {})
                source = material.get('response_source', {})
            elif 'ASSESSMENT.json' in files:
                assessment = store.json(base + '/ASSESSMENT.json')
                source = manifest.get('response_source', {})
            else:
                continue
            qid = assessment.get('question_id')
            if not qid and source:
                qid = next((q for q, a in chosen.items() if a and a.get('source') == source), None)
            attempt = chosen.get(qid)
            if not attempt or (source and source != attempt.get('source')):
                continue
            if not assessment_matches(assessment, attempt, records[qid]['reference']['question_text_sha256']):
                continue
            # A self-sealed file is not authenticated human semantic acceptance.
            if assessment.get('overall_status') not in {'REVIEW_REQUIRED', 'VALIDATION_FAILED', 'INDETERMINATE', 'FAILED'}:
                continue
            value = {'created_at': manifest.get('created_at', ''), 'reference': ref, 'assessment': assessment,
                     'preparation': 'PREPARATION.json' in files}
            if qid not in found or (value['created_at'], ref) > (found[qid]['created_at'], found[qid]['reference']):
                found[qid] = value
        except (ArtifactError, ValueError, KeyError, TypeError, OSError):
            rejected.append(path.parent.name)
    return found, rejected


def review_state(attempt, decisions):
    if not attempt.get('response'):
        return 'DIAGNOSTIC_TRIAGE_ONLY'
    expected = {'response_sha256': digest(attempt['response']),
                'request_sha256': attempt['audit']['request_sha256'],
                'package_sha256': attempt['audit']['M8_package_sha256']}
    matches = [(value, path) for value, path in decisions
               if value['question_id'] == attempt['question_id']
               and all(value['bindings'].get(k) == v for k, v in expected.items())]
    if not matches:
        return 'PENDING_REVIEW'
    value, _ = max(matches, key=lambda item: (item[0]['decided_at'], item[1]))
    return value['status']


def findings(post, original, attempt, record):
    notes = []
    for error in attempt['audit'].get('response_diagnostics', []):
        path = '.'.join(str(p) for p in error.get('path', [])) or 'response root'
        notes.append(f"{error['code']} at {path}")
    quotes = post.get('quotation_fidelity', post.get('quotations', []))
    counts = Counter(q['outcome'] for q in quotes if q.get('outcome'))
    if counts:
        notes.append('; '.join(f'{number} {kind}' for kind, number in sorted(counts.items())))
    elif post.get('quote_checks', {}).get('all_verbatim'):
        notes.append(f"{len(post['quote_checks']['checks'])} exact quotations")
    if any(c.get('status') == 'INVALID_CITATION' for c in post.get('citations', [])):
        notes.append('Unauthorized evidence reference; no ID repaired')
    measurement = record.get('completion')
    if measurement:
        required = measurement['required_groups']
        delivered = measurement['m8']['delivered_groups']
        if required and delivered != required:
            notes.append(f'M8 delivered {delivered}/{required} approved groups; known evidence gap')
    if record['reference']['answerability'] == 'UNSUPPORTED':
        status = (attempt.get('response') or {}).get('status')
        notes.append('PRIORITY: ANSWERED on unsupported control' if status == 'ANSWERED'
                     else 'Unsupported control: abstention appropriateness needs independent review')
    qualification = post.get('qualification_status')
    if qualification == 'QUALIFICATION_APPLICABILITY_UNDETERMINED':
        notes.append('Qualification applicability unresolved')
    if original != post.get('overall_status'):
        notes.append(f'Original validation {original} preserved; separate reassessment shown')
    if not notes:
        notes.append('Independent semantic grounding and completeness remain pending')
    return ' · '.join(notes)


def build(root, data=None):
    from tools.human_review.local_poc import discover as decisions_reader
    from tools.quality_dashboard.completion_adapter import load_completed

    data = data if data is not None else load_completed(root)
    if data['rejected']:
        raise ArtifactError('TRACKER_UNVERIFIED_TELEMETRY')
    groups = stages(root)
    if {q for _, ids in groups for q in ids} != set(data['records']):
        raise ArtifactError('TRACKER_STAGE_INVENTORY_MISMATCH')
    chosen = {qid: selected_attempt(record) for qid, record in data['records'].items()}
    newer, rejected_assessments = reassessments(root, chosen, data['records'])
    decisions, bad_decisions = decisions_reader(root)
    rows, totals = [], []
    for stage, ids in groups:
        cost, missing, count, inputs, outputs = Decimal(0), 0, 0, 0, 0
        for qid in ids:
            record, attempt = data['records'][qid], chosen[qid]
            for a in record['attempts']:
                count += 1
                usage = a.get('usage', {})
                amount = usage.get('total_estimated_cost_usd')
                if amount is None:
                    missing += 1
                else:
                    cost += Decimal(amount)
                inputs += usage.get('input_tokens') or 0
                outputs += usage.get('output_tokens') or 0
            if attempt is None:
                rows.append({'Stage': stage, 'Question': qid, 'Question text': record['question'],
                             'Model status': 'NOT_RUN', 'Validation': 'NOT_RUN', 'Main findings': 'No generation attempt'})
                continue
            declared, contract, raw = returned_status(root, attempt)
            if attempt.get('response'):
                raw = capture_status(root, attempt)
            original = (attempt.get('validation') or {}).get('overall_status',
                         (attempt.get('validation') or {}).get('status', 'NOT_RUN'))
            assessment = newer.get(qid)
            post = assessment['assessment'] if assessment else attempt.get('validation') or {}
            owner = review_state(attempt, decisions)
            if assessment and assessment['preparation'] and owner == 'BLOCKED_TECHNICAL':
                from tools.human_review.preparation import read as read_preparation
                from tools.human_review.review_state import recorded_review_required
                if recorded_review_required(root, read_preparation(root, assessment['reference'])):
                    owner = 'COMPLETENESS_ACCEPTED / GROUNDING_REVIEW_REQUIRED'
            validation = post.get('overall_status', post.get('status', 'NOT_RUN'))
            if contract == 'CONTRACT_REJECTED' and validation in {'NOT_RUN', 'NOT_RUN_NO_VALID_RESPONSE'}:
                validation = 'CONTRACT_REJECTED / POST_CHECKS_NOT_RUN'
            usage = attempt.get('usage', {})
            rows.append({'Stage': stage, 'Question': qid, 'Question text': record['question'],
                'Cohort': record['reference']['cohort_label'], 'Model status': declared,
                'Contract': contract, 'Validation': validation, 'Original validation': original,
                'Owner review': owner,
                'Main findings': findings(post, original, attempt, record),
                'Estimated API cost USD': usage.get('total_estimated_cost_usd'),
                'Input tokens': usage.get('input_tokens'), 'Output tokens': usage.get('output_tokens'),
                'API seconds': round(usage['latency_ms'] / 1000, 3) if usage.get('latency_ms') is not None else None,
                'Raw response': raw, 'Attempts': len(record['attempts']),
                'Prompt': attempt['audit'].get('prompt_template', 'UNAVAILABLE'),
                'Model': attempt['audit'].get('model', 'UNAVAILABLE'),
                'Experiment': attempt['experiment'],
                'Reassessment reference': assessment['reference'] if assessment else None})
        totals.append({'Stage': stage, 'Questions': len(ids), 'Attempt records': count,
                       'Known estimated API cost USD': str(cost), 'Unknown-cost attempts': missing,
                       'Measured input tokens': inputs, 'Measured output tokens': outputs})
    return {'rows': rows, 'batches': totals, 'summary': data['summary'],
            'unverified_review_records': bad_decisions,
            'unverified_assessment_records': len(rejected_assessments)}
