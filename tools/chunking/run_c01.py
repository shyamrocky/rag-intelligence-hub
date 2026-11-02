"""Execute only the authorized offline M2 C01 pilot; never embed or publish QA."""

import argparse
import html
import importlib.metadata
import json
import resource
import socket
import sys
import time
from collections import Counter
from pathlib import Path

from rag_hub.chunk_preparation import ChunkPreparation, write_once
from rag_hub.chunk_profile import distribution, tokens
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.structure_chunking import StructureAwarePilot
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

COMPONENTS = [
    "src/rag_hub/m2_tokenizer.py", "src/rag_hub/structure_chunking.py",
    "src/rag_hub/chunk_inputs.py", "src/rag_hub/chunk_preparation.py",
    "src/rag_hub/chunk_profile.py", "tools/chunking/run_c01.py",
    "tools/chunking/pyproject.toml", "tools/chunking/uv.lock", "config/bge-tokenizer-v1.json",
]


def render_preview(records, results):
    h = html.escape
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>C01 M2 comparison</title>',
             ('<style>body{font:16px system-ui;margin:30px auto;max-width:1250px;padding:20px;'
             'color:#203039}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f7;'
             'padding:12px}details{border:1px solid #cbd6dd;padding:12px;margin:12px 0}'
             '.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}'
             '@media(max-width:850px){.pair{display:block}}</style>'),
             '<h1>C01 — M2 structure-aware chunking comparison</h1>',
             ('<p>Derived pilot candidates only. No embeddings, retrieval, QA publication or '
             'standalone evidence authorization. Counts include the BGE heading prefix and CLS/SEP. '
             'Original source text is shown literally. No model-decoded text is used.</p>')]
    for record in records:
        parts.append(f'<details><summary>{h(record.unit_id.split(":", 2)[-1])}</summary>')
        parts.append('<div class="pair">')
        for budget in [256, 384]:
            result = next(u for u in results[budget] if u['unit_id'] == record.unit_id)
            parts.append(f'<section><h2>{budget} total tokens</h2><p>{len(result["chunks"])} '
                         f'pieces; {len(result["unresolved"])} unresolved regions</p>')
            for chunk in result['chunks']:
                parts.append(f'<h3>{chunk["token_count"]} tokens · '
                             f'display [{chunk["display_start"]}:{chunk["display_end"]}]</h3>')
                parts.append(f'<p>{h(chunk["boundary_decision"])}</p>')
                if chunk['heading_prefix']:
                    parts.append('<b>Required heading prefix — context</b><pre>'
                                 + h(chunk['heading_prefix']) + '</pre>')
                parts.append('<b>Authorized source display slice</b><pre>'
                             + h(chunk['source_text']) + '</pre>')
                parts.append('<p>Lineage: ' + h(chunk['lineage']['precision']) + '</p>')
                if chunk['review_notes']:
                    parts.append('<p><b>Diagnostic limitations:</b> '
                                 + h(' '.join(chunk['review_notes'])) + '</p>')
                parts.append('<details><summary>Lineage / source references</summary><pre>'
                             + h(json.dumps(chunk['lineage'], ensure_ascii=False, indent=2))
                             + '</pre></details>')
            for unresolved in result['unresolved']:
                parts.append('<pre>UNRESOLVED: '
                             + h(json.dumps(unresolved, ensure_ascii=False, indent=2)) + '</pre>')
            parts.append('</section>')
        parts.append('</div>')
        for title, obj in [('Required context', record.required_context),
                           ('QA observations — separate from publisher content', record.qa_observations),
                           ('Mandatory qualifications', record.qualification),
                           ('Publication and membership', {'publication': record.publication_identity,
                            'memberships': record.memberships})]:
            parts.append(f'<details><summary>{h(title)}</summary><pre>'
                         + h(json.dumps(obj, ensure_ascii=False, indent=2)) + '</pre></details>')
        parts.append('</details>')
    parts.append('</html>')
    return '\n'.join(parts).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, default=Path('data/chunking/m2-c01-v3'))
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output if args.output.is_absolute() else root / args.output
    start = time.perf_counter()
    component_hashes = {p: sha((root / p).read_bytes()) for p in COMPONENTS}
    attempts = []

    def no_network(sock, address):
        attempts.append(str(address))
        raise RuntimeError('M2 offline replay attempted network access')

    original_connect = socket.socket.connect
    socket.socket.connect = no_network
    try:
        corpus = load_verified_corpus(root)
        loaded = time.perf_counter()
        preparation = ChunkPreparation(corpus)
        tokenizer = PinnedBgeTokenizer(root)
        records = preparation.prepare_document('C01')
        assert len(records) == 61
        reference = tokenizer.reference_tokenizer()
        assert all(tokenizer.encode(s.text).ids == reference.encode(s.text).ids
                   for r in records for s in r.indexable_source_content)
        pilot = StructureAwarePilot(preparation, tokenizer)
        results = {b: [pilot.chunk(r, total_tokens=b) for r in records] for b in [256, 384]}
        files = {}

        def save(name, raw):
            write_once(out / name, raw)
            files[name] = sha(raw)

        save('prepared-inputs.jsonl', b''.join(preparation.serialize(r) + b'\n' for r in records))
        token_profile = []
        for record in records:
            source = record.indexable_source_content[0]
            row = next(u for u in results[256] if u['unit_id'] == record.unit_id)
            token_profile.append({
                'unit_id': record.unit_id, 'content_type': source.content_type,
                'lexical_tokens_M1_method': tokens(source.text),
                'bge_source_tokens_without_specials': tokenizer.count(source.text, special=False),
                'bge_whole_unit_with_heading_and_specials': tokenizer.count(
                    (row['chunks'][0]['heading_prefix'] if row['chunks'] else '') + source.text),
                'heading_tokens': row['heading_prefix_tokens'],
                'unique_section_count': len({m['section_id'] for m in record.memberships}),
                'scope_limited': any(s['scope_limited_projection'] for s in record.section_bindings),
            })
        save('C01_BGE_TOKEN_PROFILE.json', encode({'units': token_profile,
             'whole_unit_tokens': distribution([
                 u['bge_whole_unit_with_heading_and_specials'] for u in token_profile]),
             'authority': 'INSPECTION_ONLY'}))
        comparison = {}
        review_cases = []
        original_chars = sum(len(s.text) for r in records for s in r.indexable_source_content)
        for budget, units in results.items():
            save(f'config-{budget}/unit-results.jsonl', b''.join(encode(u) + b'\n' for u in units))
            chunks = [c for u in units for c in u['chunks']]
            unresolved = [dict(u, unit_id=result['unit_id']) for result in units
                          for u in result['unresolved']]
            chunked_chars = sum(len(c['source_text']) for c in chunks)
            unresolved_chars = sum(u['display_end'] - u['display_start'] for u in unresolved)
            assert chunked_chars + unresolved_chars == original_chars
            bib = [c for c in chunks if c['content_type'] == 'bibliography']
            partial_parent = []
            for chunk in chunks:
                record = next(r for r in records if r.unit_id == chunk['unit_id'])
                source = record.indexable_source_content[0]
                partial = chunk['display_start'] > 0 or chunk['display_end'] < len(source.text)
                if chunk['lineage']['precision'].startswith('AUTHORIZED') and partial:
                    partial_parent.append(chunk['proposal_id'])
                    review_cases.append({'budget': budget, 'unit_id': record.unit_id,
                        'proposal_id': chunk['proposal_id'], 'kind': 'PARTIAL_DISPLAY_PARENT_LEVEL_RAW_LINEAGE',
                        'blocking_integrity_failure': False,
                        'explanation': 'Exact approved display slice and parent citation are retained; '
                                       'no new exact partial raw offset is claimed. Review before requiring '
                                       'finer M3 lineage.'})
                if chunk['unknown_token_offsets']:
                    review_cases.append({'budget': budget, 'unit_id': record.unit_id,
                        'proposal_id': chunk['proposal_id'], 'kind': 'BGE_UNKNOWN_TOKEN',
                        'blocking_integrity_failure': False,
                        'unknown_source_strings': [chunk['embedding_text'][x['embedding_start']:x['embedding_end']]
                                                  for x in chunk['unknown_token_offsets']],
                        'explanation': 'Original text preserved; tokenization has vocabulary limitations. '
                                       'This is not a publisher defect or a new QA HOLD decision.'})
            comparison[str(budget)] = {
                'units_accounted': len(units), 'chunk_count': len(chunks),
                'units_remaining_intact': sum(len(u['chunks']) == 1 and not u['unresolved'] for u in units),
                'units_split': sum(len(u['chunks']) > 1 for u in units),
                'unresolved_regions': len(unresolved), 'unresolved_characters': unresolved_chars,
                'authorized_source_display_characters': original_chars,
                'chunked_source_display_characters': chunked_chars,
                'accounted_display_characters': chunked_chars + unresolved_chars,
                'display_coverage_fraction': chunked_chars / original_chars,
                'overlap_source_characters': 0,
                'token_distribution_including_heading_and_specials': distribution([
                    c['token_count'] for c in chunks]),
                'body_token_distribution': distribution([c['body_token_count'] for c in chunks]),
                'heading_prefix_token_occurrences': sum(
                    tokenizer.count(c['heading_prefix'], special=False) for c in chunks),
                'special_token_occurrences': tokenizer.special_tokens * len(chunks),
                'boundary_decisions': dict(Counter(c['boundary_decision'] for c in chunks)),
                'lineage_precision': dict(Counter(c['lineage']['precision'] for c in chunks)),
                'partial_display_chunks_with_parent_level_raw_lineage': len(partial_parent),
                'bibliography_chunks': len(bib),
                'bibliography_entries': sum(len(c['reference_numbers']) for c in bib),
                'unknown_token_occurrences': sum(len(c['unknown_token_offsets']) for c in chunks),
                'unique_body_section_ids': len({sid for c in chunks for sid in c['lineage']['section_ids']}),
                'unique_required_membership_sections': len({m['section_id'] for u in units
                                                          for c in u['chunks'] for m in c['memberships']}),
                'unresolved': unresolved,
            }
        save('C01_CHUNKING_COMPARISON.json', encode({'schema': 'm2-comparison-1.0',
             'authority': 'INSPECTION_ONLY', 'configurations': comparison,
             'tokenizer': tokenizer.metadata(),
             'no_retrieval_quality_measured': True, 'no_eligibility_or_catalog_publication': True}))
        save('REVIEW_CASES.json', encode({'schema': 'm2-review-cases-1.0',
             'authority': 'INSPECTION_ONLY_NOT_QA', 'cases': review_cases}))
        save('C01_CHUNKING_REVIEW.html', render_preview(records, results))
        assert not any(p in sys.modules for p in ['torch', 'transformers', 'sentence_transformers'])
        assert not attempts
        assert component_hashes == {p: sha((root / p).read_bytes()) for p in COMPONENTS}
        manifest = {'schema': 'm2-c01-pilot-manifest-1.0',
            'authority': 'DERIVED_PILOT_NOT_ADMISSION_OR_RETRIEVAL_CATALOG',
            'components': component_hashes, 'files': files,
            'tokenizer': tokenizer.metadata(), 'upstream_snapshot': corpus.binding_manifest(),
            'M0_M1_predecessor': {'path': 'data/preparation/chunk-input-v1/C01/manifest.json',
                                'sha256': sha((root / 'data/preparation/chunk-input-v1/C01/manifest.json').read_bytes())},
            'note': 'Fresh gateway preparation includes current expiration warnings; M1 artifacts untouched.',
            'stop_boundary': 'M2 only; await owner review before M3'}
        write_once(out / 'manifest.json', encode(manifest))
        runtime = {'corpus_load_seconds': loaded - start, 'total_seconds': time.perf_counter() - start,
                   'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   'ru_maxrss_unit': 'bytes on macOS', 'network_connect_attempts': len(attempts),
                   'embedding_model_modules_loaded': [],
                   'packages': {p: importlib.metadata.version(p) for p in
                                ['tokenizers', 'langchain-text-splitters', 'langchain-core', 'pydantic', 'pymupdf']},
                   'manifest_sha256': sha(encode(manifest))}
        print(json.dumps({'comparison': comparison, 'runtime': runtime}, indent=2), flush=True)
    finally:
        socket.socket.connect = original_connect


if __name__ == '__main__':
    main()
