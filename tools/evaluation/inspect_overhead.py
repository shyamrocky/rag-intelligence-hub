"""Reproduce oversized QA-attachment structure diagnostics without inference."""

import argparse
import json
from pathlib import Path

from tools.evidence.service import EvidenceService
from tools.indexing.m5_index import encoded, local, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default='data/evals/m9/runs/m9-v3')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    out = local(root, args.run)
    if not out.is_relative_to(root / 'data/evals/m9/runs'):
        raise ValueError('m9_diagnostic_output_must_be_private_run_data')
    value = json.loads((out / 'RESULTS.json').read_bytes())
    service = EvidenceService(root, selector='config/evidence-reconstruction-m8-v1.json',
        selector_sha256='e0ac189c8b5ffd331f28ae87f81d56c22868e12c45d7b73e6a5e7f1a65c6bef2')
    rows = []
    for cost in value['component_costs_non_additive']:
        if cost['document_id'] != 'C16':
            continue
        parent = service.corpus.evidence.get_verified_unit(cost['unit_id'])
        service.corpus.evidence.validate(parent)
        observations = parent['consumer']['llm_context']['qa_observations']
        items = []
        for item in observations:
            sizes = [{'field': k, 'type': type(v).__name__,
                      'members': len(v) if isinstance(v, (dict, list)) else None,
                      'serialized_characters': len(encoded(v).decode()), 'sha256': sha(encoded(v))}
                     for k, v in item.items()]
            items.append({'keys': list(item), 'issue_id': item.get('issue_id'),
                          'kind': item.get('kind'), 'origin': item.get('origin'),
                          'largest_fields': sorted(sizes, key=lambda x: -x['serialized_characters'])[:5]})
        rows.append({'unit_id': parent['unit_id'], 'document_id': 'C16',
            'QA_observations_sha256': sha(encoded(observations)),
            'QA_observation_count': len(observations),
            'QA_observations_characters': len(encoded(observations).decode()), 'observations': items,
            'native_source_field_tokens': cost['fields'][
                'text_bearing_source_fields_including_inseparable_warnings']['tokens'],
            'QA_observation_tokens_independent': cost['fields']['qa_observations']['tokens']})
    service.check()
    result = {'authority': 'INSPECTION_ONLY_NOT_SOURCE_OR_QA_CHANGE',
        'scope': 'Five largest observed C16 native parent envelopes; no reparsing, projection or contract change.',
        'records': rows,
        'distinct_QA_payload_hashes': len({x['QA_observations_sha256'] for x in rows}),
        'interpretation': 'Compare immutable QA attachment structures with required narrative qualifications. '
            'Repeated audit evidence is not publisher content. No fields were removed or new consumable view created.'}
    path = out / 'OVERSIZED_STRUCTURE_INSPECTION.json'
    payload = encoded(result)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError('m9_immutable_overhead_inspection_differs')
        print('PASS_IDENTICAL_READ_ONLY_DIAGNOSTIC_REPRODUCTION')
    else:
        path.write_bytes(payload)
        path.chmod(0o600)
        print('PASS_DIAGNOSTIC_CREATED_WITHOUT_SOURCE_CHANGE')


if __name__ == '__main__':
    main()
