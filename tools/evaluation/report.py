"""Build source-free metric reports from completed private measurements. No inference."""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from tools.evaluation.contract import benchmark
from tools.indexing.m5_index import encoded, sha


def analysis(value, labels, parent_index):
    failures, q21, categories = [], [], []
    q21_uid = labels['M9-Q21']['required_evidence_groups'][0]['alternatives'][0]['unit_id']
    for case in value['cases']:
        qid, mode, r = case['question_id'], case['mode'], case['retrieval']
        if not r['answerable']:
            failures.append({'question_id': qid, 'mode': mode, 'budget': 'all',
                'category': 'UNSUPPORTED_QUESTION', 'reason': 'Owner-approved unsupported request; '
                'candidates and reconstructed packages do not provide an authorized answer.'})
        else:
            if r['first_relevant_rank'] is None:
                failures.append({'question_id': qid, 'mode': mode, 'budget': 'before budgeting',
                    'category': 'MISSING_KNOWN_POSITIVE_CHUNK_TOP10',
                    'reason': ('BM25 ranking/vocabulary miss' if mode == 'bm25' else
                               'Known-positive semantic slice miss' if mode == 'vector' else
                               'Hybrid top-10 miss') + '; exact cause or candidate-depth limit not '
                               'established by this bounded run. Parent/group access may still succeed through another child; unjudged alternatives remain possible.'})
            if not r['at_k']['10']['all_required_groups_retrieved']:
                failures.append({'question_id': qid, 'mode': mode, 'budget': 'before budgeting',
                    'category': 'INCOMPLETE_REQUIRED_GROUP_RETRIEVAL',
                    'reason': f"{r['at_k']['10']['parent_groups_retrieved']}/{r['required_group_denominator']} "
                              'required source groups found; this is not classified as a budget failure.'})
        for budget, b in case['budgets'].items():
            if b['budget_lost_group_numbers']:
                failures.append({'question_id': qid, 'mode': mode, 'budget': int(budget),
                    'category': 'RELEVANT_PARENT_OMITTED_BY_BUDGET',
                    'reason': 'Retrieved group(s) ' + str(b['budget_lost_group_numbers']) +
                              ' lost when complete parents did not fit; warnings/parents not truncated.'})
        if qid == 'M9-Q21':
            q21.append({'mode': mode, 'known_positive_rank': r['first_relevant_rank'],
                'bibliography_parent_retrieved': q21_uid in r['relevant_retrieved_parent_ids'],
                'first_parent_candidate_rank': min((h['rank'] for h in case['candidate_result']['candidates']
                    if parent_index[h['chunk_id']] == q21_uid), default=None),
                'parent_candidate_count': sum(parent_index[h['chunk_id']] == q21_uid
                    for h in case['candidate_result']['candidates']),
                'reconstructed': q21_uid in case['budgets']['32000']['reconstructed_parent_ids'],
                'actual_parent_block_tokens': next((p['token_count'] for p in
                    case['budgets']['32000']['omitted_parents'] if p['unit_id'] == q21_uid), None),
                **{f'included_{budget}': q21_uid in b['included_parent_ids']
                   for budget, b in case['budgets'].items()}})
    for cat in sorted({c['category'] for c in value['cases'] if c['retrieval']['answerable']}):
        for mode in ('bm25', 'vector', 'hybrid'):
            rows = [c for c in value['cases'] if c['category'] == cat and c['mode'] == mode]
            categories.append({'category': cat, 'mode': mode, 'answerable_questions': len(rows),
                'MRR_at_10': mean(c['retrieval']['reciprocal_rank_at_10'] for c in rows),
                'equivalence_aware_Recall_at_10': mean(c['retrieval']['at_k']['10'][
                    'equivalence_aware_chunk_recall'] for c in rows),
                'complete_required_groups_count': sum(c['retrieval']['at_k']['10'][
                    'all_required_groups_retrieved'] for c in rows)})
    comparison_cases = []
    by = {(c['question_id'], c['mode']): c for c in value['cases']}
    for qid in labels:
        if not labels[qid]['required_evidence_groups']:
            continue
        b, v, h = [by[qid, m]['retrieval'] for m in ('bm25', 'vector', 'hybrid')]
        if (b['first_relevant_rank'] is None) != (v['first_relevant_rank'] is None):
            comparison_cases.append({'question_id': qid, 'observation': 'BM25/vector known-positive hit disagreement',
                'bm25_rank': b['first_relevant_rank'], 'vector_rank': v['first_relevant_rank'],
                'hybrid_rank': h['first_relevant_rank']})
        if h['first_relevant_rank'] is None and (b['first_relevant_rank'] or v['first_relevant_rank']):
            comparison_cases.append({'question_id': qid, 'observation': 'Known positive present in single-mode top10 '
                                    'but absent from hybrid final top10; observed fusion ranking tradeoff, not an algorithm defect.'})
    counts = Counter(f['category'] for f in failures)
    unsupported = [{'question_id': c['question_id'], 'mode': c['mode'],
                    'candidates': c['retrieval']['candidate_count'],
                    'packages': {b: x['status'] for b, x in c['budgets'].items()}}
                   for c in value['cases'] if not c['retrieval']['answerable']]
    direct = []
    for c in value['cases']:
        label = labels[c['question_id']]
        relevant = set(label['proposed_positive_chunk_ids']) & {
            h['chunk_id'] for h in c['candidate_result']['candidates']}
        reconstructed = set(c['budgets']['32000']['reconstructed_parent_ids'])
        direct.append({'question_id': c['question_id'], 'mode': c['mode'],
                       'direct_positive_chunks_found': len(relevant),
                       'direct_positive_chunks_parent_reconstructed': sum(parent_index[x] in reconstructed
                                                                         for x in relevant)})
    efficiency = []
    for mode in ('bm25', 'vector', 'hybrid'):
        mode_cases = [c for c in value['cases'] if c['mode'] == mode and c['retrieval']['answerable']]
        for budget in (4000, 8000, 16000, 32000):
            selected = [c['budgets'][str(budget)] for c in mode_cases]
            tokens = sum(b['included_tokens'] for b in selected)
            included_groups = sum(b['groups_included'] for b in selected)
            efficiency.append({'mode': mode, 'budget': budget,
                'answerable_questions': len(mode_cases), 'included_tokens_sum': tokens,
                'included_required_groups': included_groups,
                'required_groups_per_1000_included_tokens': 1000 * included_groups / tokens if tokens else None,
                'zero_token_package_count': sum(b['included_tokens'] == 0 for b in selected),
                'duplicate_parent_blocks_avoided': sum(b['deduplicated_candidate_count'] for b in selected),
                'multi_group_complete_questions': sum(c['budgets'][str(budget)]['all_required_groups_included']
                    for c in mode_cases if c['retrieval']['required_group_denominator'] > 1),
                'reference_only_all_groups_fit_estimate_count': sum(value['expected_parent_fit_diagnostics'][
                    c['question_id']]['all_groups_fit_estimate'][str(budget)] for c in mode_cases),
                'diagnostic_not_actual_retrieval': 'reference-only fit estimate column only',
                'evidence_fit_but_required_incomplete': sum(bool(b['included_parent_ids']) and not
                    b['all_required_groups_included'] for b in selected)})
    return {'authority': 'MEASURED_ANALYSIS_NOT_EVIDENCE_AUTHORIZATION', 'failures': failures,
            'failure_categories': dict(counts), 'q21_comparison': q21,
            'efficiency_by_mode_budget': efficiency,
            'category_comparison': categories, 'observed_mode_tradeoffs': comparison_cases,
            'unsupported_controls': unsupported, 'retrieved_reconstructed_direct_positives': direct,
            'diagnostic_expected_parent_fit': value['expected_parent_fit_diagnostics'],
            'compact_evidence_implemented': False, 'chunk_size_experiment': 'PENDING_SEPARATE_AUTHORIZATION',
            'sampling': 'Small exposed source-authored set; bounded known-positive labels; no statistical generalization.'}


