"""Opt-in H2 reader safeguards through real native publications; no new authority."""

import copy
import json
from pathlib import Path

import pytest

from rag_hub.durable_unified_selection import load_durable_corpus

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def durable():
    if not (ROOT / 'config/unified-durable-selection-v1.json').exists():
        pytest.skip('private opt-in H2 successor not installed')
    return load_durable_corpus(ROOT)


def test_real_durable_counts_and_complete_memberships(durable):
    summary = durable.catalog.get_corpus_summary()
    assert {k: summary[k] for k in ['documents', 'sections', 'admitted', 'excluded', 'HOLD',
                                   'units', 'membership_edges']} == {
        'documents': 16, 'sections': 3040, 'admitted': 2572, 'excluded': 110,
        'HOLD': 358, 'units': 553, 'membership_edges': 3727}
    assert sum(len(durable.catalog.get_unit_sections(u['unit_id']))
               for u in durable.catalog.list_units()) == 3727


def test_no_workspace_or_archive_bindings_and_all_fifty_evidence_roles(durable):
    files = durable.binding_manifest()['files']
    assert not any(p.startswith(('workspace/', 'archive/', 'releases/')) for p in files)
    rows = json.loads((ROOT / 'data/validation/provenance/durable-consumer-v1/EVIDENCE_MIGRATION.json').read_bytes())['rows']
    live = [r for r in rows if r['new_active_role'] == 'RETAIN_EVIDENCE']
    assert len(live) == 50
    assert all(files[r['proposed_target']] == r['expected_sha256'] for r in live)
    assert not any(r['proposed_target'] in files for r in rows if r['new_active_role'] == 'ARCHIVE_ONLY')


@pytest.mark.parametrize('status,count', [('HOLD', 358), ('EXCLUDED', 110)])
def test_nonadmitted_sections_remain_metadata_only(durable, status, count):
    page = durable.catalog.list_sections(filters={'admission_status': status}, limit=1000)
    assert page['total'] == count
    for row in page['items']:
        assert not row['unit_ids']
        assert 'text' not in row
        with pytest.raises(ValueError):
            durable.evidence.get_verified_unit(row['section_id'])


def test_context_roles_bidirectional_and_not_independent_evidence(durable):
    unit = next(u for u in durable.catalog.list_units() if any(
        m['role'] in {'supporting_heading', 'required_context'} for m in u['memberships']))
    for member in durable.catalog.get_unit_sections(unit['unit_id']):
        section = durable.catalog.get_section(member['section_id'])
        assert unit['unit_id'] in section['unit_ids']
        assert any(m['unit_id'] == unit['unit_id'] and m['role'] == member['role']
                   for m in section['memberships'])
        assert not section['raw_section_is_independent_consumption_unit']


@pytest.mark.parametrize('field', ['qualification', 'required_context', 'qa_observations'])
def test_warning_context_and_qualification_stripping_rejected(durable, field):
    unit = next(u for u in durable.catalog.list_units(document_id='C04')
                if u['scope_limited_projection'])
    view = durable.evidence.get_verified_unit(unit['unit_id'])
    altered = copy.deepcopy(view)
    del altered['consumer']['llm_context'][field]
    with pytest.raises(ValueError, match='altered_or_warning_context_stripped'):
        durable.evidence.validate(altered)


def test_C10_required_RRF_and_QA_authorship_preserved(durable):
    selection = json.loads((ROOT / 'config/html-c10-admission-publication.json').read_bytes())
    native = json.loads((ROOT / selection['manifest_path']).read_bytes())['delta_unit_id']
    unit = next(u for u in durable.catalog.list_units(document_id='C10') if u['native_unit_id'] == native)
    context = durable.evidence.get_verified_unit(unit['unit_id'])['consumer']['llm_context']
    assert any(o.get('issue_id') == 'HTML-SRC-SCORE-STAGE'
               and o.get('origin') == 'ingestion_QA_not_publisher' and o.get('must_accompany')
               for o in context['qa_observations'])
    assert any(c.get('relationship_type') == 'documented_RRF_context_not_numerical_equivalence'
               and c.get('required') for c in context['required_context'])


def test_C14_scopes_and_original_native_ids_preserved(durable):
    evidence = json.loads((ROOT / 'data/normalized/pdf/c14-scope-correction-v1/C14.json').read_bytes())
    native = set(evidence['scope_correction']['replacement_unit_ids'])
    selected = [u for u in durable.catalog.list_units(document_id='C14') if u['native_unit_id'] in native]
    assert len(selected) == 4
    assert all(durable.evidence.get_verified_unit(u['unit_id'])['consumer']['llm_context']['qualification']['mandatory']
               for u in selected)


def test_expired_PDF_remains_readable_with_warning(durable):
    for u in durable.catalog.list_units(document_id='C01'):
        view = durable.evidence.get_verified_unit(u['unit_id'])
        expired = view['consumer'].get('publication_expiration')
        if expired:
            assert expired['status'] == 'EXPIRED' and expired['warning']
            assert any(o.get('issue_id') == 'PDF_PUBLICATION_EXPIRED' and o.get('display_to_user_when_used')
                       for o in view['consumer']['llm_context']['qa_observations'])
            return
    pytest.fail('original expiration obligation missing')


@pytest.mark.parametrize('selector', ['config/unified-c14-scope-selection-v1.json', '', 'forged.json'])
def test_wrong_selection_is_explicit_rejection(selector):
    with pytest.raises(ValueError, match='unselected_durable_publication'):
        load_durable_corpus(ROOT, selector=selector)


def test_unknown_unit_never_uses_raw_fallback(durable):
    with pytest.raises(ValueError):
        durable.evidence.get_verified_unit('forged-unit')
