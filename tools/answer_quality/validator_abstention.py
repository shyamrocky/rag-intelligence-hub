"""Additive abstention diagnostics; existing v2.1 acceptance rules stay unchanged.

The response schema already rejects missing/empty reasons. This separately
versioned check names that defect without relabeling it as an invalid citation.
Meaningfulness, factual support and appropriate abstention remain review tasks.
"""
from .abstention import check_explanation
from .validator_v21 import PostGenerationValidator as HistoricalValidator
from .validator_v21 import evaluate_dimensions as historical_evaluate


def evaluate_dimensions(response, *args, **kwargs):
    value = historical_evaluate(response, *args, **kwargs)
    check = check_explanation(response)
    value['abstention_explanation'] = check
    if check['structural_status'] == 'FAIL':
        value['diagnoses'] += check['diagnoses']
    return value


class PostGenerationValidator(HistoricalValidator):
    evaluate = staticmethod(evaluate_dimensions)
