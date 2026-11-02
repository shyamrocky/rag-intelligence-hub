"""Retain already-authorized in-memory M8 for review; never reconstruct on refresh."""
import json

from tools.generation.response_capture import _directory, _write
from tools.quality_dashboard.artifacts import ArtifactError, sha


def retain(root, qdir, row, package, m7):
    relative = 'workspace/generation-review-material/' + qdir.parent.parent.name + '/' + row['question_id']
    folder = _directory(root, relative)
    if any(p.stat().st_mode & 0o077 for p in (folder, folder.parent, folder.parent.parent)):
        raise ArtifactError('UNSAFE_REVIEW_MATERIAL_PERMISSIONS')
    path = folder / 'MATERIAL.json'
    _write(path, json.dumps({'M8_package': package, 'M7_result': m7},
                            ensure_ascii=False, sort_keys=True).encode())
    return {'schema': 'generation-review-material-1.0',
            'request_sha256': row['request_sha256'], 'M8_package_sha256': row['M8_package_sha256'],
            'M7_result_sha256': row['M7_result_sha256'],
            'artifact': {'path': relative + '/MATERIAL.json', 'sha256': sha(path)}}
