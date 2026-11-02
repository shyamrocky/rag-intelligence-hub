"""Bound, project-relative artifact access. Never a general-purpose file server."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

HEX = re.compile(r"[0-9a-f]{64}\Z")


class ArtifactError(ValueError):
    """Safe category only: do not propagate publisher text or absolute paths."""


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            result.update(block)
    return result.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode()).hexdigest()


def safe_path(root, name, *, prefix=None):
    if type(name) is not str or "\\" in name or any(ord(c) < 32 for c in name):
        raise ArtifactError("INVALID_ARTIFACT_REFERENCE")
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(p in {"..", ".", ""} for p in name.split("/")):
        raise ArtifactError("INVALID_ARTIFACT_REFERENCE")
    if any(p.startswith(".") or p.lower() in {"secrets.toml", "credentials"}
           for p in relative.parts):
        raise ArtifactError("RESTRICTED_ARTIFACT_REFERENCE")
    root = Path(root).resolve(strict=True)
    path = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ArtifactError("SYMLINK_ARTIFACT_REFERENCE")
    try:
        path = path.resolve(strict=True)
    except OSError:
        raise ArtifactError("ARTIFACT_UNAVAILABLE") from None
    if not path.is_file() or not path.is_relative_to(root):
        raise ArtifactError("ARTIFACT_OUTSIDE_PROJECT")
    if prefix and not path.is_relative_to(root / prefix):
        raise ArtifactError("ARTIFACT_OUTSIDE_SCOPE")
    return path


def read_json(path):
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=_unique)
    except (ValueError, OSError, UnicodeError):
        raise ArtifactError("INVALID_ARTIFACT_JSON") from None


def _unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.references = {}
        self.verified = {}

    def bind(self, name, expected):
        if type(expected) is not str or not HEX.fullmatch(expected):
            raise ArtifactError("INVALID_ARTIFACT_HASH")
        path = safe_path(self.root, name)
        if sha(path) != expected:
            # Explicitly reviewed implementation successors preserve historical
            # receipts. No source/config/request/authorization substitution exists.
            from tools.generation_artifact_lineage import (
                HISTORICAL_IMPLEMENTATION_VERSIONS,
                HISTORICAL_IMPLEMENTATIONS,
            )
            lineage = HISTORICAL_IMPLEMENTATION_VERSIONS.get(name, {}).get(expected)
            if lineage is None:
                lineage = HISTORICAL_IMPLEMENTATIONS.get(name)
            if (not lineage or not name.endswith('.py')
                    or lineage['historical_sha256'] != expected
                    or sha(path) != lineage['successor_sha256']):
                raise ArtifactError("ARTIFACT_HASH_MISMATCH")
            snapshot = safe_path(self.root, lineage['snapshot'],
                                 prefix='data/evals/implementation-history')
            if sha(snapshot) != expected:
                raise ArtifactError("HISTORICAL_IMPLEMENTATION_SNAPSHOT_CHANGED")
            self.verified[name] = expected
            self.references[self.ref_id(name)] = {
                "artifact": name, "sha256": expected,
                "status": "HISTORICAL_IMPLEMENTATION_SNAPSHOT_VERIFIED",
                "snapshot": lineage['snapshot'],
                "successor_sha256": lineage['successor_sha256']}
            return snapshot
        self.verified[name] = expected
        self.references[self.ref_id(name)] = {"artifact": name, "sha256": expected,
                                             "status": "HASH_VERIFIED"}
        return path

    def ref_id(self, name):
        return hashlib.sha256(name.encode()).hexdigest()[:24]

    def reference(self, name):
        if name not in self.verified:
            raise ArtifactError("UNBOUND_ARTIFACT")
        return self.ref_id(name)

    def json(self, name):
        if name not in self.verified:
            raise ArtifactError("UNBOUND_ARTIFACT")
        # Rehash on read, including after manifest verification; no stale cached authority.
        path = safe_path(self.root, name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.verified[name]:
            raise ArtifactError("ARTIFACT_HASH_MISMATCH")
        try:
            return json.loads(data, object_pairs_hook=_unique)
        except (ValueError, UnicodeError):
            raise ArtifactError("INVALID_ARTIFACT_JSON") from None

    def manifest(self, name, *, expected=None, schema=None):
        path = safe_path(self.root, name, prefix="data")
        fingerprint = sha(path)
        if expected and fingerprint != expected:
            raise ArtifactError("PINNED_MANIFEST_CHANGED")
        self.bind(name, fingerprint)
        value = self.json(name)
        if not isinstance(value, dict) or (schema and value.get("schema") != schema):
            raise ArtifactError("UNSUPPORTED_MANIFEST_SCHEMA")
        files = value.get("files")
        if not isinstance(files, dict) or not files:
            raise ArtifactError("UNSEALED_MANIFEST")
        parent = path.parent.relative_to(self.root).as_posix()
        for child, fingerprint in files.items():
            self.bind(f"{parent}/{child}", fingerprint)
        # External implementation bindings are verified, never displayed as source payloads.
        for key in ("implementation_files", "private_helpers", "diagnostic_helper"):
            bindings = value.get(key, {})
            if not isinstance(bindings, dict):
                raise ArtifactError("INVALID_EXTERNAL_BINDINGS")
            for external, fingerprint in bindings.items():
                self.bind(external, fingerprint)
        return value
