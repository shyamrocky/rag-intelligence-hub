"""Retrieval interfaces only; no adapter implemented."""

from collections.abc import Sequence
from typing import Protocol

from rag_hub.schemas import Evidence


class Retriever(Protocol):
    def retrieve(self, question: str, *, snapshot_id: str, k: int = 5) -> Sequence[Evidence]:
        """Return ranked approved evidence from exactly one index snapshot."""
        ...
