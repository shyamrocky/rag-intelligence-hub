"""Explicit C14 publication successor using unchanged unified adapters/contracts.

The accepted default snapshot/dashboard remain frozen. This composition reuses
native QA validation, membership checks and the existing evidence gateway.
"""
import json

from rag_hub.c14_scope_correction import verify_corrected_evidence
from rag_hub.pdf_corpus import load_corpus
from rag_hub.unified_adapters import html_adapter, markdown_adapter, pdf_adapter
from rag_hub.unified_bindings import FREEZE_SHA, INDEX, SELECTORS, accepted_bindings
from rag_hub.unified_consumption import VerifiedCorpus
from rag_hub.unified_models import encode

SELECTOR = 'config/unified-c14-scope-selection-v1.json'
SELECTOR_SHA256 = '382c87b298fd94034910128ae7ceda3ac8730287d1ec1e505fd632874baf3c5e'


def load_c14_verified_corpus(root):
    """Opt-in only. Historical handles never alias newly selected PDF units."""
    bound, freeze, selections = accepted_bindings(root)
    selected = json.loads(bound.bind(SELECTOR, SELECTOR_SHA256))
    if (selected['schema'] != 'unified-c14-explicit-selection-1.0'
            or selected['predecessor_freeze_sha256'] != FREEZE_SHA
            or selected['changed_qa_scope'] != ['C14']):
        raise ValueError('unbound_c14_unified_successor')
    for key in ['pdf_selector', 'pdf_issues', 'scope_witness']:
        ref = selected[key]
        bound.bind(ref['path'], ref['sha256'])
    pdf_selection = bound.json(selected['pdf_selector']['path'])
    manifest = json.loads(bound.bind(pdf_selection['manifest_path'], pdf_selection['expected_manifest_sha256']))
    release = json.loads(bound.bind(pdf_selection['release_path'], pdf_selection['expected_release_sha256']))
    for path, digest in release['files'].items():
        bound.bind(path, digest)
    admission = manifest['admission']
    bound.bind(admission['authorization_path'], admission['authorization_sha256'])
    policy = bound.json(release['qualification_policy_path'])
    for desc in manifest['publications']:
        bound.bind(desc['path'], desc['sha256'])
    witness = bound.json(selected['scope_witness']['path'])
    predecessor = bound.json(witness['predecessor_evidence']['path'])
    candidate = bound.json(policy['recovery_evidence']['C14'])
    verify_corrected_evidence(load_corpus(root)['documents']['C14'], predecessor, witness, candidate)
    # Reconcile the approved upstream scope, not just total counts.
    prior_manifest = bound.json(selections['pdf']['manifest_path'])
    for desc in manifest['publications']:
        doc = desc['path'].rsplit('/', 1)[1]
        old_desc = next(x for x in prior_manifest['publications'] if x['path'].endswith('/' + doc))
        before = bound.json(old_desc['path'])['qa']
        after = bound.json(desc['path'])['qa']
        if [(d['section_id'], d['status']) for d in before['quality_decisions']] != [
                (d['section_id'], d['status']) for d in after['quality_decisions']]:
            raise ValueError('c14_successor_changed_admission_membership')
        if doc != 'C14.json' and before['pdf_text_support'] != after['pdf_text_support']:
            raise ValueError('c14_successor_changed_unrelated_source_scope')
    selections['pdf'] = pdf_selection
    index = bound.json(INDEX)
    issues = bound.json(selected['pdf_issues']['path'])
    rows, units = {}, []
    for adapter, fmt, metadata in [(html_adapter, 'html', index),
                                   (markdown_adapter, 'markdown', index),
                                   (pdf_adapter, 'pdf', issues)]:
        rr, uu = adapter(bound.root, selections[fmt], bound, metadata)
        if set(rows) & set(rr):
            raise ValueError('c14_duplicate_canonical_identity')
        rows.update(rr)
        units.extend(uu)
    sources = json.loads(encode(freeze['frozen_source_identities']))
    for desc in manifest['publications']:
        source = bound.json(desc['path'])['qa']['pdf_text_support']['source']
        entry = next(s for s in sources if s['source']['doc_id'] == source['doc_id'])
        if source['raw_sha256'] != entry['source']['raw_sha256']:
            raise ValueError('c14_source_identity_changed')
        entry['source'] = source
    expected = dict(freeze['combined_counts'], units=selected['expected_units'])
    # Bind this opt-in composition too, preserving the ordinary lease behavior.
    from rag_hub.unified_models import sha

    path = 'src/rag_hub/c14_unified_selection.py'
    bound.bind(path, sha(bound.path(path).read_bytes()))
    corpus = VerifiedCorpus(bound, rows, units, sources, expected,
                            dict(SELECTORS, pdf=selected['pdf_selector']['path']))
    bound._json_cache.clear()
    return corpus
