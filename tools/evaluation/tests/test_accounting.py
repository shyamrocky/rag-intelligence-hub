"""Mutation controls for independent end-to-end measurement accounting."""

import copy

import pytest

from tools.evaluation.metrics import evidence, retrieval, summarize
from tools.evaluation.verify_results import check_cases


def fixture():
    l = {'proposed_positive_chunk_ids': ['a'], 'required_evidence_groups': [
        {'alternatives': [{'unit_id': 'u', 'expected_relevant_chunk_ids': ['a']}]}]}
    candidates = [{'chunk_id': 'a', 'rank': 1}]
    r = retrieval(l, candidates, {'a': 'u'})
    cases = []
    for mode in ('bm25', 'vector', 'hybrid'):
        budgets = {}
        for limit in (4000, 8000, 16000, 32000):
            p = {'budget': {'limit': limit, 'exact_llm_evidence_tokens': 100,
                           'reserved_block_tokens': 100, 'truncation': False},
                 'parents': [{'evidence': {'unit_id': 'u'}, 'token_count': 100}],
                 'counts': {'candidates': 1, 'selected_parents': 1, 'distinct_parents': 1},
                 'status': 'VERIFIED_EVIDENCE', 'diagnostics': {'omitted': [], 'deduplicated': []}}
            b = evidence(l, r, p)
            b['obligations'] = [{'unit_id': 'u', 'token_count': 100}]
            b['live_revalidation_and_deterministic_package_replay'] = True
            b['live_native_parent_binding_validation'] = True
            budgets[str(limit)] = b
        cases.append({'question_id': 'q', 'mode': mode, 'candidate_result': {'candidates': candidates},
                      'retrieval': r, 'budgets': budgets})
    value = {'cases': cases, 'summary': summarize(cases, ['bm25','vector','hybrid'],
                                                 [4000,8000,16000,32000])}
    return value, {'q': l}, {'a': 'u'}


def test_independent_complete_accounting():
    value, labels, index = fixture()
    assert check_cases(value, labels, index) == 12


@pytest.mark.parametrize('change', ['duplicate', 'missing', 'forged_chunk', 'rank',
                                   'groups', 'membership', 'tokens', 'dedup', 'source_proof', 'MRR', 'aggregate_MRR'])
def test_corrupted_measurement_fails_instead_of_becoming_a_miss(change):
    value, labels, index = fixture()
    value = copy.deepcopy(value)
    c = value['cases'][0]
    b = c['budgets']['4000']
    if change == 'duplicate':
        value['cases'].append(c)
    elif change == 'missing':
        value['cases'].pop()
    elif change == 'forged_chunk':
        c['candidate_result']['candidates'][0]['chunk_id'] = 'forged'
    elif change == 'rank':
        c['retrieval']['first_relevant_rank'] = 9
    elif change == 'MRR':
        c['retrieval']['reciprocal_rank_at_10'] = 0.5
    elif change == 'aggregate_MRR':
        value['summary']['bm25']['MRR_at_10'] = 0.5
    elif change == 'groups':
        c['retrieval']['at_k']['1']['parent_groups_retrieved'] = 0
    elif change == 'membership':
        b['reconstructed_parent_ids'] = ['other']
    elif change == 'tokens':
        b['remaining_budget'] = 0
    elif change == 'dedup':
        b['deduplicated_candidate_count'] = 1
    else:
        b['live_native_parent_binding_validation'] = False
        b['live_revalidation_and_deterministic_package_replay'] = False
    with pytest.raises((ValueError, KeyError)):
        check_cases(value, labels, index)
