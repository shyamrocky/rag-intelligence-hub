"""Frozen owner-reviewed evaluation inputs; never source admission authority."""

import json
from pathlib import Path

from tools.indexing.m5_index import encoded, read_bound, sha

BENCHMARK = 'data/evals/m9/benchmark-v1/BENCHMARK_MANIFEST.json'
BENCHMARK_SHA = '17f1c6594ff7e435b3f0da636165c4daf105f9a768f13bac80742eb33640065d'
APPROVAL = 'data/evals/m9/approvals/benchmark-v1.json'
APPROVAL_SHA = '5ba3cd13ee814b18094627b29a7761cff76859d7f7329a544cbd45e889f6477c'
CONFIG = 'config/retrieval-evaluation-m9-v3.json'
COMPONENTS = ('tools/evaluation/contract.py', 'tools/evaluation/metrics.py',
              'tools/evaluation/runner.py')
SETTINGS = {'modes': ['bm25', 'vector', 'hybrid'], 'top_k': 10, 'candidate_depth': 50,
            'rrf_k': 60, 'filters': {}, 'cutoffs': [1, 3, 5, 10],
            'budgets': [4000, 8000, 16000, 32000]}


def benchmark(root):
    root = Path(root).resolve(strict=True)
    manifest = json.loads(read_bound(root, BENCHMARK, BENCHMARK_SHA))
    approval = json.loads(read_bound(root, APPROVAL, APPROVAL_SHA))
    if (approval['status'] != 'OWNER_APPROVED_GROUND_TRUTH'
            or approval['benchmark_manifest'] != {'path': BENCHMARK, 'sha256': BENCHMARK_SHA}
            or approval['approved_question_ids'] != [f'M9-Q{i:02}' for i in range(1, 30)]
            or approval['no_revisions_or_rejections'] is not True):
        raise ValueError('m9_owner_approval_not_exact')
    base = str(Path(BENCHMARK).parent)
    files = {name: json.loads(read_bound(root, base + '/' + name, row['sha256']))
             for name, row in manifest['files'].items() if name.endswith('.json')}
    for name, row in manifest['files'].items():
        read_bound(root, base + '/' + name, row['sha256'])
    questions, labels = files['QUESTION_SET.json'], files['PROPOSED_EVIDENCE_LABELS.json']
    if (labels['question_set_sha256'] != sha(encoded(questions))
            or len(questions['questions']) != 29 or len(labels['labels']) != 29
            or [x['question_id'] for x in questions['questions']] != approval['approved_question_ids']
            or [x['question_id'] for x in labels['labels']] != approval['approved_question_ids']):
        raise ValueError('m9_benchmark_labels_mismatch')
    return manifest, questions['questions'], {x['question_id']: x for x in labels['labels']}


def load_configuration(root, *, expected_sha):
    config = json.loads(read_bound(root, CONFIG, expected_sha))
    if (config['schema'] != 'm9-evaluation-config-1.0' or config['settings'] != SETTINGS
            or config['benchmark'] != {'path': BENCHMARK, 'sha256': BENCHMARK_SHA}
            or config['approval'] != {'path': APPROVAL, 'sha256': APPROVAL_SHA}
            or set(config['components']) != set(COMPONENTS)):
        raise ValueError('m9_unapproved_configuration')
    for name, digest in config['components'].items():
        read_bound(root, name, digest)
    manifest, questions, labels = benchmark(root)
    for binding in manifest['selected_releases'].values():
        read_bound(root, binding['path'], binding['sha256'])
    return config, questions, labels
