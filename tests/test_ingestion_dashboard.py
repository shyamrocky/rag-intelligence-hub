"""Dashboard contracts exercised against the real accepted private corpus."""

import copy
import json
from pathlib import Path

import pytest

from rag_hub.dashboard_data import (
    ASSEMBLY_UNRECORDED,
    DashboardData,
    educational_example,
    issue_metadata,
    locator_label,
)
from rag_hub.unified_bindings import FREEZE, BoundFiles

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'apps/ingestion_dashboard/app.py'


@pytest.fixture(scope='module')
def data():
    if not (ROOT / FREEZE).exists():
        pytest.skip('accepted private corpus not provided')
    # Cache and tests use the same actual public loader/snapshot; no fake evidence.
    try:
        from rag_hub.dashboard_ui import load_dashboard
    except ImportError:
        return DashboardData(ROOT)
    load_dashboard.clear()
    return load_dashboard(str(ROOT))


def test_counts_and_all_documents(data):
    s = data.summary()
    assert [s[k] for k in ('documents', 'sections', 'admitted', 'excluded', 'HOLD',
                           'units', 'membership_edges')] == [16, 3040, 2572, 110, 358, 550, 3727]
    rows = data.documents()
    for column, total in [('Sections', 3040), ('ADMITTED', 2572), ('EXCLUDED', 110),
                          ('HOLD', 358), ('Units', 550)]:
        assert sum(row[column] for row in rows) == total


@pytest.mark.parametrize('did,counts', [
    ('C01', (406, 277, 19, 110, 61)), ('C02', (453, 393, 22, 38, 50)),
    ('C06', (1095, 1028, 34, 33, 128)), ('C14', (471, 293, 1, 177, 70)),
])
def test_pdf_document_counts(data, did, counts):
    row = data.documents(query=did)[0]
    assert tuple(row[k] for k in ['Sections', 'ADMITTED', 'EXCLUDED', 'HOLD', 'Units']) == counts
    profile = data.document_profile(did)
    assert sum(profile['structural_types'].values()) == counts[0]
    assert sum(profile['classifications'].values()) == counts[0]
    assert profile['parser']['recorded_dependencies']['pymupdf'] == '1.28.2'
    assert 'Not recorded' in profile['parser']['MinerU']
    assert profile['locator_coverage']['total_sections'] == counts[0]


@pytest.mark.parametrize('fmt,total,sections,admitted,units', [
    ('html', 11, 457, 427, 155), ('markdown', 1, 158, 154, 86), ('pdf', 4, 2425, 1991, 309),
])
def test_format_filters(data, fmt, total, sections, admitted, units):
    rows = data.documents(fmt=fmt)
    assert len(rows) == total
    assert sum(r['Sections'] for r in rows) == sections
    assert sum(r['ADMITTED'] for r in rows) == admitted
    assert sum(r['Units'] for r in rows) == units
    assert data.documents(fmt=fmt, query='does-not-exist') == []


def test_publisher_and_status_filters(data):
    row = data.documents(query='C10')[0]
    assert data.documents(publisher=row['Publisher'])
    assert all(r['HOLD'] > 0 for r in data.documents(status='HOLD'))
    assert all(r['Format'] == 'PDF' for r in data.documents(status='HOLD'))


def test_document_sections_paginate_search_and_types(data):
    first = data.sections('C06', limit=25)
    second = data.sections('C06', offset=25, limit=25)
    assert first['total'] == 1095 and len(first['items']) == 25
    assert not ({r['Section ID'] for r in first['items']} &
                {r['Section ID'] for r in second['items']})
    for status, expected in [('ADMITTED', 1028), ('HOLD', 33), ('EXCLUDED', 34)]:
        assert data.sections('C06', status=status)['total'] == expected
    sid = first['items'][0]['Section ID']
    result = data.sections('C06', query=sid)
    assert len(result['items']) == 1
    assert result['items'][0]['Type'] != 'Not available in the frozen evidence.'


@pytest.mark.parametrize('offset,limit', [(-1, 25), (0, 999), (False, 25)])
def test_invalid_pagination(data, offset, limit):
    with pytest.raises(ValueError):
        data.sections('C01', offset=offset, limit=limit)


