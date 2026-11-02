"""Explicit local-operator enrollment, encrypted Ed25519 keys and signed key history.

The OS account is the bootstrap authority. This is possession + passphrase
authentication, not third-party verification of a person's legal name. No keys
are created on import or dashboard refresh. No provider SDK or network access.
"""
import base64
import fcntl
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from tools.preflight_suite.artifacts import now
from tools.quality_dashboard.artifacts import ArtifactError, digest, read_json

OPENSSL = '/opt/homebrew/bin/openssl' if Path('/opt/homebrew/bin/openssl').is_file() else '/usr/bin/openssl'
DOMAIN = b'RAG-HUMAN-REVIEW-1.0\x00'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def default_store():
    return Path.home() / '.config/rag-intelligence-hub/human-review'


def secure(path, *, directory=False):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ArtifactError('UNSAFE_REVIEW_CREDENTIAL_PATH')
    st = path.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ArtifactError('REVIEW_CREDENTIAL_PERMISSIONS_REQUIRED')
    if directory != path.is_dir() or (not directory and not path.is_file()):
        raise ArtifactError('INVALID_REVIEW_CREDENTIAL_PATH')
    return path


def write_new(path, value):
    data = canonical(value) + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


@contextmanager
def locked(store):
    store = secure(store, directory=True)
    fd = os.open(store / 'LOCK', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield store
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def crypto(args, *, secret=None, data=None):
    """Passphrases use an inherited pipe, never argv/env/files/diagnostic output."""
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LC_ALL': 'C'}
    rd = wr = None
    try:
        if secret is not None:
            if (not isinstance(secret, str) or not 1 <= len(secret.encode()) <= 1024
                    or any(c in secret for c in '\r\n\x00')):
                raise ArtifactError('INVALID_REVIEW_PASSPHRASE')
            rd, wr = os.pipe()
            os.write(wr, secret.encode() + b'\n')
            os.close(wr)
            wr = None
            args = [f'fd:{rd}' if a == 'SECRET_FD' else a for a in args]
        result = subprocess.run([OPENSSL, *args], input=data, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env, pass_fds=(rd,) if rd is not None else (),
            timeout=20, check=False)
        if result.returncode:
            raise ArtifactError('REVIEW_SIGNATURE_OR_CREDENTIAL_INVALID')
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise ArtifactError('LOCAL_SIGNING_BACKEND_UNAVAILABLE') from None
    finally:
        for fd in (rd, wr):
            if fd is not None:
                os.close(fd)


def keygen(path, passphrase):
    if len(passphrase) < 12:
        raise ArtifactError('REVIEW_PASSPHRASE_MINIMUM_12_CHARACTERS')
    # Exclusive reservation before OpenSSL writes the encrypted private material.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    crypto(['genpkey', '-algorithm', 'ED25519', '-aes-256-cbc', '-pass', 'SECRET_FD',
            '-out', str(path)], secret=passphrase)
    return crypto(['pkey', '-in', str(path), '-passin', 'SECRET_FD', '-pubout'],
                  secret=passphrase).decode()


def sign(value, key, passphrase):
    # Ed25519 one-shot signing requires a seekable input on supported OpenSSL builds.
    with tempfile.TemporaryDirectory(prefix='rag-review-sign-') as folder:
        message = Path(folder) / 'message'
        message.write_bytes(DOMAIN + canonical(value))
        message.chmod(0o600)
        return base64.b64encode(crypto(['pkeyutl', '-sign', '-rawin', '-inkey', str(secure(key)),
            '-in', str(message), '-passin', 'SECRET_FD'], secret=passphrase)).decode()


def verify(value, signature, public_key):
    try:
        raw = base64.b64decode(signature, validate=True)
        with tempfile.TemporaryDirectory(prefix='rag-review-verify-') as folder:
            path = Path(folder)
            (path / 'public.pem').write_text(public_key)
            (path / 'signature').write_bytes(raw)
            (path / 'message').write_bytes(DOMAIN + canonical(value))
            crypto(['pkeyutl', '-verify', '-rawin', '-pubin', '-inkey', str(path / 'public.pem'),
                    '-sigfile', str(path / 'signature'), '-in', str(path / 'message')])
    except (ValueError, TypeError):
        raise ArtifactError('INVALID_REVIEW_SIGNATURE') from None


def enrollment_confirmation(reviewer_id, display_name):
    return f'REGISTER {reviewer_id} AS {display_name}'


