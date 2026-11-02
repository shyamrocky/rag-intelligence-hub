"""Chunking interfaces only; no adapter implemented."""

from collections.abc import Sequence
from typing import Protocol

from rag_hub.config import Settings
from rag_hub.schemas import Chunk, Section


class Chunker(Protocol):
    def chunk(self, sections: Sequence[Section], settings: Settings) -> Sequence[Chunk]:
        """Require approved input; retain deterministic IDs and multi-section lineage."""
        ...
