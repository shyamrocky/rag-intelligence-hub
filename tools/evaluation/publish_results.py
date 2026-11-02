"""Publish an opt-in immutable measurement descriptor, never a QA publication."""

import argparse
import json
from pathlib import Path

from tools.evaluation.contract import CONFIG, load_configuration
from tools.evaluation.runner import write_once
from tools.indexing.m5_index import local, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='data/evals/m9/runs/m9-v3')
    args = parser.parse_args()
    root = Path.cwd()
    out = local(root, args.run)
    frozen = json.loads((out / 'FROZEN_RUN_SPEC.json').read_bytes())
    load_configuration(root, expected_sha=frozen['configuration_sha256'])
    verified = json.loads((out / 'INDEPENDENT_METRIC_VERIFICATION.json').read_bytes())
    if (verified['status'] != 'PASS_INDEPENDENT_METRIC_ACCOUNTING'
            or verified['cases'] != 87 or verified['budget_observations'] != 348
            or verified['results_sha256'] != sha((out / 'RESULTS.json').read_bytes())):
        raise ValueError('m9_unverified_or_incomplete_result')
    def relative(name):
        return str((out / name).relative_to(root))
    manifest = {'schema': 'm9-measurement-manifest-1.0',
        'authority': 'MEASUREMENTS_ONLY_NOT_SOURCE_OR_QA_AUTHORITY',
        'status': 'CANDIDATE_PENDING_M9_OWNER_ACCEPTANCE',
        'configuration_path': CONFIG, 'configuration_sha256': frozen['configuration_sha256'],
        'results_path': relative('RESULTS.json'), 'results_sha256': sha((out / 'RESULTS.json').read_bytes()),
        'analysis_path': relative('ANALYSIS.json'), 'analysis_sha256': sha((out / 'ANALYSIS.json').read_bytes()),
        'verification_path': relative('INDEPENDENT_METRIC_VERIFICATION.json'),
        'verification_sha256': sha((out / 'INDEPENDENT_METRIC_VERIFICATION.json').read_bytes()),
        'oversized_path': relative('OVERSIZED_COST_ANALYSIS.json'),
        'oversized_sha256': sha((out / 'OVERSIZED_COST_ANALYSIS.json').read_bytes()),
        'benchmark_sha256': frozen['configuration']['benchmark']['sha256'],
        'approval_sha256': frozen['configuration']['approval']['sha256'],
        'questions': 29, 'answerable': 26, 'unsupported': 3, 'cases': 87,
        'budget_observations': 348, 'source_documents': 16, 'authorized_chunks': 992,
        'M10_authorized': False}
    write_once(out / 'manifest.json', manifest)
    selector = {'schema': 'm9-results-selection-1.0', 'manifest_path': relative('manifest.json'),
                'manifest_sha256': sha((out / 'manifest.json').read_bytes())}
    path = root / 'config/retrieval-evaluation-results-m9-v1.json'
    write_once(path, selector)
    print(json.dumps({'selector': str(path.relative_to(root)),
                      'selector_sha256': sha(path.read_bytes()),
                      'manifest_sha256': selector['manifest_sha256'],
                      'results_sha256': manifest['results_sha256']}, indent=2))


if __name__ == '__main__':
    main()
