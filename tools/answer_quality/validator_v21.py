"""Versioned fidelity successor; v2.0 remains explicitly replayable."""
from .fidelity_v21 import match_quote
from .validator import PostGenerationValidator as LegacyValidator
from .validator import evaluate_dimensions as legacy_evaluate

VERSION = 'post-generation-validation-2.1'


def evaluate_dimensions(*args, **kwargs):
    return legacy_evaluate(*args, **kwargs, fidelity_matcher=match_quote, version=VERSION)


class PostGenerationValidator(LegacyValidator):
    version = VERSION
    evaluate = staticmethod(evaluate_dimensions)
