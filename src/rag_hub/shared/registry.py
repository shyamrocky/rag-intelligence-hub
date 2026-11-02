"""Trusted Python registrations, never source-directed discovery/imports."""

import importlib.metadata
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rag_hub.acquire import digest

REQUIRED = frozenset(("source_text", "source_locations", "source_order", "source_membership"))


@dataclass(frozen=True)
class Adapter:
    adapter_id: str
    source_format: str
    version: str
    parser_factory: Callable
    fidelity: Callable | None
    parents: Callable
    options: dict = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    assets: tuple[Path, ...] = ()

    def identity(self):
        functions = [self.parser_factory, self.parents]
        if self.fidelity:
            functions.append(self.fidelity)
        paths = {Path(inspect.getsourcefile(f)).resolve() for f in functions}
        paths.update(p.resolve() for p in self.assets)
        if not self.adapter_id or not self.version or not callable(self.parser_factory):
            raise ValueError("invalid_adapter_descriptor")
        options = json.loads(json.dumps(self.options, sort_keys=True, allow_nan=False))
        return {
            "adapter_id": self.adapter_id,
            "source_format": self.source_format,
            "version": self.version,
            "options": options,
            "code_and_assets": {str(p): digest(p.read_bytes()) for p in sorted(paths)},
            "callables": [f.__module__ + ":" + f.__qualname__ for f in functions],
            "dependencies": {p: importlib.metadata.version(p) for p in sorted(self.dependencies)},
            "required_fidelity_checks": sorted(REQUIRED),
        }


class Registry:
    """Validate the complete trusted registration set inside the parsing owner.

    Keeping construction inert permits malformed trusted configuration to be
    published as an auditable failed attempt rather than an uncaught startup error.
    """

    def __init__(self, entries=()):
        self.entries = tuple(entries)

    def register(self, entry):
        return Registry((*self.entries, entry))

    def resolve(self, source_format):
        for attr in ("adapter_id", "source_format"):
            values = [getattr(e, attr) for e in self.entries]
            if len(values) != len(set(values)):
                raise ValueError("duplicate_" + attr)
        matches = [e for e in self.entries if e.source_format == source_format]
        if len(matches) != 1:
            raise ValueError("unsupported_source_format: " + source_format)
        selected = matches[0]
        if not selected.fidelity or not callable(selected.parents):
            raise ValueError("missing_required_fidelity_or_structure_component")
        return selected
