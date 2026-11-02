"""Hand-calculated independent examples; no source truth or model mocks."""

import copy

import pytest

from tools.evaluation.metrics import evidence, retrieval, summarize, targets

PARENTS = {'a': 'u1', 'a2': 'u1-alt', 'b': 'u2', 'x': 'unjudged', 'y': 'u1'}


def label():
    return {'proposed_positive_chunk_ids': ['a', 'a2', 'b'], 'required_evidence_groups': [
        {'alternatives': [{'unit_id': 'u1', 'expected_relevant_chunk_ids': ['a']},
                          {'unit_id': 'u1-alt', 'expected_relevant_chunk_ids': ['a2']}]},
        {'alternatives': [{'unit_id': 'u2', 'expected_relevant_chunk_ids': ['b']}]}]}


def hits(*ids):
    return [{'chunk_id': cid, 'rank': i} for i, cid in enumerate(ids, 1)]


def package(include=('u1',), omit=('u2',), tokens=400):
    return {'budget': {'limit': 1000, 'exact_llm_evidence_tokens': tokens,
                       'reserved_block_tokens': tokens, 'truncation': False},
            'parents': [{'evidence': {'unit_id': uid}, 'token_count': tokens} for uid in include],
            'counts': {'candidates': 3, 'selected_parents': len(include),
                       'distinct_parents': len(include) + len(omit)},
            'diagnostics': {'omitted': [{'unit_id': uid, 'token_count': 1500,
                                        'reason': 'PARENT_EXCEEDS_TOTAL_BUDGET',
                                        'partial_parent_returned': False} for uid in omit],
                            'deduplicated': [{'unit_id': 'u1'}]},
            'status': 'VERIFIED_EVIDENCE' if include else 'INSUFFICIENT_EVIDENCE_FOR_BUDGET'}


def test_raw_recall_and_equivalence_denominators():
    m = retrieval(label(), hits('a'), PARENTS)
    assert m['at_k']['1']['raw_known_positive_recall'] == pytest.approx(1/3)
    assert m['at_k']['1']['equivalence_aware_chunk_recall'] == 0.5
    assert m['at_k']['1']['parent_group_coverage'] == 0.5
    assert m['positive_chunk_denominator'] == 3
    assert m['equivalence_collapsed_target_denominator'] == 2


def test_alternative_not_an_additional_required_answer():
    m = retrieval(label(), hits('a2', 'b'), PARENTS)
    assert m['at_k']['3']['all_required_groups_retrieved']
    assert m['at_k']['3']['equivalence_aware_chunk_recall'] == 1
    assert m['at_k']['3']['raw_known_positive_recall'] == pytest.approx(2/3)


def test_multiple_chunks_same_parent_not_another_requirement():
    l = {'proposed_positive_chunk_ids': ['a', 'y'], 'required_evidence_groups': [
         {'alternatives': [{'unit_id': 'u1', 'expected_relevant_chunk_ids': ['a', 'y']}]}]}
    m = retrieval(l, hits('a'), PARENTS)
    assert len(targets(l)) == 2
    assert m['at_k']['1']['raw_known_positive_recall'] == 0.5
    assert m['at_k']['1']['all_required_groups_retrieved']


def test_unjudged_slice_can_access_relevant_parent_without_becoming_positive():
    m = retrieval(label(), hits('y', 'b'), PARENTS)
    assert m['at_k']['3']['all_required_groups_retrieved']
    assert m['at_k']['1']['direct_positive_group_hits'] == 0
    assert m['first_relevant_rank'] == 2


def test_MRR_one_based_rank_and_cutoff_prefixes():
    m = retrieval(label(), hits('x', 'a', 'b'), PARENTS)
    assert m['reciprocal_rank_at_10'] == 0.5
    assert m['at_k']['1']['equivalence_aware_chunk_recall'] == 0
    assert m['at_k']['3']['equivalence_aware_chunk_recall'] == 1


def test_zero_hits_is_not_nan():
    m = retrieval(label(), [], PARENTS)
    assert m['reciprocal_rank_at_10'] == 0
    assert m['first_relevant_rank'] is None
    assert m['at_k']['10']['raw_known_positive_recall'] == 0


