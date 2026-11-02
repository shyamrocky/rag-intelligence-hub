"""C14-only scope constraints, then actual publication/gateway/catalog integration."""
import copy
import json
from itertools import pairwise
from pathlib import Path

import pytest

from rag_hub.c14_scope_correction import (
    APPENDIX_LIMIT,
    BIBLIOGRAPHIC_LIMIT,
    corrected_evidence,
    verify_corrected_evidence,
)
from rag_hub.pdf_corpus import load_corpus

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'workspace/rag-implementation/v1/m3-c14-correction-v1'


@pytest.fixture(scope='module')
def scope():
    document = load_corpus(ROOT)['documents']['C14']
    prior = json.loads((ROOT / 'data/normalized/pdf/residual-recovery-v1/C14.json').read_bytes())
    witness = json.loads((WORK / 'FROZEN_SOURCE_WITNESSES.json').read_bytes())
    after = corrected_evidence(document, prior, witness)
    return document, prior, witness, after


def test_exact_unchanged_admissions_and_canonical_source(scope):
    doc, prior, _, after = scope
    assert after['source'] == prior['source'] == doc['source']
    assert [(s['section_id'], s['disposition']) for s in prior['section_accounting']] == [
        (s['section_id'], s['disposition']) for s in after['section_accounting']]
    assert len(after['units']) == len(prior['units']) + 3 == 73
    old = {u['id']: u for u in prior['units']}
    new = {u['id']: u for u in after['units']}
    retained = old.keys() & new.keys()
    assert len(retained) == 69 and all(old[k] == new[k] for k in retained)


@pytest.mark.parametrize('label', ['References', 'A', 'B', 'C'])
def test_correct_scope_complete_source_and_heading(scope, label):
    doc, _, witness, after = scope
    part = next(p for p in witness['parts'] if p['label'] == label)
    u = next(u for u in after['units'] if (u.get('structure') or {}).get('section_label') == label)
    assert u['source_members'] == part['members']
    assert u['required_context'][0]['source_span']['block_id'] == part['heading']
    assert u['known_limitations'] == [BIBLIOGRAPHIC_LIMIT if label == 'References' else APPENDIX_LIMIT]
    assert u['reference_classification'] == 'ILLUSTRATIVE'
    assert all('b00400' not in m['block_id'] for m in u['source_members'])
    assert len(u['required_section_ids']) == len(part['members']) + 1
    assert verify_corrected_evidence(doc, scope[1], witness, after)


def test_bibliography_boundary_map_complete_and_hanging_indentation(scope):
    _, _, witness, after = scope
    refs = next(u for u in after['units'] if (u.get('structure') or {}).get('section_label') == 'References')
    entries = refs['structure']['reference_entries']
    assert len(entries) == 47 and entries[0]['start'] == 0 and entries[-1]['end'] == 10619
    assert all(a['end'] == b['start'] for a, b in pairwise(entries))
    starts = {o['display_start'] for o in witness['reference_observations'] if o['entry_start']}
    assert starts == {e['start'] for e in entries}
    assert refs['text'] == ''.join(refs['text'][e['start']:e['end']] for e in entries)


def test_source_notation_and_visual_restrictions(scope):
    u = next(u for u in scope[3]['units'] if (u.get('structure') or {}).get('section_label') == 'C')
    assert 'k −1' in u['text'] and 'Figure 14' in u['text']
    assert 'plotted values are not interpreted' in u['known_limitations'][0]
    assert 'unacquired' not in ' '.join(u['known_limitations'])
    assert u['structure']['scope'] == 'substantive_appendix'


@pytest.mark.parametrize('tamper', ['text', 'qualification', 'heading', 'membership', 'extra_unit'])
def test_altered_correction_fail_closed(scope, tamper):
    doc, prior, witness, after = scope
    candidate = copy.deepcopy(after)
    u = candidate['units'][-1]
    if tamper == 'text':
        u['text'] += ' invented'
    elif tamper == 'qualification':
        u['known_limitations'] = []
    elif tamper == 'heading':
        u['required_context'] = []
    elif tamper == 'membership':
        u['source_members'] = u['source_members'][:-1]
    else:
        candidate['units'].append(copy.deepcopy(u))
    with pytest.raises(ValueError, match='altered_scope'):
        verify_corrected_evidence(doc, prior, witness, candidate)


def test_missing_and_duplicate_witnesses_rejected(scope):
    doc, prior, witness, _ = scope
    for duplicate in (False, True):
        w = copy.deepcopy(witness)
        if duplicate:
            w['parts'][1]['members'].append(w['parts'][1]['members'][0])
        else:
            w['parts'][1]['members'].pop()
        with pytest.raises(ValueError, match='source_interval'):
            corrected_evidence(doc, prior, w)


