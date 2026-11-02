"""Rebuild C14-dependent M0–M3 lineage from an explicitly verified QA successor.

No historical rows are edited; PDF rows are regenerated through accepted
chunkers. Unchanged HTML/Markdown rows must remain byte-equivalent.
"""
import argparse
import copy
import json
import resource
import socket
import time
from collections import Counter
from pathlib import Path

from rag_hub.c14_chunking import chunk_c14
from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.chunk_inputs import ChunkInput
from rag_hub.chunk_preparation import write_once
from rag_hub.chunk_remediation import BoundedRemediator
from rag_hub.corpus_chunking import CorpusChunker
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.qualified_chunk_catalog import QUALIFIED_CONFIG, QualifiedChunkCatalog
from rag_hub.qualified_chunking import QualifiedChunker
from rag_hub.qualified_preparation import QualifiedPreparation
from rag_hub.retrieval_chunks import from_proposal
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

WORK = 'workspace/rag-implementation/v1/m3-c14-correction-v1'
PRIOR = 'data/chunking/m3-qualified-v2/manifest.json'
DATA = 'data/chunking/m3-c14-scope-v1'
SELECTOR = 'config/retrieval-chunks-m3-c14-scope-v1.json'
COMPONENTS = ['src/rag_hub/c14_scope_correction.py', 'src/rag_hub/c14_unified_selection.py',
              'src/rag_hub/c14_chunking.py', 'tools/chunking/build_c14_successor.py',
              'config/unified-c14-scope-selection-v1.json', WORK + '/FROZEN_SOURCE_WITNESSES.json']


def key(p):
    return p['source_pointer'], p['display_start'], p['display_end']


