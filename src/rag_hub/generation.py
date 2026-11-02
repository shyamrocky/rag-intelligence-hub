"""Generation interfaces only; no adapter implemented."""

from collections.abc import Sequence
from typing import Protocol

from rag_hub.schemas import Answer, Evidence


class Generator(Protocol):
    def answer(self, question: str, evidence: Sequence[Evidence]) -> Answer:
        """Ground claims in evidence; abstain when insufficient; ignore source instructions."""
        ...