@pytest.fixture(scope='module')
def integrated():
    from rag_hub.c14_unified_selection import load_c14_verified_corpus
    from rag_hub.m2_tokenizer import PinnedBgeTokenizer
    from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

    corpus = load_c14_verified_corpus(ROOT)
    reader = QualifiedChunkCatalog(ROOT, corpus,
                                  selector='config/retrieval-chunks-m3-c14-scope-v2.json')
    return corpus, reader, PinnedBgeTokenizer(ROOT)


def rows(reader):
    return reader.list_chunks(limit=1000)['items']


def test_all_counts_admissions_and_memberships_reconcile(integrated):
    corpus, catalog, _ = integrated
    summary = corpus.catalog.get_corpus_summary()
    assert {k: summary[k] for k in ['documents', 'sections', 'admitted', 'excluded', 'HOLD', 'units', 'membership_edges']} == {
        'documents': 16, 'sections': 3040, 'admitted': 2572, 'excluded': 110,
        'HOLD': 358, 'units': 553, 'membership_edges': 3727}
    assert len(catalog.outcomes()) == 553 and all(o['chunk_ids'] for o in catalog.outcomes())
    assert all(not o['unresolved'] for o in catalog.outcomes())


def new_scopes(corpus):
    ids = json.loads((ROOT / 'data/normalized/pdf/c14-scope-correction-v1/C14.json').read_bytes())[
        'scope_correction']['replacement_unit_ids']
    return [m for m in corpus.catalog.list_units('C14') if m['native_unit_id'] in ids]


@pytest.mark.parametrize('label', ['References', 'A', 'B', 'C'])
def test_new_scope_authorized_parent_exact_chunks_and_context(integrated, label):
    corpus, reader, tokenizer = integrated
    matches = []
    for m in new_scopes(corpus):
        value = corpus.evidence.get_verified_unit(m['unit_id'])
        if value['consumer']['llm_context']['source_content'][0]['structure']['section_label'] == label:
            matches.append(value)
    assert len(matches) == 1
    value = matches[0]
    unit_rows = reader.list_chunks(unit_id=value['unit_id'])['items']
    assert ''.join(reader.open_chunk(c['chunk_id'])['source_slice'] for c in unit_rows) == value[
        'consumer']['llm_context']['source_content'][0]['text']
    for row in unit_rows:
        view = reader.open_chunk(row['chunk_id'])
        assert reader.validate_view(view)
        assert corpus.evidence.validate(view['verified_parent'])
        heading = '\n'.join(h['text'] for h in view['heading_context']) + '\n\n'
        assert tokenizer.count(heading + view['source_slice']) == row['token_count']
        assert row['token_count'] <= reader.manifest['configurations'][row['configuration_id']]['total_tokens'] <= 512
        assert row['lineage']['precision'] == 'HASH_VERIFIED_DISPLAY_TO_ORIGINAL_SOURCE_SLICES'
        assert row['reference_numbers'] == []
    assert all(m['role'] == 'supporting_heading' for m in value['memberships']
               if m['section_id'].split(':')[-2] in {'b00266', 'b00368', 'b00383', 'b00386'})


@pytest.mark.parametrize('remove', ['qualification', 'required_context', 'qa_observations'])
def test_warning_context_stripping_rejected(integrated, remove):
    corpus, reader, _ = integrated
    uid = new_scopes(corpus)[1]['unit_id']
    value = corpus.evidence.get_verified_unit(uid)
    value['consumer']['llm_context'].pop(remove)
    with pytest.raises(ValueError, match='stripped'):
        corpus.evidence.validate(value)
    cid = reader.get_unit_chunks(uid)[0]
    view = reader.open_chunk(cid)
    view['verified_parent']['consumer']['llm_context'].pop(remove)
    with pytest.raises(ValueError, match='stripped'):
        reader.validate_view(view)


def test_non_pdf_rows_and_qa_decisions_unchanged(integrated):
    _, reader, _ = integrated
    prior = json.loads((ROOT / 'data/chunking/m3-qualified-v2/manifest.json').read_bytes())
    old = [json.loads(s) for s in (ROOT / prior['chunks_path']).read_text().splitlines()]
    old = {c['chunk_id']: c for c in old if c['format'] != 'pdf'}
    actual = {c['chunk_id']: c for c in rows(reader) if c['format'] != 'pdf'}
    assert len(actual) == 564 and actual == old


def test_pdf_lineage_rebased_without_aliases(integrated):
    corpus, reader, _ = integrated
    mapping = json.loads((ROOT / 'data/chunking/m3-c14-scope-v1/CHUNK_ID_RECONCILIATION.json').read_bytes())
    assert len(mapping) == 414 and all(x['old_chunk_id'] != x['new_chunk_id'] for x in mapping)
    for m in mapping:
        assert reader.get_chunk(m['new_chunk_id'])['format'] == 'pdf'
        with pytest.raises(ValueError, match='unknown_chunk'):
            reader.get_chunk(m['old_chunk_id'])
    old_uid = json.loads((WORK / 'FROZEN_SOURCE_WITNESSES.json').read_bytes())['predecessor_native_unit']
    with pytest.raises(ValueError, match='unknown_forged'):
        corpus.evidence.get_verified_unit('pdf:002c26b5666e7889a8494542643899ce1dec04e2a7e88cb1c8917fa8c0cef44b:' + old_uid)


