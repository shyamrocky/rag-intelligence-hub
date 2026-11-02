"""Replay accepted M0-M3 boundaries against the explicit durable publication.

No hand-edited chunks, fresh boundary inference, QA authority or model inference.
"""

import argparse
import copy
import json
import os
from pathlib import Path

from rag_hub.c14_chunking import chunk_c14
from rag_hub.chunk_preparation import write_once
from rag_hub.chunk_remediation import BoundedRemediator
from rag_hub.corpus_chunking import CorpusChunker
from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.qualified_chunk_catalog import QUALIFIED_CONFIG, QualifiedChunkCatalog
from rag_hub.qualified_chunking import QualifiedChunker
from rag_hub.qualified_preparation import QualifiedPreparation
from rag_hub.retrieval_chunks import from_proposal
from rag_hub.unified_models import encode, sha

OLD = 'data/chunking/m3-c14-scope-v2/manifest.json'
HOME = 'data/chunking/m3-durable-v1'
SELECTOR = 'config/retrieval-chunks-m3-durable-v1.json'


def read(root, path):
    return json.loads((root / path).read_bytes())


def lines(root, path):
    return [json.loads(s) for s in (root / path).read_text().splitlines() if s.strip()]


def key(p):
    return p['source_pointer'], p['display_start'], p['display_end']


