"""Reuse saved numbers only after complete live old/new source/token/model equivalence."""

import argparse
import copy
import importlib.metadata
import json
import os
from pathlib import Path

from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.chunk_preparation import write_once
from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.embedding_inputs import embedding_id, embedding_input
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.unified_models import encode, sha

NEW_CATALOG = 'config/retrieval-chunks-m3-durable-v1.json'
NEW_SELECTION = 'config/embedding-artifacts-m4-durable-v1.json'
HOME = 'data/embeddings/m4-durable-v1'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def equivalent(old_view, new_view, old_record, old_input, tokenizer):
    """Use only freshly opened native views; callers cannot substitute QA JSON."""
    before, binding = embedding_input(old_view)
    after, new_binding = embedding_input(new_view)
    require(before == after == old_input, 'reuse_source_or_heading_input_changed')
    old_ids, new_ids = tokenizer.encode(before).ids, tokenizer.encode(after).ids
    require(old_ids == new_ids and sha(encode(old_ids)) == old_record['token_ids_sha256'],
            'reuse_token_ids_changed')
    require(binding['qualification_sha256'] == new_binding['qualification_sha256']
            == old_record['qualification_sha256'], 'reuse_qualification_changed')
    a, b = old_view['verified_parent'], new_view['verified_parent']
    for field in ['memberships', 'citation_locators', 'reference_classification', 'consumer']:
        require(encode(a[field]) == encode(b[field]), 'reuse_parent_scope_changed:' + field)
    for field in ['source', 'lineage', 'heading_context_sha256', 'token_count', 'reference_classification']:
        require(old_view['chunk'][field] == new_view['chunk'][field], 'reuse_chunk_source_changed:' + field)
    return after, new_binding, new_ids