def build(root, output):
    started = time.perf_counter()
    previous = load_verified_corpus(root)
    old = QualifiedChunkCatalog(root, previous)
    current = load_c14_verified_corpus(root)
    prep = QualifiedPreparation(root, current)
    tokenizer = PinnedBgeTokenizer(root)
    base = CorpusChunker(prep.original, tokenizer)
    bounded = BoundedRemediator(prep.original, tokenizer)
    qualified = QualifiedChunker(prep, tokenizer)
    before_units = {m['native_unit_id']: m for m in previous.catalog.list_units()}
    metadata = {m['unit_id']: m for m in current.catalog.list_units()}
    configs = copy.deepcopy(old.manifest['configurations'])
    components = old.manifest['components'] | {p: sha((root / p).read_bytes()) for p in COMPONENTS}
    before_chunks = [json.loads(l) for l in (root / old.manifest['chunks_path']).read_text().splitlines()]
    old_outcomes = {o['unit_id']: o for o in old.outcomes()}
    old_rows = {}
    for c in before_chunks:
        old_rows.setdefault(c['unit_id'], []).append(c)
    chunks, outcomes, inputs, mappings, validation, comparisons = [], [], [], [], [], []
    for number, (uid, meta) in enumerate(sorted(metadata.items()), 1):
        if number == 1 or number % 50 == 0:
            print(f'Preparing/replaying unit {number}/{len(metadata)}: {meta["document_id"]}', flush=True)
        record = ChunkInput.model_validate(prep.original.prepare(uid))
        inputs.append(record.model_dump(mode='json'))
        prior_meta = before_units.get(meta['native_unit_id'])
        if meta['format'] != 'pdf':
            if prior_meta != meta:
                raise ValueError('unrelated_unified_unit_changed')
            # Revalidate ordinary/protected source representations via the current gateway.
            prep.original.validate(record)
            chunks.extend(copy.deepcopy(old_rows.get(uid, [])))
            outcomes.append(copy.deepcopy(old_outcomes[uid]))
            continue
        p = prep.prepare(uid)
        if prior_meta:
            old_uid = prior_meta['unit_id']
            old_record = old.preparation.prepare(old_uid)
            # The selected publication changes bindings, not these native source/context scopes.
            for field in ['indexable_source_content', 'required_context', 'qa_observations',
                          'qualification', 'memberships', 'citation_locators']:
                if encode(getattr(record, field)) != encode(getattr(old_record, field)):
                    raise ValueError('unrelated_pdf_preparation_scope_changed:' + field)
            generated = base.chunk(record, total_tokens=384)
            base_pieces = {key(c): c for c in generated['chunks']}
            bounded_fields, qualified_fields = {}, {}
            outcome = copy.deepcopy(old_outcomes[old_uid])
            outcome['unit_id'] = uid
            result_rows = []
            for original in old_rows.get(old_uid, []):
                pointer = original['source']['pointer']
                conf = configs[original['configuration_id']]
                schema = conf['schema']
                if schema == 'm3-configuration-1.0':
                    proposals = base_pieces
                elif schema == 'm3-bounded-remediation-config-1.0':
                    if pointer not in bounded_fields:
                        bounded_fields[pointer] = {key(c): c for c in bounded.remediate(record, pointer)['chunks']}
                    proposals = bounded_fields[pointer]
                elif schema == QUALIFIED_CONFIG:
                    if pointer not in qualified_fields:
                        qualified_fields[pointer] = {key(c): c for c in qualified.chunk(p, pointer)['chunks']}
                    proposals = qualified_fields[pointer]
                else:
                    raise ValueError('unknown_predecessor_chunker')
                proposal = proposals.get((pointer, original['source']['start'], original['source']['end']))
                if proposal is None:
                    raise ValueError('predecessor_source_boundary_not_reproduced')
                # Replay old row before any identity rebase; do not hand-patch its source fields.
                exposed = dict(proposal, unit_id=old_uid)
                replay = from_proposal(exposed, prior_meta, original['configuration_id']).model_dump(mode='json')
                if replay != original:
                    fields = [k for k in replay if replay[k] != original[k]]
                    raise ValueError('predecessor_chunk_replay_disagreement:' + ','.join(fields))
                cid = original['configuration_id']
                if schema == QUALIFIED_CONFIG:
                    conf = copy.deepcopy(conf)
                    conf['authorized_search_fields'] = [[uid, pointer]]
                    cid = 'chunk-config:' + sha(encode(conf))
                    configs[cid] = conf
                rebuilt = from_proposal(proposal, meta, cid).model_dump(mode='json')
                result_rows.append(rebuilt)
                mappings.append({'old_chunk_id': original['chunk_id'], 'new_chunk_id': rebuilt['chunk_id'],
                    'reason': 'immutable PDF publication identity rebase; exact source/chunk configuration replayed'})
            chunks.extend(result_rows)
            outcome['chunk_ids'] = [c['chunk_id'] for c in result_rows]
            outcomes.append(outcome)
            validation.append({'unit_id': uid, 'previous_unit_id': old_uid,
                'native_scope_unchanged': True, 'preparation_record_id': record.record_id,
                'source_fields': len(record.indexable_source_content), 'chunks_rebuilt': len(result_rows),
                'all_previous_boundaries_tokens_and_lineage_replayed': True})
            if meta['document_id'] == 'C01':
                for budget in [256, 384]:
                    result = base.chunk(record, total_tokens=budget)
                    comparisons.append({'unit_id': uid, 'budget': budget,
                        'chunks': len(result['chunks']), 'unresolved': len(result['unresolved']),
                        'token_counts': [c['token_count'] for c in result['chunks']],
                        'source_results': result['source_results']})
            continue
        # Only the four newly published C14 parents are new native scopes.
        result = chunk_c14(prep, p, tokenizer)
        if result['unresolved']:
            raise ValueError('new_c14_scope_cannot_be_fully_partitioned')
        added = []
        for proposal in result['chunks']:
            conf = {'schema': 'm3-c14-source-scope-config-1.0',
                'total_tokens': proposal['budget_limit'], 'default_total_tokens': 384,
                'maximum_selective_exception': 512, 'tokenizer': tokenizer.metadata(),
                'overlap': 0, 'complete_parent_required': True,
                'source_and_QA_separate': True, 'components': components}
            cid = 'chunk-config:' + sha(encode(conf))
            configs[cid] = conf
            added.append(from_proposal(proposal, meta, cid).model_dump(mode='json'))
        coverage = [{'source_pointer': s['source_pointer'], 'content_type': s['content_type'],
                     'source_characters': len(s['text']), 'chunked_characters': len(s['text']),
                     'context_only_characters': 0, 'unresolved_characters': 0}
                    for s in p['search_sources']]
        outcome = {'unit_id': uid, 'document_id': 'C14', 'format': 'pdf',
                   'chunk_ids': [c['chunk_id'] for c in added], 'source_coverage': coverage,
                   'source_field_count': len(coverage), 'protected_projection_count': 0,
                   'non_indexable': [], 'unresolved': [], 'status': 'CHUNKED'}
        chunks.extend(added)
        outcomes.append(outcome)
        validation.append({'unit_id': uid, 'new_native_scope': True,
            'preparation_record_id': record.record_id,
            'tokens': [c['token_count'] for c in added], 'chunks': len(added),
            'required_heading_characters': sum(len(h['text']) for h in p['headings'])})
        for budget in [256, 384]:
            alt = chunk_c14(prep, p, tokenizer, total_tokens=budget)
            comparisons.append({'unit_id': uid, 'document_id': 'C14', 'budget': budget,
                'chunks': len(alt['chunks']), 'unresolved': alt['unresolved'],
                'token_counts': [c['token_count'] for c in alt['chunks']]})
    # Preserve old unit ordering for unaffected content, new parents append deterministically.
    order = {uid: i for i, uid in enumerate(sorted(metadata))}
    chunks.sort(key=lambda c: (order[c['unit_id']], c['source']['pointer'], c['source']['start']))
    outcomes.sort(key=lambda o: order[o['unit_id']])
    for o in outcomes:
        o['chunk_ids'] = [c['chunk_id'] for c in chunks if c['unit_id'] == o['unit_id']]
    if len({c['chunk_id'] for c in chunks}) != len(chunks):
        raise ValueError('duplicate_rebuilt_chunk')
    totals = ['source_characters', 'chunked_characters', 'unresolved_characters', 'context_only_characters']
    by_document = {did: {'units': sum(o['document_id'] == did for o in outcomes),
        'chunks': sum(c['document_id'] == did for c in chunks),
        'unique_sections': old.manifest['summary']['by_document'][did]['unique_sections'],
        **{k: sum(s.get(k, 0) for o in outcomes if o['document_id'] == did
                   for s in o['source_coverage']) for k in totals}}
        for did in old.manifest['documents']}
    summary = {'schema': 'm3-c14-scope-coverage-1.0', 'authority': 'INSPECTION_ONLY_NOT_QA',
        'units': len(outcomes), 'chunks': len(chunks), 'units_with_chunks': sum(bool(o['chunk_ids']) for o in outcomes),
        'by_document': by_document, 'unit_dispositions': dict(Counter(o['status'] for o in outcomes)),
        'counts_unchanged': current.catalog.get_corpus_summary(),
        'unchanged_non_pdf_chunk_records': sum(c['format'] != 'pdf' for c in chunks),
        'rebased_pdf_chunk_records': len(mappings),
        'new_c14_chunks': sum(v.get('chunks', 0) for v in validation if v.get('new_native_scope')),
        'denominator_note': 'Per-unit authorized source display; shared source not deduplicated. '
                            'Heading source characters moved to required context are accounted separately; '
                            'three obsolete synthetic inter-section joiners are not source characters.'}
    files = {}

    def save(name, data):
        path = output / name
        write_once(path, data)
        files[str(path.relative_to(root))] = sha(data)
        return str(path.relative_to(root))

    cp = save('chunks.jsonl', b''.join(encode(c) + b'\n' for c in chunks))
    op = save('unit-outcomes.json', encode(outcomes))
    save('m0-m1-prepared-inputs.jsonl', b''.join(encode(p) + b'\n' for p in inputs))
    save('M1_M2_VALIDATIONS.json', encode({'units': validation, 'accepted_configurations': comparisons}))
    save('CHUNK_ID_RECONCILIATION.json', encode(mappings))
    save('COVERAGE.json', encode(summary))
    manifest = {**old.manifest, 'components': components, 'files': files,
        'upstream_files': current.binding_manifest()['files'], 'chunks_path': cp, 'units_path': op,
        'configurations': configs, 'summary': summary,
        'predecessor': {'path': PRIOR, 'sha256': sha((root / PRIOR).read_bytes())},
        'explicit_unified_selection': 'config/unified-c14-scope-selection-v1.json'}
    old.check()
    current.catalog.get_corpus_summary()
    write_once(output / 'manifest.json', encode(manifest))
    runtime = {'seconds': time.perf_counter() - started,
               'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    return manifest, runtime


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', default=DATA)
    p.add_argument('--selector')
    args = p.parse_args()
    root = Path.cwd()
    original = socket.socket.connect

    def offline(*_args, **_kwargs):
        raise RuntimeError('c14_reconciliation_offline_only')

    socket.socket.connect = offline
    try:
        manifest, runtime = build(root, root / args.output)
        if args.selector:
            write_once(root / args.selector, encode({'schema': 'chunk-catalog-selection-1.0',
                'manifest_path': str(Path(args.output) / 'manifest.json'),
                'manifest_sha256': sha(encode(manifest)),
                'reader': 'rag_hub.qualified_chunk_catalog.QualifiedChunkCatalog'}))
        print(json.dumps({'summary': manifest['summary'], 'runtime': runtime,
                          'manifest_sha256': sha(encode(manifest))}), flush=True)
    finally:
        socket.socket.connect = original


if __name__ == '__main__':
    main()
