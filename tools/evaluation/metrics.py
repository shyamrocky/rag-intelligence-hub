"""Transparent qrels, source-equivalence and atomic evidence metrics; no ranking changes."""

from statistics import mean

CUTOFFS = (1, 3, 5, 10)


def groups(label):
    return [{a['unit_id'] for a in group['alternatives']}
            for group in label['required_evidence_groups']]


def covered(label, parent_ids):
    return [bool(g & set(parent_ids)) for g in groups(label)]


def targets(label):
    """Collapse only explicitly approved single-chunk source-equivalent alternatives."""
    positives = set(label['proposed_positive_chunk_ids'])
    result, collapsed = [], set()
    for group in label['required_evidence_groups']:
        alternatives = group['alternatives']
        if len(alternatives) > 1 and all(len(a['expected_relevant_chunk_ids']) == 1
                                         for a in alternatives):
            ids = {a['expected_relevant_chunk_ids'][0] for a in alternatives}
            result.append(ids)
            collapsed |= ids
    return result + [{cid} for cid in sorted(positives - collapsed)]


def retrieval(label, candidates, parents):
    ids = [x['chunk_id'] for x in candidates]
    if len(ids) != len(set(ids)) or any(cid not in parents for cid in ids):
        raise ValueError('m9_duplicate_or_unknown_candidate')
    if [x['rank'] for x in candidates] != list(range(1, len(ids) + 1)):
        raise ValueError('m9_invalid_candidate_ranks')
    positives = set(label['proposed_positive_chunk_ids'])
    answerable = bool(label['required_evidence_groups'])
    relevant_ranks = {cid: ids.index(cid) + 1 for cid in sorted(positives & set(ids))}
    expected_parents = set().union(*groups(label)) if answerable else set()
    found_parents = {parents[cid] for cid in ids} & expected_parents
    out = {'answerable': answerable, 'candidate_count': len(ids),
           'positive_chunk_denominator': len(positives),
           'equivalence_collapsed_target_denominator': len(targets(label)),
           'required_group_denominator': len(groups(label)),
           'first_relevant_rank': min(relevant_ranks.values(), default=None),
           'relevant_chunk_ranks': relevant_ranks,
           'relevant_retrieved_parent_ids': sorted(found_parents), 'at_k': {}}
    out['reciprocal_rank_at_10'] = (1 / out['first_relevant_rank']
                                    if out['first_relevant_rank'] else 0) if answerable else None
    for k in CUTOFFS:
        selected = set(ids[:k])
        pg = covered(label, {parents[cid] for cid in ids[:k]})
        direct = [any(selected & set(a['expected_relevant_chunk_ids'])
                      for a in g['alternatives']) for g in label['required_evidence_groups']]
        out['at_k'][str(k)] = {
            'raw_positive_hits': len(positives & selected),
            'raw_known_positive_recall': len(positives & selected) / len(positives)
                if answerable else None,
            'equivalent_target_hits': sum(bool(t & selected) for t in targets(label)),
            'equivalence_aware_chunk_recall': sum(bool(t & selected) for t in targets(label))
                / len(targets(label)) if answerable else None,
            'parent_groups_retrieved': sum(pg),
            'parent_group_coverage': sum(pg) / len(pg) if answerable else None,
            'all_required_groups_retrieved': all(pg) if answerable else None,
            'direct_positive_group_hits': sum(direct),
            'flat_alternative_parents_found': len({parents[c] for c in ids[:k]} & expected_parents),
            'flat_alternative_parent_denominator': len(expected_parents)}
    return out


