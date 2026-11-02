"""Normalization contracts; concrete local adapters live in the format-specific modules."""

from collections.abc import Sequence
from typing import Protocol

from rag_hub.schemas import ParsedBlock, Section


class Normalizer(Protocol):
    def normalize(self, blocks: Sequence[ParsedBlock]) -> Sequence[Section]: ...


class QualityGate(Protocol):
    def review(self, sections: Sequence[Section]) -> Sequence[Section]:
        """Approve only verified spans; keep ambiguous tables/math on HOLD."""
        ...
