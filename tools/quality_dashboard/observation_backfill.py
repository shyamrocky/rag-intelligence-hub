"""Explicit offline derived receipts; never called on dashboard refresh."""
from pathlib import Path
from uuid import uuid4

from tools.generation.observation import VERSION, field_checks
from tools.preflight_suite.artifacts import now, save
from tools.quality_dashboard.artifacts import Store, digest, sha

BASE = 'data/evals/response-observations'


def publish(root, attempt, observation, *, package=None):
    folder = Path(root) / BASE / uuid4().hex
    value = {'schema': VERSION, 'created_at': now(), 'question_id': attempt['question_id'],
        'experiment': attempt['experiment'], 'result_sha256': attempt['response_file_sha256'],
        'request_sha256': attempt['audit']['request_sha256'],
        'M8_package_sha256': attempt['audit']['M8_package_sha256'],
        'observation_state': observation['state'], 'semantic_status': 'NOT_ASSESSED',
        'historical_verdict_unchanged': True, 'owner_approval_created': False,
        'provider_calls': 0, 'original_validation': attempt.get('validation'),
        'field_checks': field_checks(observation, package) if package else {'status': 'UNAVAILABLE_NO_RETAINED_CONTEXT'},
        'raw_sha256': attempt.get('row', {}).get('audit', {}).get('raw_response_capture', {}).get('artifact')}
    # The raw reference contains hashes/path only. No answer, quote or publisher passage.
    save(folder / 'OBSERVATION.json', value)
    save(folder / 'MANIFEST.json', {'schema': VERSION, 'files': {'OBSERVATION.json': sha(folder / 'OBSERVATION.json')}})
    return (folder / 'MANIFEST.json').relative_to(root).as_posix()


def find(root, attempt):
    values = []
    for file in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        store = Store(root)
        store.manifest(file.relative_to(root).as_posix(), schema=VERSION)
        value = store.json(file.parent.relative_to(root).as_posix() + '/OBSERVATION.json')
        if (value['experiment'] == attempt['experiment'] and value['question_id'] == attempt['question_id']
                and value['result_sha256'] == attempt['response_file_sha256']
                and value['request_sha256'] == attempt['audit']['request_sha256']
                and value['M8_package_sha256'] == attempt['audit']['M8_package_sha256']
                and value['provider_calls'] == 0 and value['owner_approval_created'] is False):
            values.append(value)
    return max(values, key=lambda v: (v['created_at'], digest(v))) if values else None
