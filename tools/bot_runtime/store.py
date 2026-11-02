"""Private immutable Bot records. Hashes attest bytes, never owner consent."""
import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, digest, read_json, sha

QUESTIONS = 'data/runtime-questions/v1'
RUNS = 'data/runtime-executions/v1'
ID = re.compile(r'BOT-[0-9]{6,12}\Z')
NONCE = re.compile(r'[a-f0-9]{32}\Z')


def now():
    return datetime.now(UTC).isoformat()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def directory(root, relative):
    root = Path(root).absolute()
    path = root / relative
    if not path.is_relative_to(root) or '..' in path.parts:
        raise ArtifactError('UNSAFE_RUNTIME_PATH')
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ArtifactError('UNSAFE_RUNTIME_PATH')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_mode & 0o077:
        path.chmod(0o700)
    return path


def write(path, value):
    """Exclusive, flushed write. Never overwrite an interrupted or sealed record."""
    body = (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read(path):
    path = Path(path)
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ArtifactError('UNSAFE_RUNTIME_PATH')
    return read_json(path)


@contextmanager
def locked(folder):
    fd = os.open(folder / 'LOCK', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def seal(folder, schema, **identity):
    files = {p.relative_to(folder).as_posix(): sha(p)
             for p in folder.rglob('*') if p.is_file() and p.name not in {'LOCK', 'MANIFEST.json'}}
    value = {'schema': schema, **identity, 'files': files}
    write(folder / 'MANIFEST.json', value)
    return value


def load(folder, schema):
    value = read(folder / 'MANIFEST.json')
    if value.get('schema') != schema or not value.get('files'):
        raise ArtifactError('INVALID_RUNTIME_MANIFEST')
    for name, expected in value['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or name in {'.', 'MANIFEST.json'}:
            raise ArtifactError('UNSAFE_RUNTIME_ARTIFACT')
        path = folder / name
        read(path)  # Also rejects symlinks and non-JSON artifacts in this contract.
        if sha(path) != expected:
            raise ArtifactError('RUNTIME_ARTIFACT_CHANGED')
    return value


def register(root, question, nonce):
    if not NONCE.fullmatch(nonce):
        raise ValueError('INVALID_SUBMISSION_NONCE')
    # Reuse the accepted normalization/character policy without starting retrieval.
    from tools.retrieval.contract import parameters
    canonical, _ = parameters(question, 'hybrid', 30, 50, 60, {}, {})
    if not canonical:
        raise ValueError('EMPTY_QUESTION')
    folder = directory(root, QUESTIONS)
    claims = directory(root, QUESTIONS + '/submissions')
    with locked(folder):
        claim = claims / (nonce + '.json')
        if claim.exists():
            value = read(claim)
            existing = verify_reference(root, value['question_id'], {'path': QUESTIONS + '/' + value['question_id'] + '/MANIFEST.json',
                'sha256': value['question_manifest_sha256']})
            if existing['question_text_sha256'] != text_sha(question):
                raise ArtifactError('SUBMISSION_NONCE_ALREADY_BOUND')
            return existing
        # Allocation markers survive interrupted registration. Never reuse a number.
        numbers = [int(p.name[4:]) for p in folder.iterdir() if ID.fullmatch(p.name)]
        qid = f'BOT-{max(numbers, default=0) + 1:06d}'
        qdir = folder / qid
        qdir.mkdir(mode=0o700)
        value = {'schema': 'runtime-question-1.0', 'question_id': qid, 'question_source': 'BOT',
            'question_text': question, 'question_text_sha256': text_sha(question),
            'question': canonical, 'question_sha256': text_sha(canonical), 'created_at': now(),
            'normalization': 'OUTER_WHITESPACE_ONLY', 'submission_nonce_sha256': text_sha(nonce),
            'cohort_id': None, 'answerability': 'UNASSESSED', 'evidence_label_status': 'UNLABELED',
            'mandatory_evidence_group_ids': None, 'offline_evaluation_eligible': False}
        write(qdir / 'QUESTION.json', value)
        seal(qdir, 'runtime-question-1.0', question_id=qid)
        write(claim, {'question_id': qid, 'question_manifest_sha256': sha(qdir / 'MANIFEST.json')})
        return value


def question_record(root, qid):
    if not ID.fullmatch(qid):
        raise ArtifactError('INVALID_BOT_ID')
    folder = Path(root) / QUESTIONS / qid
    manifest = load(folder, 'runtime-question-1.0')
    if set(manifest['files']) != {'QUESTION.json'}:
        raise ArtifactError('UNSEALED_RUNTIME_QUESTION')
    row = read(folder / 'QUESTION.json')
    if (row.get('question_id') != qid or manifest['question_id'] != qid
            or row.get('schema') != 'runtime-question-1.0' or row.get('question_source') != 'BOT'
            or row.get('question_sha256') != text_sha(row['question'])
            or row.get('question_text_sha256') != text_sha(row['question_text'])
            or row['question'] != row['question_text'].strip()
            or row.get('answerability') != 'UNASSESSED' or row.get('evidence_label_status') != 'UNLABELED'
            or row.get('cohort_id') is not None or row.get('mandatory_evidence_group_ids') is not None
            or row.get('offline_evaluation_eligible') is not False):
        raise ArtifactError('RUNTIME_QUESTION_BINDING_CHANGED')
    return row


def reference(root, qid):
    question_record(root, qid)
    path = QUESTIONS + '/' + qid + '/MANIFEST.json'
    return {'path': path, 'sha256': sha(Path(root) / path)}


def verify_reference(root, qid, ref):
    if reference(root, qid) != ref:
        raise ArtifactError('RUNTIME_QUESTION_REFERENCE_CHANGED')
    return question_record(root, qid)


def logical_identity(row):
    return digest({k: row.get(k) for k in ('question_id', 'question_sha256', 'request_sha256',
        'M8_package_sha256', 'response_sha256', 'validation_policy_sha256')})
