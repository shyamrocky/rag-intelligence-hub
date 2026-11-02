"""Read-only local H4 measurement/negative controls, one explicitly selected mode.

Run in the locked dashboard environment. No corpus regeneration or model import.
Reports are inspection-only and never replace the live evidence gateway.
"""

import argparse
import copy
import json
import os
import resource
import sys
from pathlib import Path
from time import perf_counter

from rag_hub.operational_selection import DURABLE, HISTORICAL, MODES


def measure(root, selector):
    from rag_hub.chunk_dashboard import load_chunk_catalog
    from rag_hub.dashboard_ui import load_dashboard
    from rag_hub.operational_selection import (
        EmbeddingMetadata,
        construct_catalog,
        resolve_selection,
    )

    start = perf_counter()
    selection = resolve_selection(root, selector)
    data = load_dashboard(str(root), selector=selector)
    cold = perf_counter() - start
    start = perf_counter()
    cat = load_chunk_catalog(str(root), selector, _data=data)
    catalog_seconds = perf_counter() - start
    start = perf_counter()
    assert load_dashboard(str(root), selector=selector) is data
    assert load_chunk_catalog(str(root), selector, _data=data) is cat
    warm = perf_counter() - start
    start = perf_counter()
    data.document('C01')
    document_seconds = perf_counter() - start
    row = cat.list_chunks('C01', limit=1)['items'][0]
    start = perf_counter()
    view = cat.open_chunk(row['chunk_id'])
    cat.validate_view(view)
    chunk_seconds = perf_counter() - start
    edges = data.relationships(row['unit_id'])
    assert len(cat.get_chunk_sections(row['chunk_id'])) == len(edges)
    for edge in edges:
        assert row['unit_id'] in data.section(edge['section_id'])['unit_ids']
        assert row['chunk_id'] in {cid for link in cat.get_section_chunks(edge['section_id'])
                                   for cid in link['chunk_ids']}
    negatives = []
    for aspect in ['slice', 'publication', 'context', 'qa']:
        altered = copy.deepcopy(view)
        if aspect == 'slice':
            altered['source_slice'] = 'forged'
        elif aspect == 'publication':
            altered['verified_parent']['publication_identity'] = {'forged': True}
        elif aspect == 'context':
            altered['verified_parent']['consumer']['llm_context']['qualification'] = {}
        else:
            altered['verified_parent']['consumer']['llm_context']['qa_observations'] = ['forged']
        try:
            cat.validate_view(altered)
        except ValueError:
            negatives.append(aspect)
        else:
            raise ValueError('false_acceptance:' + aspect)
    extra = {}
    if selector == DURABLE:
        start = perf_counter()
        extra['embedding_metadata'] = EmbeddingMetadata(root, cat).export()
        extra['metadata_seconds'] = perf_counter() - start
        extra['model_modules_loaded'] = [m for m in ['torch', 'transformers', 'sentence_transformers']
                                         if m in sys.modules]
        assert extra['model_modules_loaded'] == []
        extra['workspace_bindings'] = [p for p in data.binding_fingerprints
                                       if p.startswith('workspace/')]
        assert extra['workspace_bindings'] == []
        rows = cat.list_chunks(limit=1000)['items']
        extra['selective_512_cases'] = [r['chunk_id'] for r in rows if r['token_count'] > 384]
        assert len(extra['selective_512_cases']) == 4
        special = []
        for did in ['C04', 'C06', 'C10', 'C14', 'C16']:
            candidates = [r for r in rows if r['document_id'] == did and (
                r['token_count'] > 384 or r['source']['content_type'] in {
                    'bibliography', 'code_example', 'code_block', 'table'})]
            for item in candidates[:6]:
                opened = cat.open_chunk(item['chunk_id'])
                cat.validate_view(opened)
                special.append({'chunk_id': item['chunk_id'], 'unit_id': item['unit_id'],
                                'document_id': did, 'content_type': item['source']['content_type']})
        extra['special_parent_checks'] = special
        # Deliberately supply the current corpus to a historical catalog. No aliases.
        try:
            construct_catalog(root, data, resolve_selection(root, HISTORICAL))
        except ValueError as exc:
            assert 'incompatible_operational_corpus_and_catalog' in str(exc)
            negatives.append('cross_release_corpus')
        else:
            raise ValueError('false_cross_release_acceptance')
    data.check()
    cat.check()
    return {'result': 'PASS', 'selector': selector, 'release_key': selection.key,
            'corpus': data.summary(), 'catalog_units': selection.spec['catalog_units'],
            'chunks': cat.manifest['summary']['chunks'], 'cold_corpus_seconds': cold,
            'catalog_seconds': catalog_seconds, 'warm_selection_seconds': warm,
            'document_lookup_seconds': document_seconds, 'chunk_inspection_seconds': chunk_seconds,
            'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'negative_controls_rejected': negatives, **extra}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selector', required=True, choices=list(MODES))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--deny-workspace', action='store_true')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output.resolve()
    if not output.is_relative_to(root / 'workspace') or output.exists():
        raise ValueError('new_private_report_path_required')
    denied = []
    if args.deny_workspace:
        if args.selector != DURABLE:
            raise ValueError('historical_modes_intentionally_require_original_evidence')

        def audit(event, values):
            if event != 'open' or not isinstance(values[0], (str, bytes, os.PathLike)):
                return
            target = Path(os.fsdecode(values[0])).resolve()
            mode, flags = values[1], values[2]
            reading = 'r' in (mode or '') or (mode is None and flags & os.O_ACCMODE == os.O_RDONLY)
            if reading and target.is_relative_to(root / 'workspace'):
                denied.append(str(target.relative_to(root)))
                raise PermissionError('H4 workspace read denied')

        sys.addaudithook(audit)
        try:
            (root / 'workspace/BUILD_CONTEXT.md').read_bytes()
        except PermissionError:
            pass
        else:
            raise ValueError('workspace_denial_control_not_active')
        denied.clear()
    result = measure(root, args.selector)
    if args.deny_workspace:
        result['workspace_denial'] = {'mechanism': 'Python audit hook, not kernel isolation',
            'positive_blocked_read': True, 'runtime_read_attempts': denied}
        assert not denied
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
