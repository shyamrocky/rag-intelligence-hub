"""Private response bytes; public receipts contain identities and hashes only."""
import hashlib
import json
import os
import re
from pathlib import Path

from tools.preflight_suite.artifacts import now
from tools.quality_dashboard.artifacts import ArtifactError, digest, safe_path, sha

SCHEMA = 'generation-response-capture-1.0'
BASE = 'workspace/generation-response-captures'
NAME = 'RAW_RESPONSE_CAPTURE.json'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\Z')


def _directory(root, relative):
    current = Path(root)
    for part in relative.split('/'):
        if not ID.fullmatch(part) or part in {'.', '..'}:
            raise ArtifactError('UNSAFE_CAPTURE_PATH')
        current /= part
        if current.is_symlink():
            raise ArtifactError('UNSAFE_CAPTURE_PATH')
        current.mkdir(mode=0o700, exist_ok=True)
        if not current.is_dir():
            raise ArtifactError('UNSAFE_CAPTURE_PATH')
        if current.is_relative_to(Path(root) / BASE) and current.stat().st_mode & 0o077:
            raise ArtifactError('UNSAFE_CAPTURE_PERMISSIONS')
    return current


def _write(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class ResponseCapture:
    def __init__(self, root, qdir, *, question_id, run_id, request_sha256,
                 package_sha256, mode):
        self.root, self.qdir = Path(root).resolve(), Path(qdir)
        if not ID.fullmatch(question_id) or not ID.fullmatch(run_id):
            raise ArtifactError('UNSAFE_CAPTURE_IDENTITY')
        self.context = {'question_id': question_id, 'run_id': run_id,
                        'request_sha256': request_sha256, 'M8_package_sha256': package_sha256,
                        'mode': mode.upper()}
        self.relative = BASE + '/' + run_id + '/' + question_id
        self.receipt = None

    def capture(self, body, *, http_status=None, unavailable_reason=None):
        """Called before decoding. Never raise publisher/provider exception text."""
        if self.receipt is not None:
            raise ArtifactError('RESPONSE_CAPTURE_ALREADY_ATTEMPTED')
        value = {'schema': SCHEMA, 'created_at': now(), 'context': self.context,
                 'capture_id': digest(self.context), 'http_status': http_status,
                 'artifact': None, 'status': 'RAW_RESPONSE_UNAVAILABLE',
                 'reason': unavailable_reason}
        try:
            if body is not None:
                if type(body) is not bytes:
                    raise TypeError('RESPONSE_BODY_BYTES_REQUIRED')
                folder = _directory(self.root, self.relative)
                path = folder / 'RAW_RESPONSE.body'
                _write(path, body)
                expected = hashlib.sha256(body).hexdigest()
                if sha(path) != expected:
                    raise ArtifactError('RAW_RESPONSE_HASH_MISMATCH')
                value.update(status='RAW_RESPONSE_CAPTURED', reason=None,
                             artifact={'path': path.relative_to(self.root).as_posix(),
                                       'sha256': expected, 'bytes': len(body)})
            relative_qdir = self.qdir.relative_to(self.root).as_posix()
            _directory(self.root, relative_qdir)
            _write(self.qdir / NAME, json.dumps(value, sort_keys=True, indent=2).encode())
        except (OSError, ValueError, TypeError) as error:
            value.update(status='RAW_RESPONSE_CAPTURE_FAILED', artifact=None,
                         reason='ARTIFACT_PERSISTENCE_ERROR', error_type=type(error).__name__)
        self.receipt = value
        return value


def verify_capture(root, receipt, row, *, run_id):
    required = {'schema', 'created_at', 'context', 'capture_id', 'http_status', 'artifact', 'status', 'reason'}
    if (receipt.get('schema') != SCHEMA or not required <= set(receipt)
            or set(receipt) - required - {'error_type'}
            or receipt.get('status') not in {'RAW_RESPONSE_CAPTURED', 'RAW_RESPONSE_CAPTURE_FAILED', 'RAW_RESPONSE_UNAVAILABLE'}):
        raise ArtifactError('INVALID_CAPTURE_RECEIPT')
    context = receipt['context']
    if (context.get('question_id') != row['question_id'] or context.get('run_id') != run_id
            or context.get('request_sha256') != row['request_sha256']
            or context.get('M8_package_sha256') != row['M8_package_sha256']
            or context.get('mode') != row['mode'].upper()
            or receipt.get('capture_id') != digest(context)):
        raise ArtifactError('CAPTURE_BINDING_MISMATCH')
    if receipt['status'] != 'RAW_RESPONSE_CAPTURED':
        if receipt.get('artifact') is not None:
            raise ArtifactError('FALSE_RAW_RESPONSE_REFERENCE')
        return None
    reference = receipt['artifact']
    expected = BASE + '/' + run_id + '/' + row['question_id'] + '/RAW_RESPONSE.body'
    if reference['path'] != expected:
        raise ArtifactError('CAPTURE_PATH_BINDING_MISMATCH')
    path = safe_path(root, reference['path'], prefix=BASE)
    if (sha(path) != reference['sha256'] or path.stat().st_size != reference['bytes']
            or any(p.stat().st_mode & 0o077 for p in [path, path.parent, path.parent.parent,
                                                   Path(root) / BASE])):
        raise ArtifactError('RAW_RESPONSE_UNVERIFIED_OR_UNSAFE')
    return path