def table(headers, rows):
    return '| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join('---' for _ in headers) + ' |\n' + ''.join(
        '| ' + ' | '.join(str(x) for x in row) + ' |\n' for row in rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='data/evals/m9/runs/m9-v3')
    args = parser.parse_args()
    root = Path.cwd()
    out = root / args.run
    value = json.loads((out / 'RESULTS.json').read_bytes())
    _, questions, labels = benchmark(root)
    parent_index = json.loads((out / 'CHUNK_PARENT_INSPECTION_INDEX.json').read_bytes())['mapping']
    a = analysis(value, labels, parent_index)
    a['oversized_current_cost_analysis'] = json.loads((out / 'OVERSIZED_COST_ANALYSIS.json').read_bytes())
    a['oversized_attachment_structure'] = json.loads((out / 'OVERSIZED_STRUCTURE_INSPECTION.json').read_bytes())
    (out / 'ANALYSIS.json').write_bytes(encoded(a))
    print('ANALYSIS_READY', sha((out / 'ANALYSIS.json').read_bytes()))
    w = root / 'workspace/rag-implementation/v1/m9-evaluation-v1'
    s = value['summary']
    report = '# M9 measured retrieval and evidence results\n\n'
    report += 'Technical measurements; M9 owner result acceptance pending. All 29 approved questions '
    report += 'use fixed top10/depth50/RRF60/no filters. Recall/MRR denominators exclude the three unsupported controls.\n\n'
    report += table(['Mode', 'Recall@1', 'Recall@3', 'Recall@5', 'Recall@10', 'MRR@10',
                     'All groups /26', 'Multi-group complete /4'], [
        [m, *[f"{r['retrieval'][str(k)]['equivalence_aware_Recall_macro']:.4f}" for k in (1,3,5,10)],
         f"{r['MRR_at_10']:.4f}", r['retrieval']['10']['all_required_complete_count'],
         r['retrieval']['10']['multi_group_complete_count']] for m, r in s.items()])
    report += '\nPrimary chunk recall collapses only approved source-equivalent alternatives. '
    report += 'Raw known-positive recall is retained in RESULTS.json; unjudged chunks are not negatives. '
    report += 'Group discovery can succeed via another chunk from the exact same complete parent.\n\n'
    report += '## Actual M8 inclusion by budget\n\n'
    report += table(['Mode','BGE budget','Complete /26','Included groups /31','Mean exact tokens',
                     'Budget-lost groups','Insufficient'], [
        [m,b,r['complete_question_count'],r['included_groups'],f"{r['mean_included_tokens']:.1f}",
         r['budget_lost_group_count'],r['insufficient_evidence_count']]
        for m, mode in s.items() for b,r in mode['budgets'].items()])
    report += '\nThese are current complete-parent packages, not answer-quality or future-LLM-window scores. '
    report += 'Diagnostic expected-parent fit is separate from actual retrieval; it does not enter these scores.\n\n'
    report += '## Per-question discovery and 16K evidence\n\n'
    report += table(['Question','Mode','First positive','Retrieved groups','Included groups at16K',
                     '16K outcome'], [[c['question_id'],c['mode'],c['retrieval']['first_relevant_rank'],
        f"{c['retrieval']['at_k']['10']['parent_groups_retrieved']}/{c['retrieval']['required_group_denominator']}",
        c['budgets']['16000']['groups_included'],c['budgets']['16000']['outcome']] for c in value['cases']])
    report += '\nFull case records include exact IDs/ranks, all budgets, omitted parents/reasons, '
    report += 'context/qualification/citation fingerprints and reconstruction/dedup accounting. '
    report += 'All source payloads remain behind native evidence readers; results contain measurements and references.\n'
    (w / 'RETRIEVAL_AND_EVIDENCE_METRICS.md').write_text(report)
    (w / 'PER_QUESTION_FAILURES.json').write_bytes(encoded(a['failures']))
    (w / 'CATEGORY_METRICS.json').write_bytes(encoded(a['category_comparison']))
    print('MEASURED_REPORTS_WRITTEN', len(questions), len(value['cases']))


if __name__ == '__main__':
    main()
