"""Single read-only native/legacy attempt projection. No pipeline execution or writes."""
import hashlib
from decimal import Decimal

from .artifacts import ArtifactError, sha


def merge_native(root, records, store, rejected, *, include_unattempted=False):
    from tools.answer_quality.current import policy_reference
    from tools.generation_runner.dashboard import discover
    history = discover(root)
    rejected.extend(history['rejected'])
    for run in history['runs']:
        if run['manifest']['mode'] != 'live':
            continue
        base = run['manifest_path'].rsplit('/', 1)[0]
        for row in run['results']['questions']:
            qid = row['question_id']
            if qid not in records:
                continue
            try:
                if hashlib.sha256(records[qid]['question'].encode()).hexdigest() != row['question_sha256']:
                    raise ArtifactError('NATIVE_QUESTION_BINDING_MISMATCH')
                # Never merge a mock or planned-only record into real attempt totals.
                if not include_unattempted and not (row.get('generation_executed') or row.get('generation_attempted')):
                    continue
                source = base + f'/questions/{qid}/RESULT.json'
                store.bind(source, run['manifest']['files'][f'questions/{qid}/RESULT.json'])
                store.bind(run['manifest_path'], sha(store.root / run['manifest_path']))
                response = row.get('response')
                complete = isinstance(response, dict)
                ids = sorted({u for c in response['claims'] for u in c['evidence_unit_ids']}) if complete else []
                audit = row.get('audit', {})
                # Known plan bindings are not invented provider measurements.
                audit = {'request_sha256': row['request_sha256'], 'M8_package_sha256': row['M8_package_sha256'],
                    'model': run['plan'].get('model', 'UNAVAILABLE'),
                    'prompt_template': run['plan'].get('prompt_version', 'UNAVAILABLE'),
                    'response_schema': run['plan'].get('response_schema', 'UNAVAILABLE'),
                    'configuration_source': 'SEALED_PLAN_WITH_RECORDED_AUDIT_WHERE_AVAILABLE', **audit}
                attempt = {'experiment': base, 'question_id': qid, 'completed': complete,
                    'status': row['status'], 'response': response, 'row': row, 'run': run,
                    'response_ref': store.reference(source) if complete else None,
                    'response_file_sha256': run['manifest']['files'][f'questions/{qid}/RESULT.json'],
                    'audit_ref': store.reference(source), 'manifest_ref': store.reference(run['manifest_path']),
                    'audit': audit, 'usage': row.get('audit', {}).get('usage', {}),
                    'validation': row.get('post_validation'), 'cited_parent_ids': ids,
                    'supplied_parents': row.get('included_parents'), 'engineering_review': None,
                    'timestamp_or_version': run['manifest'].get('created_at', run['manifest']['run_id']),
                    'review_policy': policy_reference(root),
                    'source': {'manifest_path': run['manifest_path'], 'manifest_sha256': sha(store.root / run['manifest_path']),
                        'result_path': source, 'result_sha256': run['manifest']['files'][f'questions/{qid}/RESULT.json']}}
                if not any(a['experiment'] == base for a in records[qid]['attempts']):
                    records[qid]['attempts'].append(attempt)
            except (ArtifactError, KeyError, TypeError, ValueError):
                rejected.append({'status': 'UNAVAILABLE', 'reason': 'NATIVE_ATTEMPT_BINDING_FAILED'})
    for record in records.values():
        record['attempts'].sort(key=lambda a: a['timestamp_or_version'])
        completed = [a for a in record['attempts'] if a['completed']]
        record['latest'] = completed[-1] if completed else None
        record['latest_attempt'] = record['attempts'][-1] if record['attempts'] else None


def totals(records):
    attempts = [a for r in records.values() for a in r['attempts']]
    measured = [a for a in attempts if a['usage'].get('cost_status') == 'ESTIMATED_API_COST'
                and a['usage'].get('total_estimated_cost_usd') is not None]
    return {'attempt_records': len(attempts), 'attempted_questions': sum(bool(r['attempts']) for r in records.values()),
        'never_attempted': sum(not r['attempts'] for r in records.values()),
        'attempted_without_parsed_answer': sum(bool(r['attempts']) and not r['latest'] for r in records.values()),
        'measured_attempt_cost_usd': str(sum((Decimal(a['usage']['total_estimated_cost_usd']) for a in measured), Decimal(0))),
        'unknown_cost_attempts': len(attempts) - len(measured),
        'input_tokens_measured': sum(a['usage'].get('input_tokens') or 0 for a in attempts),
        'output_tokens_measured': sum(a['usage'].get('output_tokens') or 0 for a in attempts)}
