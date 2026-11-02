"""C14-only source-backed scope overlay; shared QA remains the approval owner.

Original blocks, canonical classifications and historical decisions are immutable.
The source witness is exposed machine evidence, never a human review receipt.
"""
import copy

from rag_hub.pdf_corpus import encoded
from rag_hub.pdf_text_recovery import source_text, unit
from rag_hub.unified_models import sha

VERSION = "c14-source-scope-correction-1.0"
BIBLIOGRAPHIC_LIMIT = ("Bibliographic attribution only; citation text is not evidence "
                       "for the cited publication's unacquired contents.")
APPENDIX_LIMIT = ("Attributed appendix research narrative only. Referenced figures and their "
                  "plotted values are not interpreted or certified by this text qualification; "
                  "preserve source notation and reported-result attribution.")


def corrected_evidence(document, predecessor, witness):
    if (document['source']['doc_id'] != 'C14'
            or document['source'] != predecessor['source']
            or document['source']['raw_sha256'] != witness['source_sha256']):
        raise ValueError('c14_correction_wrong_source')
    old = next(u for u in predecessor['units'] if u['id'] == witness['predecessor_native_unit'])
    if old['unit_sha256'] != witness['predecessor_unit_sha256']:
        raise ValueError('c14_predecessor_scope_changed')
    blocks = {b['block_id']: b for b in document['blocks']}
    parts = witness['parts']
    if [p['label'] for p in parts] != ['References', 'A', 'B', 'C']:
        raise ValueError('c14_unexpected_scope_parts')
    accounted = [m for p in parts for m in p['members']]
    accounted += [next(m for m in old['source_members'] if m['block_id'] == p['heading'])
                  for p in parts[1:]]
    key = lambda m: (m['block_id'], m['start'], m['end'])
    if sorted(accounted, key=key) != sorted(old['source_members'], key=key):
        raise ValueError('c14_missing_duplicate_or_foreign_source_interval')
    if old['required_context'][0]['source_span']['block_id'] != parts[0]['heading']:
        raise ValueError('c14_wrong_references_heading')
    result = copy.deepcopy(predecessor)
    replacements = []
    for p in parts:
        label, members = p['label'], p['members']
        h = blocks[p['heading']]
        if label == 'References':
            if h['content'] != 'References':
                raise ValueError('c14_invalid_bibliography_heading')
        elif not h['content'].startswith(label + '\n'):
            raise ValueError('c14_invalid_appendix_heading')
        text = source_text(members, blocks)
        structure = {'paragraphs': [{'source_member': m,
                      'boundary': 'original source fragment; section assembly is not an independent paragraph certification'}
                     for m in members],
                     'scope': 'bibliographic_attribution' if label == 'References' else 'substantive_appendix',
                     'heading_block_id': p['heading'], 'section_label': label,
                     'source_witness_sha256': sha(encoded(witness))}
        if label == 'References':
            entries = witness['reference_entries']
            pos = 0
            for i, e in enumerate(entries, 1):
                if (e['reference_index'] != i or e['start'] != pos
                        or not pos < e['end'] <= len(text)):
                    raise ValueError('c14_incomplete_reference_partition')
                pos = e['end']
            if pos != len(text):
                raise ValueError('c14_unaccounted_reference_suffix')
            structure['reference_entries'] = entries
            structure['reference_boundary_basis'] = witness['reference_boundary_basis']
        u = unit(document, members, 'bibliography' if label == 'References' else 'section_text',
                 'ILLUSTRATIVE', headings=[p['heading']],
                 limitations=[BIBLIOGRAPHIC_LIMIT if label == 'References' else APPENDIX_LIMIT],
                 structure=structure)
        replacements.append(u)
    result['units'] = [u for u in result['units'] if u['id'] != old['id']] + replacements
    # Decisions are not written here. This is source-bound proposed evidence.
    for a in result['section_accounting']:
        if old['id'] in a['unit_ids']:
            a['unit_ids'] = [uid for uid in a['unit_ids'] if uid != old['id']] + [
                u['id'] for u in replacements if a['section_id'] in u['required_section_ids']]
            if not a['unit_ids']:
                raise ValueError('c14_admitted_section_without_proposed_parent')
            a['reason'] = 'C14 source-supported scope correction; complete qualified parent required'
    result['version'] = VERSION
    result['scope_correction'] = {
        'predecessor_unit_id': old['id'], 'predecessor_unit_sha256': old['unit_sha256'],
        'source_witness_sha256': sha(encoded(witness)),
        'replacement_unit_ids': [u['id'] for u in replacements],
        'canonical_extraction_unchanged': True,
        'removed_synthetic_boundary_joiners': 3,
        'headings_preserved_as_required_source_context': [p['heading'] for p in parts],
        'human_source_approval_asserted': False}
    return result


def verify_corrected_evidence(document, predecessor, witness, candidate):
    if encoded(corrected_evidence(document, predecessor, witness)) != encoded(candidate):
        raise ValueError('c14_altered_scope_or_qualification')
    return True