def test_exact_membership_visualization_and_reverse_links(data):
    units = data.units('C02')
    unit = next(u for u in units if len(u['memberships']) >= 3)
    actual = data.relationships(unit['unit_id'])
    native = data.corpus.catalog.get_unit_sections(unit['unit_id'])
    assert [(r['section_id'], r['role'], r['native_role']) for r in actual] == [
        (r['section_id'], r['role'], r['native_role']) for r in native]
    assert all(r['admission_status'] == 'ADMITTED' for r in actual)
    for row in actual:
        section = data.section(row['section_id'])
        assert section['unit_ids'] == data.corpus.catalog.get_section(row['section_id'])['unit_ids']
        assert unit['unit_id'] in section['unit_ids']
        assert row['context_only_in_unit'] == (row['role'] in {'required_context', 'supporting_heading'})
    # Select a genuinely shared Section rather than assuming the first C02 unit
    # happens to contain one. Every returned reverse link must match the catalog.
    shared = next(s for s in data.corpus.catalog.list_sections('C04', limit=1000)['items']
                  if len(s['unit_ids']) > 1)
    assert data.section(shared['section_id'])['unit_ids'] == shared['unit_ids']
    for uid in shared['unit_ids']:
        assert any(r['section_id'] == shared['section_id'] for r in data.relationships(uid))


def test_actual_unit_publication_and_assembly_evidence(data):
    unit = data.units('C10')[0]
    verified = data.verified_unit(unit['unit_id'])
    assert verified['publication_identity'] == unit['publication_identity']
    assert 'c009966ac7dd' in json.dumps(verified['publication_identity'])
    evidence = data.assembly_evidence(verified)
    assert all('basis' in e for e in evidence)
    assert all('semantic similarity' not in e['basis'] for e in evidence)
    assert ASSEMBLY_UNRECORDED.startswith('Verified membership established')


def test_educational_example_is_not_actual_evidence(data):
    example = educational_example()
    assert example['authority'] == 'ILLUSTRATIVE_ONLY_NOT_CORPUS_EVIDENCE'
    assert 'not actual corpus evidence' in example['label']
    for sid in [s['section_id'] for s in example['sections']]:
        with pytest.raises(ValueError):
            data.section(sid)
    with pytest.raises(ValueError):
        data.verified_unit(example['unit_id'])


@pytest.mark.parametrize('status', ['HOLD', 'EXCLUDED'])
def test_nonadmitted_visible_without_evidence(data, status):
    row = data.corpus.catalog.list_sections(filters={'admission_status': status}, limit=1)['items'][0]
    sid = row['section_id']
    inspection = data.section(sid)
    assert inspection['admission_status'] == status
    assert inspection['unit_ids'] == [] and inspection['unit_qualifications'] == []
    assert 'text' not in inspection and 'consumer' not in inspection
    assert all('evidence' not in i for i in inspection['issues'])
    with pytest.raises(ValueError):
        data.verified_unit(sid)
    with pytest.raises(ValueError):
        data.relationships(sid)


def test_context_only_sections_remain_context(data):
    native = data.corpus.catalog.list_sections(filters={'context_only': True}, limit=1)['items'][0]
    section = data.section(native['section_id'])
    assert section['context_only']
    for m in section['memberships']:
        assert m['role'] in {'required_context', 'supporting_heading'}
    with pytest.raises(ValueError):
        data.verified_unit(section['section_id'])


def test_restricted_markdown_and_c10_qualifications(data):
    restricted = [u for u in data.units('C04') if u['scope_limited_projection']]
    assert len(restricted) == 4
    for unit in restricted:
        value = data.verified_unit(unit['unit_id'])
        context = value['consumer']['llm_context']
        assert context['source_content'][0]['restricted_projection']
        assert context['qa_observations']
        assert 'source_evidence' not in value['consumer']
    value = data.verified_unit(data.units('C10')[0]['unit_id'])
    context = value['consumer']['llm_context']
    assert context['source_content'][0]['table']
    assert any(o.get('issue_id') == 'HTML-SRC-SCORE-STAGE' for o in context['qa_observations'])
    assert any('RRF' in str(c) for c in context['required_context'])


