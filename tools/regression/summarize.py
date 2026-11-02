"""Account for declared jobs and the entire discovered test inventory; no QA authority."""

import json
import sys
from collections import Counter
from pathlib import Path

TEST_JOBS = {'current', 'historical', 'dashboard', 'chunking', 'm4', 'coordinator'}
PROJECT_SLUGS = ['root', 'apps-ingestion_dashboard', 'tools-chunking', 'tools-embeddings']
PREFLIGHT = {prefix + project for prefix in ['environment-', 'lock-'] for project in PROJECT_SLUGS}
PREFLIGHT |= {'inventory-root', 'inventory-chunking', 'inventory-embedding'}
REQUIRED_FULL = {'current', 'historical', 'dashboard', 'chunking', 'm4', 'm4-artifact-reader',
                 'lint', 'smoke'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_selection(data, *, collect_only=False):
    require(data['collect_only'] == collect_only, 'wrong_collection_receipt_kind')
    for key in ['collected_nodeids', 'selected_nodeids', 'deselected_nodeids', 'executed_nodeids']:
        require(len(data[key]) == len(set(data[key])), 'duplicate_test_accounting:' + key)
    collected, selected, deselected, executed = (
        set(data[key]) for key in ['collected_nodeids', 'selected_nodeids',
                                   'deselected_nodeids', 'executed_nodeids'])
    require(not selected & deselected and selected | deselected == collected,
            'unreported_or_wrong_deselection')
    require(executed <= selected and set(data['outcomes']) <= executed,
            'unexpected_executed_test')
    require(set(data['outcomes'].values()) <= {'PASSED', 'FAILED', 'ERROR', 'SKIPPED'},
            'unknown_test_outcome')
    if collect_only:
        require(not executed and not data['outcomes'], 'collection_claimed_test_execution')
    return {'collected': len(collected), 'selected': len(selected), 'executed': len(executed),
            'call_executed': len(data['call_executed_nodeids']),
            'deselected': len(deselected),
            'passed': list(data['outcomes'].values()).count('PASSED'),
            'failed': list(data['outcomes'].values()).count('FAILED'),
            'errored': list(data['outcomes'].values()).count('ERROR'),
            'skipped': list(data['outcomes'].values()).count('SKIPPED')}


def analyze(run, results, inventory, selections):
    names = [row['job'] for row in results]
    require(len(names) == len(set(names)), 'duplicate_job_accounting')
    required = set(run['expected_commands'])
    complete = set(names) == required and all(row['exit_code'] == 0 for row in results)
    expected_jobs = set(run['selected_jobs'])
    mandatory = PREFLIGHT | expected_jobs | ({'artifact-preflight'} if run['tier'] != 'fast' else set())
    require(required == mandatory, 'verification_plan_missing_required_command')
    if run['tier'] == 'fast':
        require(expected_jobs == {'m4-artifact-reader'}, 'missing_fast_artifact_gate')
    require(set(selections) == expected_jobs & TEST_JOBS, 'missing_test_job_receipt')
    for name, data in selections.items():
        validate_selection(data)
        require(set(data['selected_nodeids']) == set(data['executed_nodeids'])
                == set(data['outcomes']), 'selected_test_not_executed:' + name)
        complete = complete and data['exitstatus'] == 0 and all(
            value == 'PASSED' for value in data['outcomes'].values())
    all_nodes = set().union(*(set(data['outcomes']) for data in selections.values()))
    inventory_nodes = set().union(*(set(nodes) for nodes in inventory.values()))
    require(all_nodes <= inventory_nodes, 'execution_outside_collected_inventory')
    missing = sorted(inventory_nodes - all_nodes)
    if run['tier'] == 'full':
        require(expected_jobs == REQUIRED_FULL, 'missing_full_job_coverage')
        complete = complete and not missing
    counts = {name: validate_selection(data) for name, data in selections.items()}
    totals = Counter({k: 0 for k in [
        'collected', 'selected', 'executed', 'call_executed', 'deselected',
        'passed', 'failed', 'errored', 'skipped']})
    for values in counts.values():
        totals.update(values)
    return {'schema': 'regression-verification-summary-2.0',
            'status': ('PASS_' + run['tier'].upper()) if complete else 'INCOMPLETE_OR_FAILED',
            'tier': run['tier'], 'full_release_gate': run['tier'] == 'full' and complete,
            'jobs': results, 'job_test_counts': counts, 'test_totals_with_overlaps': dict(totals),
            'unique_tests_collected': len(inventory_nodes), 'unique_tests_executed': len(all_nodes),
            'overlap_executions': totals['executed'] - len(all_nodes),
            'not_executed_by_tier_or_failure': missing,
            'all_inventory_executed': not missing, 'all_commands_completed': set(names) == required,
            'scope': 'TEST_ONLY_NOT_QA_ADMISSION', 'm4_acceptance': 'PENDING', 'm5_authorized': False}


def validate_artifact_report(report, depth):
    require(report['schema'] == 'current-artifact-gate-2.0' and report['result'] == 'PASS'
            and report['depth'] == depth and report['inference'] is False,
            'missing_or_invalid_artifact_verification')
    require(report['shape'] == [992, 384] and report['records'] == 992
            and report['corpus']['units'] == 553 and report['corpus']['HOLD'] == 358
            and report['corpus']['membership_edges'] == 3727,
            'wrong_artifact_scope')
    require(report['all992_saved_input_token_vector_and_catalog_lineage_bindings'] is True,
            'incomplete_artifact_binding_verification')
    if depth == 'full':
        require(report['all992_live_parent_input_bindings'] is True
                and report['live_complete_parent_rehydrations'] == 992
                and report['protected_markdown_parents_checked'] == 4
                and report['unique_live_parents_checked'] == 553
                and report['C10_required_context_and_QA_observation_checked'] is True,
                'incomplete_full_parent_verification')


def observed_test_counts(output):
    totals = Counter({key: 0 for key in ['collected', 'selected', 'executed', 'call_executed',
                                        'deselected', 'passed', 'failed', 'errored', 'skipped']})
    issues = []
    for path in output.glob('*-selection.json'):
        if path.name.startswith('inventory-'):
            continue
        try:
            totals.update(validate_selection(json.loads(path.read_bytes())))
        except (ValueError, KeyError, TypeError) as exc:
            issues.append({'receipt': path.name, 'error': str(exc)})
    return {'test_totals_with_overlaps': dict(totals), 'accounting_errors': issues,
            'inventory_available': (output / 'INVENTORY.json').exists()}


def summarize(output):
    output = Path(output)
    run = json.loads((output / 'RUN.json').read_bytes())
    require(run['schema'] == 'regression-jobs-2.0', 'legacy_run_use_its_preserved_summary')
    results = json.loads((output / 'RESULTS.json').read_bytes())
    inventory = json.loads((output / 'INVENTORY.json').read_bytes())['nodeids_by_tree']
    selections = {name: json.loads((output / (name + '-selection.json')).read_bytes())
                  for name in run['selected_jobs'] if name in TEST_JOBS}
    artifacts = [('artifact-results.json', 'full' if run['tier'] == 'full' else 'fast')] if 'm4-artifact-reader' in run['selected_jobs'] else []
    if run['tier'] != 'fast':
        artifacts.append(('artifact-preflight.json', 'fast'))
    for name, depth in artifacts:
        validate_artifact_report(json.loads((output / name).read_bytes()), depth)
    summary = analyze(run, results, inventory, selections)
    summary['verified_artifact_reports'] = [name for name, _ in artifacts]
    (output / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    result = summarize(Path(sys.argv[1]))
    print(json.dumps({k: v for k, v in result.items() if k != 'jobs'}, indent=2))
    sys.exit(int(not result['status'].startswith('PASS_')))
