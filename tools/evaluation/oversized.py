"""Diagnostic token measurements only; no compact evidence or admission changes."""

from tools.indexing.m5_index import encoded


def collect(service, value, labels):
    uid = labels['M9-Q21']['required_evidence_groups'][0]['alternatives'][0]['unit_id']
    observations = []
    for case in value['cases']:
        if case['question_id'] != 'M9-Q21':
            continue
        if uid not in case['retrieval']['relevant_retrieved_parent_ids']:
            observations.append({'mode': case['mode'], 'parent_retrieved': False,
                                 'actual_wrapper_components': None,
                                 'note': 'No counterfactual candidate is inserted into the actual search.'})
            continue
        # Cost inspection outside the four scored budget scenarios. Keeps entire parents.
        result = case['candidate_result']
        p = service.assemble(result, token_budget=1000000)
        service.validate(p, result)
        block = next(x['evidence'] for x in p['parents'] if x['evidence']['unit_id'] == uid)
        fields = {'complete_M8_block': block,
                  'contributing_candidate_diagnostics': block['contributing_candidates'],
                  'chunk_citation_precision_and_lineage': block['citation_precision'],
                  'native_parent': block['verified_parent']}
        texts = [encoded(x).decode() + ('\n' if k == 'complete_M8_block' else '')
                 for k, x in fields.items()]
        counts = service._count(texts)
        actual = next(x['token_count'] for x in case['budgets']['32000']['omitted_parents']
                      if x['unit_id'] == uid)
        if counts[0] != actual:
            raise ValueError('m9_q21_current_block_cost_changed')
        observations.append({'mode': case['mode'], 'parent_retrieved': True,
            'actual_wrapper_components': dict(zip(fields, counts, strict=True)),
            'counting': 'Independent serializations with pinned BGE specials; NON-ADDITIVE.',
            'scored_budget_omitted_cost_matches': True,
            'cost_probe_budget': 1000000,
            'cost_probe_authority': 'DIAGNOSTIC_COST_ONLY_NOT_AN_EXTRA_SCORED_BUDGET_OR_M10_CONTEXT',
            'candidate_contributions': len(block['contributing_candidates'])})
    native = next(x for x in value['component_costs_non_additive'] if x['unit_id'] == uid)
    return {'schema': 'm9-oversized-cost-analysis-1.0', 'unit_id': uid,
            'native_field_costs_non_additive': native, 'actual_query_wrapper_costs': observations,
            'reference_fit': value['expected_parent_fit_diagnostics']['M9-Q21'],
            'compact_projection_implemented': False,
            'usage': 'Measurements only; source content remains behind the original verified gateway.'}