def build(root):
    old = read(root, OLD)
    for p, h in old['files'].items():
        if sha((root / p).read_bytes()) != h:
            raise ValueError('changed_accepted_M3_payload')
    corpus = load_durable_corpus(root)
    prep = QualifiedPreparation(root, corpus)
    tokenizer = PinnedBgeTokenizer(root)
    base, bounded, qualified = (CorpusChunker(prep.original, tokenizer),
        BoundedRemediator(prep.original, tokenizer), QualifiedChunker(prep, tokenizer))
    metadata = {u['native_unit_id']: u for u in corpus.catalog.list_units()}
    old_records = lines(root, 'data/chunking/m3-c14-scope-v1/m0-m1-prepared-inputs.jsonl')
    old_rows = lines(root, old['chunks_path'])
    by_old = {}
    for row in old_rows:
        by_old.setdefault(row['unit_id'], []).append(row)
    mapping = {r['unit_id']: metadata[r['unit_id'].split(':', 2)[2]]['unit_id'] for r in old_records}
    if len(mapping) != 553 or len(set(mapping.values())) != 553:
        raise ValueError('nonbijective_durable_unit_scopes')
    migrations = read(root, 'data/validation/provenance/durable-consumer-v1/EVIDENCE_MIGRATION.json')['rows']
    paths = {r['path']: r['proposed_target'] for r in migrations if r['new_active_role'] == 'RETAIN_EVIDENCE'}
    paths['config/unified-c14-scope-selection-v1.json'] = 'config/unified-durable-selection-v1.json'
    def remap_components(components):
        result = {paths.get(p, p): sha((root / paths[p]).read_bytes()) if p in paths else h
                  for p, h in components.items()}
        if any(p.startswith('workspace/') for p in result):
            raise ValueError('unmigrated_chunk_component')
        return result
    config_map, configs = {}, {}
    used = {r['configuration_id'] for r in old_rows}
    for cid in used:
        before = old['configurations'][cid]
        config = copy.deepcopy(before)
        config['components'] = remap_components(config['components'])
        if 'authorized_search_fields' in config:
            config['authorized_search_fields'] = [[mapping[uid], pointer]
                                                  for uid, pointer in config['authorized_search_fields']]
        new_id = cid if config == before else 'chunk-config:' + sha(encode(config))
        configs[new_id], config_map[cid] = config, new_id
    rebuilt, prepared, validation, comparisons = {}, [], [], []
    units = []
    for number, previous in enumerate(old_records, 1):
        old_uid = previous['unit_id']
        uid = mapping[old_uid]
        meta = metadata[old_uid.split(':', 2)[2]]
        record = prep.original.prepare(uid)
        actual = record.model_dump(mode='json')
        for field in previous:
            if (field not in {'record_id', 'unit_id', 'publication_identity', 'evidence_sha256'}
                    and encode(previous[field]) != encode(actual[field])):
                raise ValueError('durable_source_context_or_qualification_changed:' + old_uid + ':' + field)
        prepared.append(actual)
        p = None
        generated = {}
        source_fields = {}
        for original in by_old[old_uid]:
            cid, pointer = original['configuration_id'], original['source']['pointer']
            schema = old['configurations'][cid]['schema']
            group = (schema, pointer if schema in {
                'm3-bounded-remediation-config-1.0', QUALIFIED_CONFIG} else '')
            if group not in generated:
                if schema == 'm3-configuration-1.0':
                    result = base.chunk(record, total_tokens=384)
                elif schema == 'm3-bounded-remediation-config-1.0':
                    result = bounded.remediate(record, pointer)
                elif schema == QUALIFIED_CONFIG:
                    if p is None:
                        p = prep.prepare(uid)
                    result = qualified.chunk(p, pointer)
                elif schema == 'm3-c14-source-scope-config-1.0':
                    if p is None:
                        p = prep.prepare(uid)
                    result = chunk_c14(prep, p, tokenizer, total_tokens=384)
                else:
                    raise ValueError('unknown_accepted_chunking_algorithm')
                generated[group] = {key(piece): piece for piece in result['chunks']}
                source_fields[group] = result
            target = (pointer, original['source']['start'], original['source']['end'])
            proposal = generated[group].get(target)
            if proposal is None:
                raise ValueError('accepted_structural_boundary_not_reproduced')
            # Reconstruct the old row from verified new source plus the exact old
            # parent bindings. No original source/config/lineage field is patched.
            parent = dict(meta, native_handle=original['parent_binding']['native_handle'])
            parent['publication_identity'] = previous['publication_identity']
            reproduced = from_proposal(dict(proposal, unit_id=old_uid), parent, cid).model_dump(mode='json')
            if reproduced != original:
                raise ValueError('accepted_chunk_replay_changed:' + ','.join(
                    k for k in reproduced if reproduced[k] != original[k]))
            new = from_proposal(proposal, meta, config_map[cid]).model_dump(mode='json')
            if new['source'] != original['source'] or new['lineage'] != original['lineage']:
                raise ValueError('source_interval_or_lineage_changed')
            if (new['token_count'], new['heading_context_sha256']) != (
                    original['token_count'], original['heading_context_sha256']):
                raise ValueError('token_input_or_heading_changed')
            rebuilt[original['chunk_id']] = new
        units.append({'old_unit_id': old_uid, 'new_unit_id': uid,
                      'native_unit_id': meta['native_unit_id'], 'document_id': meta['document_id'],
                      'source_memberships_qualifications_unchanged': True})
        validation.append({'old_unit_id': old_uid, 'unit_id': uid, 'record_id': actual['record_id'],
                           'all_source_context_QA_spans_and_qualifications_equal': True,
                           'accepted_boundaries_reproduced': len(by_old[old_uid])})
        if meta['document_id'] == 'C01':
            for budget in [256, 384]:
                result = base.chunk(record, total_tokens=budget)
                comparisons.append({'unit_id': uid, 'budget': budget, 'source_results': result['source_results'],
                    'token_counts': [c['token_count'] for c in result['chunks']],
                    'unresolved': result['unresolved']})
        if number == 1 or number % 50 == 0 or number == 553:
            print(f'Replayed authorized preparation and boundaries {number}/553', flush=True)
    chunks = [rebuilt[c['chunk_id']] for c in old_rows]
    if len(chunks) != 992 or len({c['chunk_id'] for c in chunks}) != 992:
        raise ValueError('incomplete_durable_chunk_bijection')
    chunkmap = [{'old_chunk_id': old['chunk_id'], 'new_chunk_id': new['chunk_id'],
                 'old_unit_id': old['unit_id'], 'new_unit_id': new['unit_id'],
                 'old_configuration_id': old['configuration_id'],
                 'new_configuration_id': new['configuration_id'],
                 'source_and_tokens_unchanged': True}
                for old, new in zip(old_rows, chunks, strict=True)]
    outcomes = copy.deepcopy(read(root, old['units_path']))
    for o in outcomes:
        o['unit_id'] = mapping[o['unit_id']]
        o['chunk_ids'] = [c['chunk_id'] for c in chunks if c['unit_id'] == o['unit_id']]
    summary = copy.deepcopy(old['summary'])
    summary['durable_packaging'] = {'old_units': 553, 'new_units': 553, 'old_chunks': 992,
        'new_chunks': 992, 'changed_chunk_ids': sum(x['old_chunk_id'] != x['new_chunk_id'] for x in chunkmap),
        'unchanged_source_and_context_coverage': True}
    old_structure = read(root, old['structural_witness_index'])
    structure = {'schema': 'durable-source-structure-witnesses-1.0',
                 'authority': 'SOURCE_BOUND_REPLAY_EVIDENCE_NOT_ADMISSION',
                 'fields': [{'unit_id': mapping[f['unit_id']], 'historical_unit_id': f['unit_id'],
                             'source_pointer': f['source_pointer'],
                             'historical_witness': f, 'original_witness_sha256': sha(encode(f)),
                             'status': 'SOURCE_SCOPE_REPLAYED_WITH_DURABLE_PUBLICATION'}
                            for f in old_structure['fields']],
                 'historical_superseded_fields': old_structure['historical_superseded_fields']}
    files = {}
    def save(name, raw):
        path = HOME + '/' + name
        write_once(root / path, raw)
        files[path] = sha(raw)
        return path
    cp = save('chunks.jsonl', b''.join(encode(c) + b'\n' for c in chunks))
    op = save('unit-outcomes.json', encode(outcomes))
    save('m0-m1-prepared-inputs.jsonl', b''.join(encode(p) + b'\n' for p in prepared))
    save('UNIT_ID_RECONCILIATION.json', encode(units))
    save('CHUNK_ID_RECONCILIATION.json', encode(chunkmap))
    save('M1_M2_VALIDATIONS.json', encode({'units': validation, 'C01_configurations': comparisons}))
    save('COVERAGE.json', encode(summary))
    sp = save('STRUCTURE_EVIDENCE.json', encode(structure))
    components = remap_components(old['components'])
    for name in ['src/rag_hub/durable_unified_selection.py', 'tools/hardening/build_catalog.py']:
        components[name] = sha((root / name).read_bytes())
    manifest = {**old, 'files': files, 'components': components,
        'configurations': configs, 'default_configuration_id': config_map[old['default_configuration_id']],
        'upstream_files': corpus.binding_manifest()['files'], 'chunks_path': cp, 'units_path': op,
        'summary': summary, 'structural_witness_index': sp,
        'explicit_unified_selection': 'config/unified-durable-selection-v1.json',
        'predecessor': {'path': OLD, 'sha256': sha((root / OLD).read_bytes())}}
    write_once(root / HOME / 'manifest.json', encode(manifest))
    selection = {'schema': 'chunk-catalog-selection-1.0', 'manifest_path': HOME + '/manifest.json',
                 'manifest_sha256': sha(encode(manifest)),
                 'reader': 'rag_hub.qualified_chunk_catalog.QualifiedChunkCatalog'}
    write_once(root / SELECTOR, encode(selection))
    catalog = QualifiedChunkCatalog(root, corpus, selector=SELECTOR)
    catalog.check()
    return summary['durable_packaging']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    os.umask(0o077)
    print(json.dumps(build(args.root.resolve())))


if __name__ == '__main__':
    main()
