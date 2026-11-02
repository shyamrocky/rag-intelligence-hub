"""Explicit frozen measurement reader. Metrics never authorize source evidence."""

import json
from pathlib import Path

from tools.evaluation.contract import CONFIG, benchmark, load_configuration
from tools.evaluation.metrics import summarize
from tools.indexing.m5_index import encoded, read_bound

SELECTOR = 'config/retrieval-evaluation-results-m9-v1.json'


def load_results(root, *, expected_sha):
    root = Path(root).resolve(strict=True)
    selected = json.loads(read_bound(root, SELECTOR, expected_sha))
    if selected['schema'] != 'm9-results-selection-1.0':
        raise ValueError('m9_wrong_result_selection')
    manifest = json.loads(read_bound(root, selected['manifest_path'], selected['manifest_sha256']))
    if manifest['schema'] != 'm9-measurement-manifest-1.0':
        raise ValueError('m9_wrong_result_manifest')
    config, questions, labels = load_configuration(root, expected_sha=manifest['configuration_sha256'])
    if manifest['configuration_path'] != CONFIG:
        raise ValueError('m9_wrong_measured_configuration')
    benchmark(root)
    value = json.loads(read_bound(root, manifest['results_path'], manifest['results_sha256']))
    analysis = json.loads(read_bound(root, manifest['analysis_path'], manifest['analysis_sha256']))
    verification = json.loads(read_bound(root, manifest['verification_path'], manifest['verification_sha256']))
    oversized = json.loads(read_bound(root, manifest['oversized_path'], manifest['oversized_sha256']))
    if (verification['status'] != 'PASS_INDEPENDENT_METRIC_ACCOUNTING'
            or verification['results_sha256'] != manifest['results_sha256']
            or verification['cases'] != 87 or verification['budget_observations'] != 348
            or encoded(oversized) != encoded(analysis['oversized_current_cost_analysis'])):
        raise ValueError('m9_verification_or_cost_analysis_mismatch')
    expected = {(q['question_id'], m) for q in questions for m in config['settings']['modes']}
    actual = [(c['question_id'], c['mode']) for c in value['cases']]
    if (len(actual) != len(set(actual)) or set(actual) != expected
            or value['settings'] != config['settings'] or value['case_count'] != 87
            or value['budget_observation_count'] != 348
            or value['configuration_sha256'] != manifest['configuration_sha256']
            or value['integrity_failures']):
        raise ValueError('m9_incomplete_or_incompatible_measurements')
    computed = summarize(value['cases'], config['settings']['modes'], config['settings']['budgets'])
    if encoded(computed) != encoded(value['summary']):
        raise ValueError('m9_summary_does_not_match_measured_cases')
    return {'authority': 'MEASUREMENTS_ONLY_NOT_SOURCE_EVIDENCE', 'manifest': manifest,
            'questions': questions, 'labels': labels, 'results': value, 'analysis': analysis}