def build(root):
    producer_sha = sha(Path(__file__).read_bytes())
    # Both original and new live authorities are required, not detached exports.
    original_corpus = load_c14_verified_corpus(root)
    original_catalog = QualifiedChunkCatalog(root, original_corpus,
        selector='config/retrieval-chunks-m3-c14-scope-v2.json')
    original = EmbeddingArtifacts(root, original_catalog, selector='config/embedding-artifacts-m4-v1.json')
    require(sha(encode(original.manifest)) ==
            'e9e1a5edb83db723384ce8583f053b31d65d93a7318a21d5948fb4f0e71e4baa',
            'reuse_not_the_accepted_embedding_manifest')
    corpus = load_durable_corpus(root)
    catalog = QualifiedChunkCatalog(root, corpus, selector=NEW_CATALOG)
    mappings = json.loads((root / 'data/chunking/m3-durable-v1/CHUNK_ID_RECONCILIATION.json').read_bytes())
    old_rows, new_rows = original_catalog.list_chunks(limit=1000)['items'], catalog.list_chunks(limit=1000)['items']
    require(len(mappings) == len(old_rows) == len(new_rows) == 992, 'reuse_incomplete_992_bijection')
    require(len({m['old_chunk_id'] for m in mappings}) == len({m['new_chunk_id'] for m in mappings}) == 992,
            'reuse_duplicate_mapping')
    require([r['chunk_id'] for r in old_rows] == [m['old_chunk_id'] for m in mappings]
            and [r['chunk_id'] for r in new_rows] == [m['new_chunk_id'] for m in mappings],
            'reuse_row_order_or_scope_changed')
    config = original.manifest['model_configuration']
    require(sha((root / config['path']).read_bytes()) == config['sha256'], 'reuse_model_configuration_changed')
    configuration = json.loads((root / config['path']).read_bytes())
    require({n: importlib.metadata.version(n) for n in configuration['runtime_versions']}
            == configuration['runtime_versions'], 'reuse_pinned_runtime_changed')
    tokenizer = PinnedBgeTokenizer(root)
    old_inputs = {p['chunk_id']: p['text'] for p in map(json.loads,
        (root / original.manifest['inputs_path']).read_text().splitlines())}
    records, inputs, proof = [], [], []
    for i, m in enumerate(mappings):
        old_cid, cid = m['old_chunk_id'], m['new_chunk_id']
        old_view = original.open_bound_chunk(old_cid)
        new_view = catalog.open_chunk(cid)
        old = original.records[old_cid]
        text, binding, ids = equivalent(old_view, new_view, old, old_inputs[old_cid], tokenizer)
        vector, stored = original.get_vector(old_cid)
        require(stored == old and sha(vector.tobytes()) == old['vector_sha256'], 'reuse_numerical_row_changed')
        limit = catalog.manifest['configurations'][new_rows[i]['configuration_id']]['total_tokens']
        require(len(ids) == old['tokens_including_specials'] <= limit == old['total_token_limit'],
                'reuse_budget_changed')
        record = dict(binding, row_index=i, token_ids_sha256=sha(encode(ids)), total_token_limit=limit,
            vector_sha256=old['vector_sha256'], embedding_id=embedding_id(config['sha256'], cid, sha(text.encode())))
        records.append(record)
        inputs.append({'chunk_id': cid, 'text': text,
                       'authority': 'FROZEN_NUMERIC_REPLAY_INPUT_NOT_EVIDENCE_AUTHORIZATION'})
        proof.append({'old_chunk_id': old_cid, 'new_chunk_id': cid,
            'old_unit_id': old['unit_id'], 'new_unit_id': binding['unit_id'],
            'old_embedding_id': old['embedding_id'], 'new_embedding_id': record['embedding_id'],
            'row_index': i, 'input_text_sha256': sha(text.encode()),
            'token_ids_sha256': record['token_ids_sha256'], 'qualification_sha256': binding['qualification_sha256'],
            'model_configuration_sha256': config['sha256'], 'vector_sha256': old['vector_sha256'],
            'both_live_native_views_and_all_scope_fields_verified': True})
        if i == 0 or (i + 1) % 100 == 0 or i == 991:
            print(f'Verified live numerical reuse bijection {i + 1}/992', flush=True)
    original.check()
    catalog.check()
    require(sha(Path(__file__).read_bytes()) == producer_sha, 'reuse_producer_changed_during_run')
    files = {}
    for name, raw in [('inputs.jsonl', b''.join(encode(p) + b'\n' for p in inputs)),
                      ('records.jsonl', b''.join(encode(p) + b'\n' for p in records)),
                      ('NUMERICAL_REUSE_PROOF.json', encode({'status': 'PASS', 'records': proof,
                          'authority': 'BINDING_VERIFICATION_NOT_NEW_QA', 'inference': False,
                          'producer_sha256': producer_sha,
                          'original_manifest_sha256': sha(encode(original.manifest))}))]:
        p = HOME + '/' + name
        write_once(root / p, raw)
        files[p] = sha(raw)
    vp = original.manifest['vectors_path']
    # Reference the immutable original saved matrix; no redundant numerical copy.
    files[vp] = sha((root / vp).read_bytes())
    files['tools/embeddings/rebind_artifacts.py'] = producer_sha
    for p, h in original.manifest['files'].items():
        if p.endswith('/runtime.json'):
            files[p] = h
    selected = json.loads((root / NEW_CATALOG).read_bytes())
    manifest = copy.deepcopy(original.manifest)
    manifest.update(release_id='m4-bge-durable-v1', files=files,
        records_path=HOME + '/records.jsonl', inputs_path=HOME + '/inputs.jsonl', vectors_path=vp,
        catalog_selector={'path': NEW_CATALOG, 'sha256': sha((root / NEW_CATALOG).read_bytes())},
        catalog_manifest_sha256=selected['manifest_sha256'],
        numerical_reuse={'original_manifest_sha256': sha(encode(original.manifest)),
                         'proof_path': HOME + '/NUMERICAL_REUSE_PROOF.json',
                         'all992_live_bijections_verified': True, 'inference': False})
    write_once(root / HOME / 'manifest.json', encode(manifest))
    write_once(root / NEW_SELECTION, encode({'schema': 'embedding-selection-1.0',
        'manifest_path': HOME + '/manifest.json', 'manifest_sha256': sha(encode(manifest))}))
    reused = EmbeddingArtifacts(root, catalog, selector=NEW_SELECTION)
    require(reused.vectors.tobytes() == original.vectors.tobytes(), 'reused_matrix_not_bit_identical')
    reused.check()
    return {'status': 'PASS', 'records': 992, 'shape': list(reused.vectors.shape),
            'manifest_sha256': sha(encode(manifest)), 'inference': False,
            'changed_embedding_ids': sum(p['old_embedding_id'] != p['new_embedding_id'] for p in proof)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    os.umask(0o077)
    print(json.dumps(build(p.parse_args().root.resolve())))
