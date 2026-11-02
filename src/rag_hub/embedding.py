"""Embedding interfaces only; no adapter implemented."""

from collections.abc import Sequence
from typing import Protocol

from rag_hub.schemas import Chunk


class Embedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...
    def embed_query(self, text: str) -> Sequence[float]: ...


class IndexWriter(Protocol):
    def write(self, chunks: Sequence[Chunk], embedder: Embedder) -> str:
        """Reject HOLD; persist model revision, dimension and snapshot metadata."""
        ...
