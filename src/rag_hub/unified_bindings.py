"""Fixed accepted selections and read-only integrity leases; no active registry."""

import json
from pathlib import Path

from rag_hub.unified_models import sha

FREEZE = "data/validation/corpus-qa/ingestion-freeze-v1/CORPUS_INGESTION_FREEZE.json"
FREEZE_SHA = "3c00d5df6f7cb15530c13c5161c24531df537eb9b1a585ef19bad8ceff8c86a5"
INDEX = "data/validation/html-markdown-qa-closure/v1/HTML_MARKDOWN_QA_CLOSURE_INDEX.json"
PDF_ISSUES = "data/validation/pdf/residual-recovery-v1/PDF_RESIDUAL_QA_ISSUES.json"
SELECTORS = {
    "html": "config/html-c10-admission-publication.json",
    "markdown": "config/markdown-admission-publication-v1-1.json",
    "pdf": "config/pdf-residual-admission-publication-v1.json",
}


class BoundFiles:
    """Hash at construction; detect filesystem changes cheaply on subsequent access.

    Every lease includes resolved path, inode, device, size, mtime and ctime.
    Changing a watched file permanently invalidates this loaded snapshot, even
    if later restored. Reloading runs the native validators again. No disk cache
    or caller-supplied digest can mint evidence authorization.
    """

    def __init__(self, root):
        self.root = Path(root).resolve()
        self._files = {}
        self._invalid = False
        self._json_cache = {}

    def path(self, name):
        p = self.root / name
        resolved = p.resolve(strict=True)
        if not resolved.is_relative_to(self.root):
            raise ValueError("unified_binding_outside_root")
        return p

    def signature(self, name):
        p = self.path(name)
        s = p.stat()
        return (str(p.resolve()), s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

    def bind(self, name, expected):
        name = str(name)
        before = self.signature(name)
        raw = self.path(name).read_bytes()
        if sha(raw) != expected or self.signature(name) != before:
            raise ValueError(f"unified_binding_changed:{name}")
        previous = self._files.get(name)
        if previous and previous != (expected, before):
            raise ValueError(f"unified_binding_conflict:{name}")
        self._files[name] = (expected, before)
        return raw

    def check(self):
        if self._invalid:
            raise ValueError("unified_snapshot_invalidated")
        try:
            for name, (_, signature) in self._files.items():
                if self.signature(name) != signature:
                    raise ValueError(f"unified_snapshot_binding_changed:{name}")
        except (OSError, ValueError):
            self._invalid = True
            raise ValueError("unified_snapshot_invalidated") from None

    def json(self, name, expected=None):
        if name not in self._files:
            raise ValueError(f"unbound_catalog_artifact:{name}")
        if expected is not None and expected != self._files[name][0]:
            raise ValueError(f"unified_binding_conflict:{name}")
        if name not in self._json_cache:
            self._json_cache[name] = json.loads(self.bind(name, self._files[name][0]))
        return self._json_cache[name]

    def fingerprints(self):
        return {k: v[0] for k, v in sorted(self._files.items())}


def accepted_bindings(root, selection_set=None):
    bound = BoundFiles(root)
    freeze = json.loads(bound.bind(FREEZE, FREEZE_SHA))
    verification = freeze["verification"]
    checks = json.loads(bound.bind(verification["path"], verification["sha256"]))
    # The freeze's inventory is an integrity aid only. Native loaders below
    # still validate each accepted publication against the sole QA authority.
    for path, digest in checks["checked_artifacts"].items():
        bound.bind(path, digest)
    # Canonical PDF manifests bind the original Section/structure payloads.
    manifest = bound.json("data/normalized/pdf/four-pdf-poc-v1/manifest.json")
    for path, digest in manifest["artifacts"].items():
        bound.bind(path, digest)
    selections = {}
    for fmt, key in [("html", "HTML"), ("markdown", "Markdown"), ("pdf", "PDF")]:
        ref = freeze["independent_format_releases"][key]["selector_binding"]
        if ref["path"] != SELECTORS[fmt]:
            raise ValueError("unified_nonaccepted_selector")
        selections[fmt] = json.loads(bound.bind(ref["path"], ref["sha256"]))
    if selection_set is not None and selection_set != selections:
        raise ValueError("unified_wrong_or_historical_selection")
    # Watch new loaded implementation too; do not modify accepted fingerprints.
    for name in ["unified_models", "unified_bindings", "unified_adapters", "unified_consumption"]:
        path = f"src/rag_hub/{name}.py"
        raw = bound.path(path).read_bytes()
        bound.bind(path, sha(raw))
    return bound, freeze, selections