def register(store, reviewer_id, display_name, passphrase, confirmation):
    """Interactive operator only. Caller must not infer or invent either identity field."""
    if (not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}', reviewer_id)
            or not display_name.strip() or len(display_name) > 100
            or any(ord(c) < 32 for c in display_name)
            or confirmation != enrollment_confirmation(reviewer_id, display_name)):
        raise ArtifactError('EXPLICIT_REVIEWER_ENROLLMENT_REQUIRED')
    store = Path(store).absolute()
    if store.exists() or any(p.is_symlink() for p in [store, *store.parents]):
        raise ArtifactError('NEW_PRIVATE_REVIEW_STORE_REQUIRED')
    store.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # A failed enrollment remains an untrusted .pending directory, not a registration.
    with tempfile.TemporaryDirectory(dir=store.parent, prefix='.review-enrollment-') as folder:
        temp = Path(folder)
        public = keygen(temp / 'key-0.pem', passphrase)
        event = {'schema': 'local-reviewer-event-1.0', 'operation': 'REGISTER',
            'reviewer_id': reviewer_id, 'display_name': display_name, 'public_key': public,
            'created_at': now(), 'previous_sha256': None, 'key_file': 'key-0.pem'}
        journal = [{'event': event, 'signature': sign(event, temp / 'key-0.pem', passphrase)}]
        write_new(temp / 'ANCHOR.json', {'schema': 'local-reviewer-anchor-1.0',
            'reviewer_id': reviewer_id, 'public_key': public, 'registration_sha256': digest(journal[0])})
        write_new(temp / 'REGISTRY.json', journal)
        os.mkdir(store, 0o700)  # Never replace a concurrent registration.
        for p in temp.iterdir():
            os.rename(p, store / p.name)
    return registry(store)


def registry(store):
    store = secure(store, directory=True)
    anchor = read_json(secure(store / 'ANCHOR.json'))
    journal = read_json(secure(store / 'REGISTRY.json'))
    if not isinstance(journal, list) or not journal or digest(journal[0]) != anchor['registration_sha256']:
        raise ArtifactError('REVIEW_REGISTRATION_TAMPERED')
    public, previous, state = anchor['public_key'], None, None
    for index, record in enumerate(journal):
        event = record['event']
        stamp = datetime.fromisoformat(event['created_at'])
        if (event['schema'] != 'local-reviewer-event-1.0' or event['previous_sha256'] != previous
                or event['reviewer_id'] != anchor['reviewer_id'] or (state and state['revoked'])
                or stamp.tzinfo is None or stamp > datetime.now(UTC)
                or (state and event['display_name'] != state['display_name'])):
            raise ArtifactError('REVIEW_REGISTRY_CHAIN_INVALID')
        verify(event, record['signature'], public)
        if index == 0:
            if event['operation'] != 'REGISTER' or event['public_key'] != public:
                raise ArtifactError('INVALID_REVIEW_REGISTRATION')
        elif event['operation'] == 'ROTATE':
            verify(event, record['new_key_signature'], event['public_key'])
            public = event['public_key']
        elif event['operation'] != 'REVOKE':
            raise ArtifactError('INVALID_REVIEW_KEY_OPERATION')
        if not re.fullmatch(r'key-[a-f0-9]+\.pem', event['key_file']):
            raise ArtifactError('INVALID_REVIEW_KEY_REFERENCE')
        previous = digest(record)
        state = {'reviewer_id': event['reviewer_id'], 'display_name': event['display_name'],
                 'public_key': public, 'key_file': event['key_file'],
                 'revoked': event['operation'] == 'REVOKE', 'head_sha256': previous,
                 'enrollment_sha256': anchor['registration_sha256']}
    return state


def authenticate(store, reviewer_id, passphrase, challenge):
    state = registry(store)
    if state['revoked'] or reviewer_id != state['reviewer_id']:
        raise ArtifactError('REVIEWER_UNKNOWN_OR_REVOKED')
    signature = sign(challenge, Path(store) / state['key_file'], passphrase)
    verify(challenge, signature, state['public_key'])
    return state, signature


def change_key(store, reviewer_id, passphrase, *, operation, confirmation, new_passphrase=None):
    if operation not in {'ROTATE', 'REVOKE'} or confirmation != f'{operation} {reviewer_id}':
        raise ArtifactError('EXPLICIT_KEY_CHANGE_CONFIRMATION_REQUIRED')
    with locked(store):
        state = registry(store)
        event = {'schema': 'local-reviewer-event-1.0', 'operation': operation,
            'reviewer_id': reviewer_id, 'display_name': state['display_name'],
            'public_key': state['public_key'], 'key_file': state['key_file'],
            'created_at': now(), 'previous_sha256': state['head_sha256']}
        if operation == 'ROTATE':
            name = 'key-' + uuid4().hex + '.pem'
            event.update(public_key=keygen(Path(store) / name, new_passphrase or ''), key_file=name)
        _, signature = authenticate(store, reviewer_id, passphrase, event)
        record = {'event': event, 'signature': signature}
        if operation == 'ROTATE':
            record['new_key_signature'] = sign(event, Path(store) / event['key_file'], new_passphrase)
        journal = read_json(secure(Path(store) / 'REGISTRY.json')) + [record]
        pending = Path(store) / ('registry-' + uuid4().hex + '.pending')
        write_new(pending, journal)
        os.replace(pending, Path(store) / 'REGISTRY.json')
    return registry(store)