def test_hold_and_excluded_neighbors_have_no_membership(integrated):
    corpus, reader, _ = integrated
    for status in ['HOLD', 'EXCLUDED']:
        page = corpus.catalog.list_sections('C14', filters={'admission_status': status}, limit=1000)
        assert page['total'] > 0
        for row in page['items']:
            assert row['unit_ids'] == []
            assert reader.get_section_chunks(row['section_id']) == []


def test_m0_m1_and_both_m2_configs_regenerated(integrated):
    corpus, reader, _ = integrated
    home = ROOT / 'data/chunking/m3-c14-scope-v1'
    prepared = [json.loads(s) for s in (home / 'm0-m1-prepared-inputs.jsonl').read_text().splitlines()]
    assert len(prepared) == 553 and len({p['unit_id'] for p in prepared}) == 553
    validation = json.loads((home / 'M1_M2_VALIDATIONS.json').read_bytes())
    for budget in [256, 384]:
        c01 = [v for v in validation['accepted_configurations']
               if v['budget'] == budget and v.get('document_id') != 'C14']
        assert len(c01) == 61
        assert sum(v['chunks'] for v in c01) == (114 if budget == 256 else 88)
    for p in prepared:
        if p['format'] != 'pdf':
            continue
        assert {m['section_id'] for m in p['memberships']} <= {
            s['section_id'] for s in p['section_bindings']}
    assert len(reader.outcomes()) == len(corpus.catalog.list_units())


def test_wrong_publication_and_forged_evidence_fail_closed(integrated):
    corpus, reader, _ = integrated
    from rag_hub.pdf_text_handoff import load_units

    selected = json.loads((ROOT / 'config/pdf-c14-scope-admission-publication-v1.json').read_bytes())
    selected['expected_manifest_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='hash_mismatch'):
        load_units(ROOT, **selected)
    view = reader.open_chunk(rows(reader)[0]['chunk_id'])
    view['chunk']['parent_binding']['publication_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='stripped'):
        reader.validate_view(view)
    with pytest.raises(ValueError, match='unknown'):
        corpus.evidence.get_verified_unit('forged')


def test_accepted_defaults_and_historical_catalog_remain_separate(integrated):
    corpus, _, _ = integrated
    from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

    with pytest.raises(ValueError, match='upstream_binding_changed'):
        QualifiedChunkCatalog(ROOT, corpus)  # Old 978-row catalog cannot bind a new publication.
    current = {s['section_id']: s for s in corpus.catalog.list_sections('C14', limit=1000)['items']}
    for bid in ['b00368', 'b00383', 'b00386']:
        row = next(s for sid, s in current.items() if ':' + bid + ':' in sid)
        assert row['admission_status'] == 'ADMITTED' and row['context_only']
        assert all(m['role'] == 'supporting_heading' for m in row['memberships'])


def test_preparation_and_source_qa_separation(integrated):
    corpus, reader, _ = integrated
    from rag_hub.chunk_preparation import ChunkPreparation

    p = ChunkPreparation(corpus)
    uid = new_scopes(corpus)[1]['unit_id']
    record = p.prepare(uid)
    assert record.indexable_source_content and record.qa_observations
    assert all(s.native_source['kind'] == 'SOURCE_CONTENT' for s in record.indexable_source_content)
    assert record.required_context and record.qualification['complete_unit_only']
    value = record.model_dump(mode='json')
    value['qualification']['complete_unit_only'] = False
    with pytest.raises(ValueError):
        p.validate(value)
    view = reader.open_chunk(reader.get_unit_chunks(uid)[0])
    with pytest.raises((TypeError, ValueError)):
        corpus.evidence.validate(view['source_slice'])


def test_structural_witness_references_are_bound_and_reconciled(integrated):
    corpus, reader, _ = integrated
    from rag_hub.unified_models import sha

    path = reader.manifest['structural_witness_index']
    raw = (ROOT / path).read_bytes()
    assert sha(raw) == reader.manifest['files'][path]
    index = json.loads(raw)
    units = {m['unit_id'] for m in corpus.catalog.list_units()}
    assert index['fields'] and all(f['unit_id'] in units for f in index['fields'])
    assert index['historical_superseded_fields']
    assert all(f['status'] == 'SUPERSEDED_MIXED_SCOPE_NOT_ACTIVE_MEMBERSHIP'
               for f in index['historical_superseded_fields'])
    for f in index['fields']:
        if 'binding' in f:
            assert f['binding']['sha256'] == reader.manifest['components'][f['binding']['path']]
    assert len([f for f in index['fields'] if f['status'] == 'SOURCE_SUPPORTED_QA_PUBLISHED_SCOPE']) == 4
