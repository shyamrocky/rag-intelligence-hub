"""Explicit durable composition; native QA remains the only source authority.

The original accepted/default compositions stay unchanged. This source is
fingerprinted by downstream catalogs and watched by its snapshot lease.
"""

import json
from pathlib import Path

from rag_hub.c14_scope_correction import verify_corrected_evidence
from rag_hub.pdf_corpus import load_corpus
from rag_hub.unified_adapters import html_adapter, markdown_adapter, pdf_adapter
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_consumption import VerifiedCorpus
from rag_hub.unified_models import encode, sha

SELECTOR = 'config/unified-durable-selection-v1.json'
SELECTOR_SHA = 'd9a2bc8452df9da83dd4d2ae7511bb2393203821e2c8218e51e962a090aad681'
SELECTIONS = {'html': 'config/html-c10-admission-publication.json',
              'markdown': 'config/markdown-admission-publication-v1-1.json',
              'pdf': 'config/pdf-durable-admission-publication-v1.json'}


def load_durable_corpus(root, *, selector=SELECTOR):
    """Construct through exact explicit native publications; no latest/old fallback."""
    if str(selector) != SELECTOR:
        raise ValueError('unselected_durable_publication')
    bound = BoundFiles(root)
    if Path(__file__).resolve() != bound.root / 'src/rag_hub/durable_unified_selection.py':
        raise ValueError('durable_composition_import_origin_changed')
    selected = json.loads(bound.bind(SELECTOR, SELECTOR_SHA))
    descriptor = json.loads(bound.bind(selected['descriptor_path'], selected['descriptor_sha256']))
    if (descriptor['schema'] != 'durable-unified-bindings-1.0'
            or descriptor['authority'] != 'NATIVE_PUBLICATIONS_NOT_NEW_ADMISSION'
            or descriptor['selectors'] != SELECTIONS
            or any(Path(p).parts[0] in {'workspace', 'archive', 'releases'}
                   for p in descriptor['files'])):
        raise ValueError('invalid_durable_binding_contract')
    for name, expected in descriptor['files'].items():
        bound.bind(name, expected)
    selections = {fmt: bound.json(path) for fmt, path in SELECTIONS.items()}
    pdf = selections['pdf']
    manifest = bound.json(pdf['manifest_path'])
    release = bound.json(pdf['release_path'])
    policy = bound.json(release['qualification_policy_path'])
    witness = bound.json(policy['source_scope_witness'])
    document = load_corpus(bound.root)['documents']['C14']
    verify_corrected_evidence(document,
        bound.json(witness['predecessor_evidence']['path']), witness,
        bound.json(policy['recovery_evidence']['C14']))
    rows, units = {}, []
    index = bound.json(descriptor['html_markdown_index'])
    for adapter, fmt, inspection in [(html_adapter, 'html', index),
            (markdown_adapter, 'markdown', index),
            (pdf_adapter, 'pdf', bound.json(descriptor['pdf_issues']))]:
        rr, uu = adapter(bound.root, selections[fmt], bound, inspection)
        if set(rows) & set(rr):
            raise ValueError('duplicate_durable_canonical_section')
        rows.update(rr)
        units.extend(uu)
    freeze = bound.json(descriptor['source_freeze'])
    sources = json.loads(encode(freeze['frozen_source_identities']))
    for desc in manifest['publications']:
        source = bound.json(desc['path'])['qa']['pdf_text_support']['source']
        old = next(s for s in sources if s['source']['doc_id'] == source['doc_id'])
        if source['raw_sha256'] != old['source']['raw_sha256']:
            raise ValueError('durable_source_snapshot_changed')
        old['source'] = source
    own = 'src/rag_hub/durable_unified_selection.py'
    # Avoid a self-referential selector/source hash cycle, as in the accepted
    # C14 composition. Downstream manifests pin this exact loaded source too.
    bound.bind(own, sha(bound.path(own).read_bytes()))
    corpus = VerifiedCorpus(bound, rows, units, sources,
                            descriptor['expected_counts'], SELECTIONS)
    bound._json_cache.clear()
    return corpus
