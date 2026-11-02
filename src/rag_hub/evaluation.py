"""Evaluation interfaces only; no adapter implemented."""

from collections.abc import Sequence
from typing import Protocol

from rag_hub.schemas import EvaluationCase, EvaluationReport


class Evaluator(Protocol):
    def evaluate(self, cases: Sequence[EvaluationCase]) -> EvaluationReport:
        """Use reviewed passage labels; never report document hits as passage recall."""
        ...
