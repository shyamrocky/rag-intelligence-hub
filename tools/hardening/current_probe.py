"""Read-only accepted-chain probe and file-open trace; no model inference or publication."""

import argparse
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if not output.is_relative_to((root / 'workspace').resolve()) or output.exists():
        raise ValueError('new_private_report_directory_required')
    output.mkdir(parents=True)
    # Record current runtime reads, not fixture/probe report writes. The audit
    # hook is observational only: it never modifies paths, code or validation.
    opened, callers = Counter(), {}
    prefix = str(root / 'workspace') + '/'

    def observe(event, values):
        if event != 'open' or not values or not isinstance(values[0], str):
            return
        name = values[0]
        name = str(root / name) if not Path(name).is_absolute() else name
        if not name.startswith(prefix) or name.startswith(str(output) + '/'):
            return
        mode = values[1]
        if isinstance(mode, str) and any(flag in mode for flag in 'wax+'):
            return
        relative = str(Path(name).relative_to(root))
        opened[relative] += 1
        stack, frame = [], sys._getframe(1)
        for _ in range(10):
            if frame is None:
                break
            filename = frame.f_code.co_filename
            if filename.startswith(str(root / 'src') + '/'):
                stack.append(f'{Path(filename).relative_to(root)}:{frame.f_lineno}:{frame.f_code.co_name}')
            frame = frame.f_back
        callers.setdefault(relative, set()).add(tuple(stack))

    sys.addaudithook(observe)
    from rag_hub.c14_unified_selection import load_c14_verified_corpus
    from rag_hub.embedding_artifacts import EmbeddingArtifacts
    from rag_hub.m2_tokenizer import PinnedBgeTokenizer
    from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
    from rag_hub.unified_models import encode, sha

    tick = time.perf_counter()
    corpus = load_c14_verified_corpus(root)
    catalog = QualifiedChunkCatalog(root, corpus, selector='config/retrieval-chunks-m3-c14-scope-v2.json')
    artifacts = EmbeddingArtifacts(root, catalog, selector='config/embedding-artifacts-m4-v1.json')
    rows = catalog.list_chunks(limit=1000)['items']
    summary = corpus.catalog.get_corpus_summary()
    expected = {'documents': 16, 'sections': 3040, 'admitted': 2572, 'excluded': 110,
                'HOLD': 358, 'units': 553, 'membership_edges': 3727}
    if any(summary[k] != v for k, v in expected.items()) or len(rows) != 992:
        raise ValueError('accepted_scope_changed')
    unit_metadata = {u['unit_id']: u for u in corpus.catalog.list_units()}
    prepared = {p['unit_id']: p for p in map(json.loads, (root /
        'data/chunking/m3-c14-scope-v1/m0-m1-prepared-inputs.jsonl').read_text().splitlines())}
    if prepared.keys() != unit_metadata.keys():
        raise ValueError('preparation_parent_accounting_changed')
    inputs = {p['chunk_id']: p['text'] for p in map(json.loads,
        artifacts.bound.path(artifacts.manifest['inputs_path']).read_text().splitlines())}
    tokenizer = PinnedBgeTokenizer(root)
    invariants = []
    for row in rows:
        cid, uid = row['chunk_id'], row['unit_id']
        r, p = artifacts.records[cid], prepared[uid]
        tokens = tokenizer.encode(inputs[cid]).ids
        if sha(inputs[cid].encode()) != r['input_text_sha256'] or sha(encode(tokens)) != r['token_ids_sha256']:
            raise ValueError('saved_input_or_tokens_changed')
        if r['qualification_sha256'] != sha(encode(p['qualification'])):
            raise ValueError('stored_qualification_changed')
        invariants.append({
            'logical_key': cid, 'old_chunk_id': cid, 'old_unit_id': uid,
            'old_embedding_id': r['embedding_id'], 'row_index': r['row_index'],
            'document_id': r['document_id'],
            'source_scope_sha256': sha(encode({'source': r['source'],
                'classification': r['reference_classification'],
                'required_context': p['required_context'], 'qa_observations': p['qa_observations']})),
            'source_spans_sha256': sha(encode(r['lineage'])),
            'memberships_sha256': sha(encode(p['memberships'])),
            'qualification_sha256': r['qualification_sha256'],
            'citation_sha256': sha(encode(p['citation_locators'])),
            'input_text_sha256': r['input_text_sha256'], 'token_ids_sha256': r['token_ids_sha256'],
            'encoding_sha256': artifacts.manifest['model_configuration']['sha256'],
            'vector_sha256': r['vector_sha256'],
        })
    # Open a small risk-stratified sample via the live gateway. The H1 full-v2
    # 992-parent replay is historical reuse, never presented as a fresh run.
    protected, sample = [], []
    for row in rows:
        if (row['document_id'] == 'C04' and 'restricted_projection' in row['source']['pointer']
                and row['unit_id'] not in protected):
            protected.append(row['unit_id'])
            sample.append(row)
    for doc in ('C01', 'C02', 'C06'):
        sample.append(next(r for r in rows if r['document_id'] == doc))
    c14 = json.loads((root / 'data/normalized/pdf/c14-scope-correction-v1/C14.json').read_bytes())
    replacements = set(c14['scope_correction']['replacement_unit_ids'])
    html_selection = json.loads((root / 'config/html-c10-admission-publication.json').read_bytes())
    delta = json.loads((root / html_selection['manifest_path']).read_bytes())['delta_unit_id']
    for u in unit_metadata.values():
        if u['native_unit_id'] in replacements or u['native_unit_id'] == delta:
            sample.append(next(r for r in rows if r['unit_id'] == u['unit_id']))
    views = []
    for row in sample:
        view = artifacts.open_bound_chunk(row['chunk_id'])
        parent = view['verified_parent']
        views.append({'chunk_id': row['chunk_id'], 'unit_id': row['unit_id'],
                      'document_id': row['document_id'], 'validated_view_sha256': sha(encode(view)),
                      'publication_identity_sha256': sha(encode(parent['publication_identity'])),
                      'qualification_sha256': sha(encode(parent['consumer']['llm_context']['qualification']))})
    artifacts.check()
    bindings = corpus.binding_manifest()['files'] | catalog.bound.fingerprints() | artifacts.bound.fingerprints()
    dependencies = sorted(p for p in bindings if p.startswith('workspace/'))
    selected = json.loads((root / 'data/chunking/m3-c14-scope-v2/manifest.json').read_bytes())
    recorded = {p for p in selected['upstream_files'] | selected['components'] if p.startswith('workspace/')}
    if set(dependencies) != recorded or len(recorded) != 88:
        raise ValueError('workspace_inventory_changed')
    result = {'schema': 'H2-H3-current-chain-inspection-1.0', 'result': 'PASS',
              'authority': 'INSPECTION_ONLY_NOT_NEW_ADMISSION', 'corpus': expected,
              'chunks': len(rows), 'vectors': list(artifacts.vectors.shape),
              'all_saved_rows_inputs_tokens_and_vector_hashes_verified': True,
              'fresh_live_parent_sample': views, 'fresh_live_parent_sample_count': len(views),
              'all992_live_parent_replay': 'REUSED_H1_FULL_V2_NOT_NEWLY_EXECUTED',
              'bindings': bindings, 'workspace_dependencies': dependencies,
              'workspace_open_trace': {p: {'open_count': opened[p],
                  'caller_stacks': [list(s) for s in sorted(callers.get(p, []))]}
                  for p in sorted(opened)},
              'unlisted_workspace_reads': sorted(set(opened) - recorded),
              'no_workspace_successor_proven': False,
              'seconds': time.perf_counter() - tick,
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'model_inference': False, 'new_identities_generated': False}
    for name, obj in [('CURRENT_CHAIN.json', result), ('VECTOR_REUSE_BASELINE.json', {
            'schema': 'H2-H3-pre-migration-comparison-baseline-1.0',
            'authority': 'COMPARISON_ONLY_NOT_AUTHORIZATION', 'records': invariants})]:
        with (output / name).open('x') as stream:
            stream.write(json.dumps(obj, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['result', 'corpus', 'chunks', 'vectors',
        'fresh_live_parent_sample_count', 'seconds', 'peak_rss_bytes', 'unlisted_workspace_reads']}))


if __name__ == '__main__':
    main()
