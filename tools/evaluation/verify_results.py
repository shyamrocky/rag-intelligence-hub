"""Independent arithmetic/accounting checks using live authorized catalog metadata."""

import argparse
import json
import math
from pathlib import Path

from tools.evaluation.contract import benchmark
from tools.evidence.service import EvidenceService
from tools.indexing.m5_index import encoded, sha


def check_cases(value, labels, parent_index):
    expected = {(qid, mode) for qid in labels for mode in ('bm25', 'vector', 'hybrid')}
    pairs = [(c['question_id'], c['mode']) for c in value['cases']]
    if len(pairs) != len(set(pairs)) or set(pairs) != expected:
        raise ValueError('m9_missing_duplicate_or_wrong_case')
    checked = 0
    for case in value['cases']:
        label = labels[case['question_id']]
        hits = case['candidate_result']['candidates']
        ids = [h['chunk_id'] for h in hits]
        if len(ids) != len(set(ids)) or any(c not in parent_index for c in ids):
            raise ValueError('m9_unapproved_candidate')
        positives = set(label['proposed_positive_chunk_ids'])
        alternatives = [{a['unit_id'] for a in group['alternatives']}
                        for group in label['required_evidence_groups']]
        ranks = {cid: i for i, cid in enumerate(ids, 1) if cid in positives}
        if case['retrieval']['relevant_chunk_ranks'] != ranks:
            raise ValueError('m9_known_positive_ranks_incorrect')
        first = min(ranks.values(), default=None)
        if case['retrieval']['first_relevant_rank'] != first:
            raise ValueError('m9_first_rank_incorrect')
        rr = (1 / first if first else 0) if positives else None
        if case['retrieval']['reciprocal_rank_at_10'] != rr:
            raise ValueError('m9_reciprocal_rank_incorrect')
        for k in (1, 3, 5, 10):
            row = case['retrieval']['at_k'][str(k)]
            groups_found = sum(bool(g & {parent_index[c] for c in ids[:k]}) for g in alternatives)
            if row['parent_groups_retrieved'] != groups_found:
                raise ValueError('m9_parent_groups_incorrect')
            if positives:
                expected_recall = len(positives & set(ids[:k])) / len(positives)
                if not math.isclose(row['raw_known_positive_recall'], expected_recall, abs_tol=1e-15):
                    raise ValueError('m9_raw_recall_incorrect')
            elif row['raw_known_positive_recall'] is not None:
                raise ValueError('m9_unsupported_contaminates_recall')
        unique = {parent_index[c] for c in ids}
        for budget in (4000, 8000, 16000, 32000):
            b = case['budgets'][str(budget)]
            inc = set(b['included_parent_ids'])
            omit = {o['unit_id'] for o in b['omitted_parents']}
            if inc & omit or inc | omit != unique or set(b['reconstructed_parent_ids']) != unique:
                raise ValueError('m9_reconstruction_membership_incorrect')
            flags = [bool(a & inc) for a in alternatives]
            if b['group_included_flags'] != flags:
                raise ValueError('m9_inclusion_groups_incorrect')
            if (not 0 <= b['included_tokens'] <= budget
                    or b['remaining_budget'] != budget - b['included_tokens']
                    or b['deduplicated_candidate_count'] != len(ids) - len(unique)
                    or sum(x['token_count'] for x in b['obligations']) != b['reserved_included_block_tokens']
                    or {o['unit_id'] for o in b['obligations']} != inc):
                raise ValueError('m9_budget_or_dedup_accounting_incorrect')
            if not b['live_native_parent_binding_validation']:
                raise ValueError('m9_missing_live_source_validation')
            if case['question_id'] in {'M9-Q01', 'M9-Q21'} and not b[
                    'live_revalidation_and_deterministic_package_replay']:
                raise ValueError('m9_missing_representative_package_replay')
            checked += 1
    if 'summary' in value:
        for mode in ('bm25', 'vector', 'hybrid'):
            answerable = [c for c in value['cases'] if c['mode'] == mode and
                          labels[c['question_id']]['proposed_positive_chunk_ids']]
            expected = math.fsum(c['retrieval']['reciprocal_rank_at_10'] for c in answerable) / len(answerable)
            if not math.isclose(value['summary'][mode]['MRR_at_10'], expected, rel_tol=0, abs_tol=1e-15):
                raise ValueError('m9_aggregate_MRR_incorrect')
    return checked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='data/evals/m9/runs/m9-v3')
    args = parser.parse_args()
    root = Path.cwd()
    path = root / args.run
    value = json.loads((path / 'RESULTS.json').read_bytes())
    _, _, labels = benchmark(root)
    gateway = EvidenceService(root, selector='config/evidence-reconstruction-m8-v1.json',
        selector_sha256='e0ac189c8b5ffd331f28ae87f81d56c22868e12c45d7b73e6a5e7f1a65c6bef2')
    index = {c['chunk_id']: c['unit_id'] for c in gateway.catalog.list_chunks(limit=1000)['items']}
    checked = check_cases(value, labels, index)
    from tools.evaluation.oversized import collect

    oversized = collect(gateway, value, labels)
    (path / 'OVERSIZED_COST_ANALYSIS.json').write_bytes(encoded(oversized))
    gateway.check()
    out = {'status': 'PASS_INDEPENDENT_METRIC_ACCOUNTING', 'cases': len(value['cases']),
           'budget_observations': checked, 'live_authorized_chunk_inventory': len(index),
           'results_sha256': sha((path / 'RESULTS.json').read_bytes()),
           'note': 'Independent set/count/denominator checks. Not an independent human relevance review.'}
    (path / 'INDEPENDENT_METRIC_VERIFICATION.json').write_bytes(encoded(out))
    (path / 'CHUNK_PARENT_INSPECTION_INDEX.json').write_bytes(encoded({
        'authority': 'INSPECTION_ONLY_NOT_EVIDENCE', 'selected_M3': 'config/retrieval-chunks-m3-durable-v1.json',
        'mapping': index}))
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
