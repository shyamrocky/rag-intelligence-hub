"""Read-only full successor gate; runnable with OS-denied original workspace access."""

import argparse
import copy
import json
import resource
import sys
import time
from pathlib import Path

from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.unified_models import encode, sha


def verify(root, *, depth='full'):
    tick = time.perf_counter()
    corpus = load_durable_corpus(root)
    catalog = QualifiedChunkCatalog(root, corpus, selector='config/retrieval-chunks-m3-durable-v1.json')
    artifacts = EmbeddingArtifacts(root, catalog, selector='config/embedding-artifacts-m4-durable-v1.json')
    summary = corpus.catalog.get_corpus_summary()
    assert (summary['units'], summary['sections'], summary['membership_edges']) == (553, 3040, 3727)
    rows = catalog.list_chunks(limit=1000)['items']
    assert len(rows) == len(artifacts.records) == 992 and artifacts.vectors.shape == (992, 384)
    all_bindings = corpus.binding_manifest()['files'] | catalog.bound.fingerprints() | artifacts.bound.fingerprints()
    assert not any(p.startswith(('workspace/', 'archive/', 'releases/')) for p in all_bindings)
    tokenizer = PinnedBgeTokenizer(root)
    inputs = {x['chunk_id']: x['text'] for x in map(json.loads,
        (root / artifacts.manifest['inputs_path']).read_text().splitlines())}
    for r in rows:
        record = artifacts.records[r['chunk_id']]
        ids = tokenizer.encode(inputs[r['chunk_id']]).ids
        assert sha(inputs[r['chunk_id']].encode()) == record['input_text_sha256']
        assert sha(encode(ids)) == record['token_ids_sha256']
        assert len(ids) == r['token_count'] <= record['total_token_limit']
    for status, count in [('HOLD', 358), ('EXCLUDED', 110)]:
        page = corpus.catalog.list_sections(filters={'admission_status': status}, limit=1000)
        assert page['total'] == count
        for section in page['items']:
            assert not section['unit_ids'] and not catalog.get_section_chunks(section['section_id'])
    protected, expired, units = set(), set(), set()
    selection = json.loads((root / 'config/html-c10-admission-publication.json').read_bytes())
    c10_native = json.loads((root / selection['manifest_path']).read_bytes())['delta_unit_id']
    c10 = False
    checks = []
    selected = rows if depth == 'full' else rows[:1]
    for i, r in enumerate(selected, 1):
        view = artifacts.open_bound_chunk(r['chunk_id'])
        p = view['verified_parent']
        units.add(p['unit_id'])
        context = p['consumer']['llm_context']
        assert context['qualification']['mandatory'] and context['qualification']['complete_unit_only']
        if p['native_unit_id'] == c10_native:
            assert any(o.get('issue_id') == 'HTML-SRC-SCORE-STAGE' and o.get('must_accompany')
                       and o.get('origin') == 'ingestion_QA_not_publisher' for o in context['qa_observations'])
            assert any(c.get('relationship_type') == 'documented_RRF_context_not_numerical_equivalence'
                       and c.get('required') for c in context['required_context'])
            c10 = True
        if p['document_id'] == 'C04' and 'restricted_projection' in r['source']['pointer']:
            protected.add(p['unit_id'])
        if p['consumer'].get('publication_expiration', {}).get('status') == 'EXPIRED':
            assert p['consumer']['publication_expiration']['warning']
            assert any(o.get('issue_id') == 'PDF_PUBLICATION_EXPIRED'
                       and o.get('display_to_user_when_used') for o in context['qa_observations'])
            expired.add(p['unit_id'])
        if i == 1:
            for field in ['qualification', 'required_context', 'qa_observations']:
                bad = copy.deepcopy(view)
                del bad['verified_parent']['consumer']['llm_context'][field]
                try:
                    catalog.validate_view(bad)
                except ValueError:
                    checks.append('reject_removed_' + field)
                else:
                    raise ValueError('accepted_stripped_' + field)
            for field in ['source_slice', 'source_span', 'publication', 'lineage']:
                bad = copy.deepcopy(view)
                if field == 'source_slice':
                    bad['source_slice'] += ' forged'
                elif field == 'source_span':
                    bad['chunk']['source']['start'] += 1
                elif field == 'publication':
                    bad['verified_parent']['publication_identity'] = {}
                else:
                    bad['chunk']['lineage']['section_ids'].append('forged')
                try:
                    catalog.validate_view(bad)
                except ValueError:
                    checks.append('reject_forged_' + field)
                else:
                    raise ValueError('accepted_forged_' + field)
        if i % 100 == 0:
            print(f'Successor verified complete live bindings {i}/992', flush=True)
    if depth == 'full':
        assert len(units) == 553 and len(protected) == 4 and len(expired) == 13 and c10
    artifacts.check()
    return {'status': 'PASS', 'authority': 'VERIFICATION_NOT_QA_OR_OWNER_ACCEPTANCE',
        'depth': depth, 'summary': summary, 'chunks': len(rows), 'vectors': list(artifacts.vectors.shape),
        'opened_live_bindings': len(selected), 'opened_unique_parents': len(units),
        'protected_Markdown_units': len(protected), 'expiry_warning_units': len(expired),
        'C10_context_checked': c10, 'negative_controls': checks,
        'binding_files': len(all_bindings), 'workspace_binding_files': 0,
        'numerical_inference': False, 'seconds': time.perf_counter() - tick,
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--depth', choices=['full', 'sample'], default='full')
    args = p.parse_args()
    root = args.root.resolve()
    denied = []
    def observe(event, values):
        if event in {'socket.connect', 'socket.getaddrinfo'}:
            raise PermissionError('successor_network_access_forbidden')
        if event == 'open' and values and isinstance(values[0], str):
            path = Path(values[0])
            path = path if path.is_absolute() else root / path
            if path.is_relative_to(root / 'workspace'):
                mode = values[1]
                if not isinstance(mode, str) or not any(k in mode for k in 'wax+'):
                    denied.append(str(path))
                    raise PermissionError('original_workspace_read_forbidden')
    sys.addaudithook(observe)
    try:
        (root / 'workspace/owned-denial-control').read_bytes()
    except PermissionError:
        denial_control = True
    else:
        raise ValueError('workspace_read_denial_not_active')
    denied.clear()
    result = verify(root, depth=args.depth)
    result['denial_control_blocked'] = denial_control
    result['denied_workspace_read_attempts'] = denied
    print(json.dumps(result))