@pytest.mark.parametrize('alteration', ['warning', 'context', 'text', 'publication'])
def test_forged_payloads_rejected(data, alteration):
    value = data.verified_unit(data.units('C10')[0]['unit_id'])
    value = copy.deepcopy(value)
    if alteration == 'warning':
        value['consumer']['llm_context']['qa_observations'] = []
    elif alteration == 'context':
        value['consumer']['llm_context']['required_context'] = []
    elif alteration == 'text':
        value['consumer']['llm_context']['source_content'][0]['text'] = 'forged'
    else:
        value['publication_identity']['expected_manifest_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='altered_or_warning_context_stripped'):
        data.validate_unit(value)


def test_pdf_limited_projection_and_expiration_metadata(data):
    unit = next(u for u in data.units('C06') if u['scope_limited_projection'])
    value = data.verified_unit(unit['unit_id'])
    assert value['scope_limited_projection']
    assert value['consumer']['llm_context']['qualification']['mandatory']
    old = next(u for u in data.units('C01') if u['native_unit_id'].startswith('pdf-preserved:'))
    value = data.verified_unit(old['unit_id'])
    expiry = value['consumer']['publication_expiration']
    assert expiry['status'] in {'VALID', 'EXPIRED'}
    if expiry['status'] == 'EXPIRED':
        assert expiry['warning']


def test_lease_invalidates_instead_of_using_detached_cache(data, tmp_path):
    # Real bound-file implementation, isolated control; never mutate corpus files.
    path = tmp_path / 'bound'; path.write_bytes(b'original')
    from rag_hub.unified_models import sha
    bound = BoundFiles(tmp_path); bound.bind('bound', sha(b'original'))
    path.write_bytes(b'altered!')
    original = data._inspection
    data._inspection = bound
    try:
        with pytest.raises(ValueError, match='snapshot_invalidated'):
            data.summary()
        with pytest.raises(ValueError, match='snapshot_invalidated'):
            data.verified_unit(data.units('C01')[0]['unit_id'])
    finally:
        data._inspection = original


def test_inspection_filters_raw_nested_evidence():
    result = issue_metadata([{'issue_id': 'test', 'description': 'safe observation',
                              'evidence': [{'text': 'raw restricted'}], 'source_excerpt': 'private'}])
    assert result == [{'issue_id': 'test', 'description': 'safe observation'}]
    assert locator_label([{'page': 5}]) == 'p. 5'
    assert 'lines' in locator_label([{'line_start': 1, 'line_end': 3}])


@pytest.fixture(scope='module')
def app(data):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    result = AppTest.from_file(str(APP), default_timeout=180).run()
    assert not result.exception
    return result


def test_streamlit_overview_and_warm_cache(app, data):
    from rag_hub.dashboard_ui import load_dashboard
    assert load_dashboard(str(ROOT)) is data
    assert app.title[0].value == 'Ingestion pipeline'
    assert any('How Sections Become Verified Units' in h.value for h in app.subheader)
    assert any('not actual corpus evidence' in i.value for i in app.info)
    app.run()
    assert not app.exception and load_dashboard(str(ROOT)) is data


def test_streamlit_document_and_section_navigation(app):
    app.sidebar.radio(key='view').set_value('Document Explorer').run()
    assert not app.exception
    app.selectbox(key='format_filter').set_value('PDF').run()
    app.selectbox(key='document').set_value('C01').run()
    assert not app.exception
    app.button(key='document-open-section').click().run()
    assert not app.exception
    assert app.title[0].value == 'Section & Unit Inspector'
    assert any('INSPECTION_ONLY' in c.value for c in app.caption)


def test_streamlit_actual_relationships_and_reverse_unit_navigation(app, data):
    app.sidebar.radio(key='view').set_value('Pipeline Overview').run()
    app.radio(key='relationship_mode').set_value('Explore actual corpus relationships').run()
    assert not app.exception
    assert not any('not actual corpus evidence' in i.value for i in app.info)
    uid = app.selectbox(key='relationship_unit').value
    expected = data.corpus.catalog.get_unit_sections(uid)
    node_buttons = [b for b in app.button if b.key and b.key.startswith('assembly-')
                    and b.key != 'assembly-open-unit']
    assert [b.label for b in node_buttons] == [e['section_id'] for e in expected]
    assert all(any(e['role'] in c.value and e['native_role'] in c.value
                   for c in app.caption) for e in expected)
    assert any('publication' in c.value.lower() for c in app.caption)
    app.button(key='assembly-open-unit').click().run()
    assert not app.exception
    assert any('VERIFIED_CONSUMER_EVIDENCE' in c.value for c in app.caption)
    assert app.session_state['selected_unit'] == uid


def test_streamlit_unknown_id_safe_error(app):
    app.sidebar.radio(key='view').set_value('Section & Unit Inspector').run()
    app.radio(key='inspector_mode').set_value('Section').run()
    app.text_input[0].input('unknown-section')
    app.button(key='FormSubmitter:id-search-Inspect ID').click().run()
    assert not app.exception
    assert any('ID not found' in e.value for e in app.error)


def test_warm_dashboard_never_reruns_pipeline_or_exports_catalog(data, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('warm inspection reran loading, QA, parsing or full catalog export')
    for module in ['html_handoff', 'markdown_handoff', 'pdf_text_handoff']:
        monkeypatch.setattr(f'rag_hub.{module}.load_units', forbidden)
    monkeypatch.setattr('rag_hub.shared.qa.assess', forbidden)
    monkeypatch.setattr(data.corpus.catalog, 'export', forbidden)
    data.summary(); data.documents(); data.document_profile('C04')
    section = data.sections('C04')['items'][0]['Section ID']
    data.section(section)
    data.verified_unit(data.units('C04')[0]['unit_id'])


def test_expired_pdf_warning_reaches_dashboard_reader(data, monkeypatch):
    from datetime import datetime, timedelta

    from rag_hub import pdf_publication
    old = next(u for u in data.units('C01') if u['native_unit_id'].startswith('pdf-preserved:'))
    before = data.verified_unit(old['unit_id'])
    expiry = before['consumer']['publication_expiration']
    end = datetime.fromisoformat(expiry['expires_at'])
    monkeypatch.setattr(pdf_publication, 'utc_now', lambda: end + timedelta(seconds=1))
    expired = data.verified_unit(old['unit_id'])
    assert expired['consumer']['publication_expiration']['status'] == 'EXPIRED'
    assert expired['consumer']['publication_expiration']['warning']
    assert any(o.get('display_to_user_when_used') for o in
               expired['consumer']['llm_context']['qa_observations'])
    assert expired['consumer']['llm_context']['source_content'] == before['consumer']['llm_context']['source_content']


def test_streamlit_hold_has_no_content_view(app, data):
    held = data.corpus.catalog.list_sections(filters={'admission_status': 'HOLD'}, limit=1)['items'][0]
    app.session_state['selected_section'] = held['section_id']
    app.session_state['inspector_mode'] = 'Section'
    app.session_state['view'] = 'Section & Unit Inspector'
    app.run()
    assert not app.exception
    assert any('No verified unit membership' in i.value for i in app.info)
    assert not any('VERIFIED_CONSUMER_EVIDENCE' in c.value for c in app.caption)
    assert not any(b.key and b.key.startswith('section-linked-unit-') for b in app.button)


def test_streamlit_c10_table_context_and_qa_warning(app, data):
    app.session_state['selected_unit'] = data.units('C10')[0]['unit_id']
    app.session_state['inspector_mode'] = 'Unit'
    app.session_state['view'] = 'Section & Unit Inspector'
    app.run()
    assert not app.exception
    assert any('scoring' in w.value or 'scores' in w.value for w in app.warning)
    assert any('RRF' in t.value or 'Reciprocal' in t.value for t in app.text)
    # Complete native headers retained as table columns, not a flattened guess.
    assert any('@search.score' in str(df.value.columns) for df in app.dataframe)


def test_streamlit_restricted_markdown_uses_warning_projection(app, data):
    unit = next(u for u in data.units('C04') if u['scope_limited_projection'])
    value = data.verified_unit(unit['unit_id'])
    projection = value['consumer']['llm_context']['source_content'][0]['restricted_projection']
    app.session_state['selected_unit'] = unit['unit_id']
    app.session_state['inspector_mode'] = 'Unit'
    app.run()
    assert not app.exception
    assert any(t.value == projection['consumable_text'] for t in app.text)
    assert all(any(warning == w.value for w in app.warning) for warning in projection['warnings'])
