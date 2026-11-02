"""Small read-only comparative M9 view; native inspectors retain evidence authority."""

from pathlib import Path

RESULT_SELECTOR_SHA256 = "f3420b4645ac8b37819a37750d1d9a33e74b7d1e828f7711eef14e573d868ece"
DURABLE = 'config/retrieval-chunks-m3-durable-v1.json'


def get_results(root, expected_sha):
    import sys

    project = Path(__file__).resolve().parents[2]
    if Path(root).resolve(strict=True) != project:
        raise ValueError('m9_dashboard_requires_installed_project_root')
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    from tools.evaluation.results import load_results

    return load_results(project, expected_sha=expected_sha)


def select_query(state, query, mode):
    state['m7_query'] = query
    state['m7_mode'] = mode


def render(root, *, selector):
    import pandas as pd
    import streamlit as st

    from rag_hub.m5_dashboard import open_parent

    with st.expander('M9 · Retrieval evaluation', expanded=False):
        st.caption('Measured retrieval, verified evidence availability and token cost. '
                   'No generated answers or new QA authority.')
        if selector != DURABLE:
            st.info('Select the durable operational release for M9. Historical inspection is unchanged.')
            return
        if not st.checkbox('View M9 measured evaluation', key='m9_enabled'):
            return
        try:
            # Small measurement JSON only; recheck fingerprints on every requested render.
            data = get_results(root, RESULT_SELECTOR_SHA256)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            st.error('M9 measurement integrity unavailable. No fallback or fabricated metrics.')
            st.text(str(exc))
            return
        value = data['results']
        st.info('29 owner-approved questions · 26 answerable / 3 unsupported · 16 documents. '
                'Known-positive labels are bounded; unjudged chunks are not negatives. '
                'This source-authored set is not a blind held-out test.')
        st.caption('Fixed top-10 · depth 50 · RRF 60 · no filters. '
                   'Chunk recall collapses only approved equivalent representations; '
                   'raw qrels recall remains available separately.')
        rows = []
        for mode, record in value['summary'].items():
            row = {'Mode': mode, 'MRR@10': record['MRR_at_10']}
            for k in (1, 3, 5, 10):
                row[f'Recall@{k}'] = record['retrieval'][str(k)]['equivalence_aware_Recall_macro']
            row['Group coverage@10'] = record['retrieval']['10']['parent_group_coverage_micro']
            row['Complete questions / 26'] = record['retrieval']['10']['all_required_complete_count']
            row['Complete multi-group / 4'] = record['retrieval']['10']['multi_group_complete_count']
            rows.append(row)
        st.subheader('Retrieval discovery')
        st.dataframe(rows, hide_index=True, width='stretch')
        with st.expander('Raw bounded qrels denominators and metrics'):
            st.json({m: {k: v for k, v in record.items() if k != 'budgets'}
                     for m, record in value['summary'].items()}, expanded=False)
        budget_rows = []
        for mode, record in value['summary'].items():
            for budget, b in record['budgets'].items():
                budget_rows.append({'Mode': mode, 'Budget': int(budget),
                    'Complete questions / 26': b['complete_question_count'],
                    'Included required groups': b['included_groups'],
                    'Mean exact tokens': b['mean_included_tokens'],
                    'Mean utilization': b['mean_utilization'],
                    'Budget-lost groups': b['budget_lost_group_count'],
                    'Insufficient packages': b['insufficient_evidence_count']})
        with st.expander('Per-category comparisons — small samples'):
            st.caption('Category denominators are explicit; most categories have only one question. No statistical generalization.')
            st.dataframe(data['analysis']['category_comparison'], hide_index=True, width='stretch')
        st.subheader('Complete evidence within token budgets')
        st.caption('Actual unchanged M8 packages; BGE counting is not an M10 model context choice. '
                   'Integrity failure, retrieval miss and budget omission are distinct.')
        st.dataframe(budget_rows, hide_index=True, width='stretch')
        frame = pd.DataFrame(budget_rows).pivot(index='Budget', columns='Mode',
                                               values='Complete questions / 26')
        st.line_chart(frame)
        with st.expander('Relevant groups per token, deduplication and reference-only fit diagnostics'):
            st.caption('Efficiency is a proxy, not answer quality. Reference-only fit is diagnostic and never a retrieval score.')
            st.dataframe(data['analysis']['efficiency_by_mode_budget'], hide_index=True, width='stretch')
        st.subheader('Q21 · Oversized C14 bibliography')
        st.caption('Current live measurements, not the earlier approximate 84,064-token observation. '
                   'Component token counts are independently serialized and non-additive.')
        st.dataframe(data['analysis']['q21_comparison'], hide_index=True, width='stretch')
        with st.expander('Source versus envelope component measurements'):
            st.json({'largest_native_parents': value['component_costs_non_additive'],
                     'Q21_actual_wrappers': data['analysis']['oversized_current_cost_analysis'],
                     'C16_shared_QA_attachment': data['analysis']['oversized_attachment_structure']},
                    expanded=False)
        st.subheader('Per-question diagnostics')
        ids = [q['question_id'] for q in data['questions']]
        qid = st.selectbox('Benchmark question', ids, key='m9_question')
        question = next(q for q in data['questions'] if q['question_id'] == qid)
        st.write(question['question'])
        st.caption(question['category'] + ' · owner-approved ' + question['proposed_answerability'])
        budget = st.selectbox('M9 evidence scenario', [4000, 8000, 16000, 32000],
                              index=2, key='m9_scenario')
        cases = [c for c in value['cases'] if c['question_id'] == qid]
        display = []
        for case in cases:
            r, b = case['retrieval'], case['budgets'][str(budget)]
            display.append({'Mode': case['mode'], 'First relevant rank': r['first_relevant_rank'],
                'Retrieved groups': r['at_k']['10']['parent_groups_retrieved'],
                'Required groups': r['required_group_denominator'], 'Included groups': b['groups_included'],
                'Exact tokens': b['included_tokens'], 'Omitted parents': len(b['omitted_parents']),
                'Outcome': b['outcome']})
        st.dataframe(display, hide_index=True, width='stretch')
        diagnostic = value['expected_parent_fit_diagnostics'][qid]
        with st.expander('Diagnostic reference-parent fit — NOT retrieval performance'):
            st.json(diagnostic, expanded=False)
        failures = [f for f in data['analysis']['failures'] if f['question_id'] == qid]
        if failures:
            st.dataframe([{**f, 'budget': str(f['budget'])} for f in failures],
                         hide_index=True, width='stretch')
        with st.expander('Approved evidence groups / source alternatives'):
            st.json(data['labels'][qid]['required_evidence_groups'], expanded=False)
        mode = st.selectbox('Inspect measured retrieval mode', ['bm25', 'vector', 'hybrid'],
                            key='m9_inspect_mode')
        selected_case = next(c for c in cases if c['mode'] == mode)
        with st.expander('Actual parent inclusion and omission details'):
            scenario = selected_case['budgets'][str(budget)]
            st.caption(f"Exact tokens {scenario['included_tokens']:,}; remaining {scenario['remaining_budget']:,}. "
                       'Complete parents only; source eligibility is unchanged by budget omission.')
            st.write('Included Unit IDs')
            st.code('\n'.join(scenario['included_parent_ids']) or 'None')
            if scenario['omitted_parents']:
                st.dataframe(scenario['omitted_parents'], hide_index=True, width='stretch')
        st.button('Copy this question to existing M7 search', key='m9_to_m7',
                  on_click=select_query, args=(st.session_state, question['question'], mode))
        st.caption('Submit the copied query in M7 for live candidates, then use its existing M8 '
                   'evidence action. Saved M9 metrics do not authorize source evidence.')
        st.dataframe(selected_case['candidate_result']['candidates'], hide_index=True, width='stretch')
        for hit in selected_case['candidate_result']['candidates']:
            st.button(f"Open live verified parent · M9 #{hit['rank']} · {hit['document_id']}",
                      key='m9_parent_' + hit['chunk_id'], on_click=open_parent,
                      args=(st.session_state, hit['chunk_id']))
        st.warning('Chunk-size comparison PENDING: historical C01 256/384 pilots lack two '
                   'compatible retrieval pipelines. No alternative index or compact evidence was built.')
        with st.expander('Measured release and sampling limits'):
            st.json({'manifest': data['manifest'], 'limitations': value['limitations']}, expanded=False)
