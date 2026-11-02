"""Ingestion contracts; concrete local adapters live in the format-specific modules."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from rag_hub.schemas import ParsedBlock, SourceManifest


class Acquirer(Protocol):
    def acquire(self, source: SourceManifest) -> Path:
        """Verify permitted local bytes and hash; remote policy is still open."""
        ...


class Parser(Protocol):
    def parse(self, source: SourceManifest) -> Sequence[ParsedBlock]:
        """Preserve ordered blocks, pages, headings, code and provider labels."""
        ...