def evidence(label, retrieved, package):
    limit = package['budget']['limit']
    included = [p['evidence']['unit_id'] for p in package['parents']]
    omitted = package['diagnostics']['omitted']
    omitted_ids = [p['unit_id'] for p in omitted]
    counts = package['counts']
    if (len(set(included + omitted_ids)) != len(included) + len(omitted_ids)
            or counts['selected_parents'] != len(included)
            or counts['distinct_parents'] != len(included) + len(omitted_ids)
            or not 0 <= package['budget']['exact_llm_evidence_tokens'] <= limit
            or package['budget']['truncation'] is not False
            or any(p['partial_parent_returned'] is not False for p in omitted)):
        raise ValueError('m9_invalid_atomic_budget_accounting')
    pg = covered(label, included)
    rg = covered(label, retrieved['relevant_retrieved_parent_ids'])
    answerable = retrieved['answerable']
    if not answerable:
        outcome = 'UNSUPPORTED_CONTROL_NOT_ANSWER_EVIDENCE'
    elif not all(rg):
        outcome = 'RETRIEVAL_INCOMPLETE_BEFORE_BUDGET'
    elif not all(pg):
        outcome = 'REQUIRED_EVIDENCE_OMITTED_BY_BUDGET'
    else:
        outcome = 'ALL_REQUIRED_GROUPS_INCLUDED'
    budget_lost = [i + 1 for i, (r, p) in enumerate(zip(rg, pg, strict=True)) if r and not p]
    return {'status': package['status'], 'outcome': outcome,
            'included_parent_ids': included, 'omitted_parents': omitted,
            'reconstructed_parent_ids': sorted(included + omitted_ids),
            'relevant_parents_reconstructed': len(retrieved['relevant_retrieved_parent_ids']),
            'relevant_parents_included': sorted(set(included) &
                                             set(retrieved['relevant_retrieved_parent_ids'])),
            'group_included_flags': pg, 'groups_included': sum(pg),
            'required_group_denominator': len(pg),
            'all_required_groups_included': all(pg) if answerable else None,
            'budget_lost_group_numbers': budget_lost,
            'candidate_count': counts['candidates'], 'distinct_parents': counts['distinct_parents'],
            'deduplicated_candidate_count': len(package['diagnostics']['deduplicated']),
            'included_tokens': package['budget']['exact_llm_evidence_tokens'],
            'reserved_included_block_tokens': package['budget']['reserved_block_tokens'],
            'omitted_block_tokens_sum': sum(p['token_count'] for p in omitted),
            'reconstructed_block_tokens_sum': sum(p['token_count'] for p in package['parents'])
                + sum(p['token_count'] for p in omitted),
            'remaining_budget': limit - package['budget']['exact_llm_evidence_tokens'],
            'utilization': package['budget']['exact_llm_evidence_tokens'] / limit,
            'relevant_groups_per_1000_tokens': 1000 * sum(pg)
                / package['budget']['exact_llm_evidence_tokens']
                if answerable and package['budget']['exact_llm_evidence_tokens'] else None}


def summarize(cases, modes, budgets):
    result = {}
    for mode in modes:
        all_rows = [c for c in cases if c['mode'] == mode]
        rows = [c for c in all_rows if c['retrieval']['answerable']]
        denominator = sum(c['retrieval']['required_group_denominator'] for c in rows)
        data = {'answerable_denominator': len(rows),
                'unsupported_denominator': len(all_rows) - len(rows),
                'required_group_denominator': denominator,
                'MRR_at_10': mean(c['retrieval']['reciprocal_rank_at_10'] for c in rows),
                'retrieval': {}, 'budgets': {}}
        for k in CUTOFFS:
            rr = [c['retrieval']['at_k'][str(k)] for c in rows]
            data['retrieval'][str(k)] = {
                'equivalence_aware_Recall_macro': mean(r['equivalence_aware_chunk_recall'] for r in rr),
                'raw_known_positive_Recall_macro': mean(r['raw_known_positive_recall'] for r in rr),
                'raw_known_positive_Recall_micro': sum(r['raw_positive_hits'] for r in rr)
                    / sum(c['retrieval']['positive_chunk_denominator'] for c in rows),
                'parent_group_coverage_macro': mean(r['parent_group_coverage'] for r in rr),
                'parent_group_coverage_micro': sum(r['parent_groups_retrieved'] for r in rr) / denominator,
                'all_required_complete_count': sum(r['all_required_groups_retrieved'] for r in rr),
                'multi_group_complete_count': sum(c['retrieval']['at_k'][str(k)][
                    'all_required_groups_retrieved'] for c in rows
                    if c['retrieval']['required_group_denominator'] > 1)}
        for budget in budgets:
            bb = [c['budgets'][str(budget)] for c in rows]
            data['budgets'][str(budget)] = {
                'complete_question_count': sum(b['all_required_groups_included'] for b in bb),
                'included_groups': sum(b['groups_included'] for b in bb),
                'group_inclusion_micro': sum(b['groups_included'] for b in bb) / denominator,
                'mean_included_tokens': mean(b['included_tokens'] for b in bb),
                'mean_utilization': mean(b['utilization'] for b in bb),
                'omitted_parent_count': sum(len(b['omitted_parents']) for b in bb),
                'budget_lost_group_count': sum(len(b['budget_lost_group_numbers']) for b in bb),
                'insufficient_evidence_count': sum(b['status'] == 'INSUFFICIENT_EVIDENCE_FOR_BUDGET'
                                                   for b in bb),
                'all_retrieved_but_budget_incomplete_count': sum(b['outcome'] ==
                    'REQUIRED_EVIDENCE_OMITTED_BY_BUDGET' for b in bb)}
        result[mode] = data
    return result