def test_unsupported_not_given_zero_recall_in_answerable_denominator():
    m = retrieval({'required_evidence_groups': [], 'proposed_positive_chunk_ids': []},
                  hits('x'), PARENTS)
    assert m['reciprocal_rank_at_10'] is None
    assert m['at_k']['10']['raw_known_positive_recall'] is None
    assert not m['answerable'] and m['candidate_count'] == 1


@pytest.mark.parametrize('ids', [('a', 'a'), ('forged',)])
def test_duplicate_or_unknown_candidates_reject(ids):
    with pytest.raises(ValueError):
        retrieval(label(), hits(*ids), PARENTS)


def test_wrong_rank_reject():
    with pytest.raises(ValueError):
        retrieval(label(), [{'chunk_id': 'a', 'rank': 2}], PARENTS)


def test_retrieval_miss_not_classified_budget_failure():
    m = retrieval(label(), hits('a'), PARENTS)
    e = evidence(label(), m, package(include=('u1',), omit=()))
    assert e['outcome'] == 'RETRIEVAL_INCOMPLETE_BEFORE_BUDGET'
    assert e['budget_lost_group_numbers'] == []
    assert e['relevant_parents_reconstructed'] == 1


def test_retrieved_but_budget_omitted_is_distinct():
    m = retrieval(label(), hits('a', 'b'), PARENTS)
    e = evidence(label(), m, package())
    assert e['outcome'] == 'REQUIRED_EVIDENCE_OMITTED_BY_BUDGET'
    assert e['budget_lost_group_numbers'] == [2]
    assert e['relevant_parents_reconstructed'] == 2
    assert e['relevant_parents_included'] == ['u1']
    assert e['remaining_budget'] == 600 and e['utilization'] == 0.4
    assert e['reconstructed_block_tokens_sum'] == 1900


def test_partial_budget_loss_can_coexist_with_retrieval_miss():
    m = retrieval(label(), hits('a'), PARENTS)
    e = evidence(label(), m, package(include=(), omit=('u1',), tokens=0))
    assert e['outcome'] == 'RETRIEVAL_INCOMPLETE_BEFORE_BUDGET'
    assert e['budget_lost_group_numbers'] == [1]
    assert e['relevant_groups_per_1000_tokens'] is None


def test_all_required_included():
    m = retrieval(label(), hits('a2', 'b'), PARENTS)
    p = package(include=('u1-alt', 'u2'), omit=(), tokens=300)
    e = evidence(label(), m, p)
    assert e['outcome'] == 'ALL_REQUIRED_GROUPS_INCLUDED'
    assert e['groups_included'] == 2
    assert e['deduplicated_candidate_count'] == 1


@pytest.mark.parametrize('mutation', ['truncate', 'overflow', 'duplicated_parent', 'count'])
def test_invalid_budget_accounting_reject(mutation):
    p = package()
    if mutation == 'truncate':
        p['budget']['truncation'] = True
    elif mutation == 'overflow':
        p['budget']['exact_llm_evidence_tokens'] = 1001
    elif mutation == 'duplicated_parent':
        p['diagnostics']['omitted'][0]['unit_id'] = 'u1'
    else:
        p['counts']['distinct_parents'] = 8
    with pytest.raises(ValueError):
        evidence(label(), retrieval(label(), hits('a', 'b'), PARENTS), p)


def test_summary_excludes_unsupported_and_has_independent_micro_denominators():
    answer = retrieval(label(), hits('a', 'b'), PARENTS)
    unknown_label = {'required_evidence_groups': [], 'proposed_positive_chunk_ids': []}
    unsupported = retrieval(unknown_label, hits('x'), PARENTS)
    p = package(include=('u1', 'u2'), omit=(), tokens=300)
    cases = [{'mode': 'bm25', 'retrieval': answer,
              'budgets': {'1000': evidence(label(), answer, p)}},
             {'mode': 'bm25', 'retrieval': unsupported,
              'budgets': {'1000': evidence(unknown_label, unsupported, package())}}]
    s = summarize(copy.deepcopy(cases), ['bm25'], [1000])['bm25']
    assert s['answerable_denominator'] == 1 and s['unsupported_denominator'] == 1
    assert s['MRR_at_10'] == 1
    assert s['retrieval']['10']['equivalence_aware_Recall_macro'] == 1
    assert s['retrieval']['10']['raw_known_positive_Recall_micro'] == pytest.approx(2/3)
    assert s['budgets']['1000']['complete_question_count'] == 1
