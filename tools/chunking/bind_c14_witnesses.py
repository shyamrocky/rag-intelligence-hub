"""Bind historical boundary witnesses to rebased handles without editing chunks.

The QA parent remains the authority. This deterministic envelope adds inspection
traceability, not a source interpretation or eligibility decision.
"""
import argparse
import json
from pathlib import Path

from rag_hub.chunk_preparation import write_once
from rag_hub.unified_models import encode, sha

BASE = 'data/chunking/m3-c14-scope-v1/manifest.json'
DEST = 'data/chunking/m3-c14-scope-v2'
SELECTOR = 'config/retrieval-chunks-m3-c14-scope-v2.json'


def consolidate(root, destination):
    original = json.loads((root / BASE).read_bytes())
    for p, h in original['files'].items():
        if sha((root / p).read_bytes()) != h:
            raise ValueError('changed_c14_rebuild_payload')
    prepared_path = next(p for p in original['files'] if p.endswith('/m0-m1-prepared-inputs.jsonl'))
    prepared = [json.loads(s) for s in (root / prepared_path).read_text().splitlines()]
    by_native = {p['unit_id'].split(':', 2)[2]: p for p in prepared}
    fields, historical, dependencies = [], [], {}
    for mp in ['data/chunking/m3-remediation-v1/manifest.json',
               'data/chunking/m3-qualified-v2/manifest.json']:
        prior = json.loads((root / mp).read_bytes())
        path = next(p for p in prior['files'] if p.endswith('/STRUCTURE_EVIDENCE.json'))
        raw = (root / path).read_bytes()
        if sha(raw) != prior['files'][path]:
            raise ValueError('changed_historical_structure_witness')
        dependencies[path] = sha(raw)
        for witness in json.loads(raw)['fields']:
            old_uid = witness['unit_id']
            native = old_uid.split(':', 2)[2]
            current = by_native.get(native)
            entry = {'original_unit_id': old_uid, 'original_witness': witness,
                     'binding': {'path': path, 'sha256': sha(raw)}}
            if current is None:
                # Former mixed C14 witnesses are history, not aliases to the four replacements.
                entry['status'] = 'SUPERSEDED_MIXED_SCOPE_NOT_ACTIVE_MEMBERSHIP'
                historical.append(entry)
                continue
            pointer = witness.get('source_pointer', witness.get('pointer'))
            candidates = [s for s in current['indexable_source_content'] if s['source_pointer'] == pointer]
            if candidates and sha(candidates[0]['text'].encode()) != witness['source_text_sha256']:
                raise ValueError('rebound_structure_source_text_changed')
            entry.update(unit_id=current['unit_id'], source_pointer=pointer,
                         status='UNCHANGED_SOURCE_WITNESS_EXPLICIT_HANDLE_REBASE')
            fields.append(entry)
    c14 = json.loads((root / 'data/normalized/pdf/c14-scope-correction-v1/C14.json').read_bytes())
    new = set(c14['scope_correction']['replacement_unit_ids'])
    for u in c14['units']:
        if u['id'] not in new:
            continue
        current = by_native[u['id']]
        fields.append({'unit_id': current['unit_id'],
            'source_pointer': '/consumer/llm_context/source_content/0',
            'source_text_sha256': sha(u['display_text'].encode()),
            'status': 'SOURCE_SUPPORTED_QA_PUBLISHED_SCOPE',
            'structure': u['structure'], 'source_members': u['source_members'],
            'required_context': u['required_context'],
            'publication_identity': current['publication_identity']})
    payload = {'schema': 'm3-rebound-boundary-witness-index-1.0',
               'authority': 'SOURCE_BOUND_MACHINE_EVIDENCE_NOT_ADMISSION_OR_HUMAN_APPROVAL',
               'fields': fields, 'historical_superseded_fields': historical,
               'identity_rule': 'Original witness handles are historical references, never aliases or permissions.'}
    path = destination / 'STRUCTURE_EVIDENCE.json'
    write_once(path, encode(payload))
    manifest = dict(original)
    manifest['files'] = dict(original['files']) | {str(path.relative_to(root)): sha(encode(payload))}
    manifest['components'] = dict(original['components']) | dependencies | {
        'tools/chunking/bind_c14_witnesses.py': sha((root / 'tools/chunking/bind_c14_witnesses.py').read_bytes())}
    manifest['predecessor'] = {'path': BASE, 'sha256': sha((root / BASE).read_bytes())}
    manifest['original_lineage_predecessor'] = original['predecessor']
    manifest['structural_witness_index'] = str(path.relative_to(root))
    write_once(destination / 'manifest.json', encode(manifest))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=DEST)
    parser.add_argument('--selector')
    args = parser.parse_args()
    root = Path.cwd()
    result = consolidate(root, root / args.output)
    if args.selector:
        write_once(root / args.selector, encode({'schema': 'chunk-catalog-selection-1.0',
            'manifest_path': str(Path(args.output) / 'manifest.json'),
            'manifest_sha256': sha(encode(result)),
            'reader': 'rag_hub.qualified_chunk_catalog.QualifiedChunkCatalog'}))
    print(json.dumps({'chunks_unchanged': result['summary']['chunks'],
                      'manifest_sha256': sha(encode(result)),
                      'structural_witness_index': result['structural_witness_index']}))


if __name__ == '__main__':
    main()
