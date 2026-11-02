"""Actual Streamlit AppTest smoke of the additive M3 read-only inspector."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def chunk_app():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    from rag_hub.dashboard_ui import load_dashboard

    data = load_dashboard(str(ROOT))
    app = AppTest.from_file(str(ROOT / "apps/ingestion_dashboard/app.py"), default_timeout=180)
    app.session_state["view"] = "Chunk Inspector"
    app.run()
    return app, data


def test_chunk_inspector_starts_without_generation(chunk_app):
    app, _ = chunk_app
    assert not app.exception
    assert any(t.value == "Retrieval Chunk Inspector" for t in app.title)
    assert any("not independent evidence" in c.value for c in app.caption)
    assert any(m.label == "Catalog chunks" for m in app.metric)


def test_chunk_opens_parent_context_warnings_and_roles(chunk_app):
    from rag_hub.chunk_dashboard import load_chunk_catalog

    app, data = chunk_app
    selector = app.selectbox(key="operational_release").value
    cat = load_chunk_catalog(str(ROOT), selector, _data=data)
    chunk = cat.list_chunks("C01", limit=1)["items"][0]
    next(t for t in app.text_input if t.label == "Exact version-qualified Chunk ID").set_value(
        chunk["chunk_id"])
    app.run()
    assert not app.exception
    view = cat.open_chunk(chunk["chunk_id"])
    assert any(t.value == view["source_slice"] for t in app.text)
    assert any(b.key == "chunk-open-parent" for b in app.button)
    assert len([b for b in app.button if b.key and b.key.startswith("chunk-open-section-")]) == len(
        cat.get_chunk_sections(chunk["chunk_id"]))
    assert any("Qualifications" in t.value for t in app.subheader)


def test_chunk_unknown_id_has_no_raw_fallback(chunk_app):
    app, _ = chunk_app
    next(t for t in app.text_input if t.label == "Exact version-qualified Chunk ID").set_value(
        "forged-chunk-id")
    app.run()
    assert not app.exception
    assert any("ID not found" in e.value for e in app.error)
    assert not any(b.key == "chunk-open-parent" for b in app.button)


def test_chunk_parent_and_section_navigation(chunk_app):
    from rag_hub.chunk_dashboard import load_chunk_catalog

    app, data = chunk_app
    catalog = load_chunk_catalog(str(ROOT), app.selectbox(key="operational_release").value, _data=data)
    row = catalog.list_chunks("C01", limit=1)["items"][0]
    next(t for t in app.text_input if t.label == "Exact version-qualified Chunk ID").set_value(
        row["chunk_id"])
    app.run()
    app.button(key="chunk-open-parent").click().run()
    assert not app.exception
    assert app.title[0].value == "Section & Unit Inspector"
    app.button(key="unit-chunk-lineage").click().run()
    assert not app.exception
    assert app.title[0].value == "Retrieval Chunk Inspector"
    assert app.text_input(key="chunk_unit_filter").value == row["unit_id"]
    # Returning to an inventory does not silently choose a child. Streamlit
    # removes widgets from the previous view; explicitly reopen the desired ID.
    next(t for t in app.text_input if t.label == "Exact version-qualified Chunk ID").set_value(
        row["chunk_id"])
    app.run()
    app.button(key="chunk-open-section-0").click().run()
    assert not app.exception
    assert app.title[0].value == "Section & Unit Inspector"
    app.button(key="section-chunk-lineage").click().run()
    assert not app.exception
    assert app.title[0].value == "Retrieval Chunk Inspector"
    assert app.text_input(key="chunk_section_filter").value


@pytest.fixture(scope="module")
def h4_app():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "apps/ingestion_dashboard/app.py"), default_timeout=240)
    app.session_state["view"] = "Chunk Inspector"
    app.run()
    return app


@pytest.mark.parametrize('selector,units,chunks', [
    ('config/retrieval-chunks-v2.json', 550, 893),
    ('config/retrieval-chunks-c01-v2.json', 61, 88),
    ('config/retrieval-chunks-m3-c14-scope-v2.json', 553, 992),
    ('config/retrieval-chunks-m3-durable-v1.json', 553, 992),
])
def test_h4_actual_modes_and_identity(h4_app, selector, units, chunks):
    app = h4_app
    app.selectbox(key='operational_release').set_value(selector).run()
    assert not app.exception and not app.error
    metrics = {m.label: m.value for m in app.metric}
    assert int(metrics['Catalog chunks']) == chunks
    assert int(metrics['Accounted verified units']) == units
    assert any(selector in c.value for c in app.caption)
    assert any('Manifest SHA-256:' in c.value for c in app.caption)
    if 'durable' in selector:
        assert any('992 embeddings' in x.value for x in app.info)
        assert any('M4 owner acceptance pending' in x.value for x in app.caption)


def test_h4_durable_qualified_parent_and_reverse_navigation(h4_app):
    from rag_hub.chunk_dashboard import load_chunk_catalog
    from rag_hub.dashboard_ui import load_dashboard
    from rag_hub.operational_selection import DURABLE

    app = h4_app
    app.selectbox(key='operational_release').set_value(DURABLE).run()
    data = load_dashboard(str(ROOT), selector=DURABLE)
    cat = load_chunk_catalog(str(ROOT), DURABLE, _data=data)
    # All four admitted Markdown projections have real chunks with full parents.
    protected = [u for u in data.units('C04') if u['scope_limited_projection']]
    assert len(protected) == 4
    for unit in protected:
        cid = cat.get_unit_chunks(unit['unit_id'])[0]
        app.text_input(key='chunk_entered').set_value(cid).run()
        assert not app.exception and not app.error
        view = cat.open_chunk(cid)
        projection = view['verified_parent']['consumer']['llm_context']['source_content'][0][
            'restricted_projection']
        assert any(t.value == projection['consumable_text'] for t in app.text)
        assert all(any(w.value == warning for w in app.warning) for warning in projection['warnings'])
        assert any(h.value == 'Complete authorized parent' for h in app.subheader)
    app.button(key='chunk-open-parent').click().run()
    assert app.title[0].value == 'Section & Unit Inspector'
    app.button(key='unit-chunk-lineage').click().run()
    assert app.text_input(key='chunk_unit_filter').value == protected[-1]['unit_id']


def test_h4_switch_clears_stale_chunk_and_cross_release_id_rejected(h4_app):
    from rag_hub.chunk_dashboard import load_chunk_catalog
    from rag_hub.dashboard_ui import load_dashboard
    from rag_hub.operational_selection import DURABLE, HISTORICAL

    app = h4_app
    app.selectbox(key='operational_release').set_value(DURABLE).run()
    data = load_dashboard(str(ROOT), selector=DURABLE)
    cat = load_chunk_catalog(str(ROOT), DURABLE, _data=data)
    cid = cat.list_chunks('C14', limit=1)['items'][0]['chunk_id']
    app.text_input(key='chunk_entered').set_value(cid).run()
    assert not app.exception and not app.error
    app.selectbox(key='operational_release').set_value(HISTORICAL).run()
    assert not app.exception and not app.error
    assert app.text_input(key='chunk_entered').value == ''
    assert app.text_input(key='chunk_unit_filter').value == ''
    assert not any(h.value == 'Authorized source display slice' for h in app.subheader)
    app.text_input(key='chunk_entered').set_value(cid).run()
    assert any('ID not found' in e.value for e in app.error)
    assert not any(h.value == 'Complete authorized parent' for h in app.subheader)


def test_h4_specialized_current_content_keeps_full_parent_and_qualifications():
    import copy
    import json

    from rag_hub.chunk_dashboard import load_chunk_catalog
    from rag_hub.dashboard_ui import load_dashboard
    from rag_hub.operational_selection import DURABLE

    data = load_dashboard(str(ROOT), selector=DURABLE)
    cat = load_chunk_catalog(str(ROOT), DURABLE, _data=data)
    rows = cat.list_chunks(limit=1000)['items']
    exceptional = [r for r in rows if r['token_count'] > 384]
    assert len(exceptional) == 4
    targets = list(exceptional)
    for did in ['C04', 'C06', 'C16']:
        qualified = [r for r in rows if r['document_id'] == did and cat.manifest[
            'configurations'][r['configuration_id']].get('schema') == 'm3-qualified-config-1.0']
        assert qualified
        targets.append(qualified[0])
    corrected = json.loads((ROOT / 'data/normalized/pdf/c14-scope-correction-v1/C14.json').read_text())
    replacements = corrected['scope_correction']['replacement_unit_ids']
    assert len(replacements) == 4
    for native_id in replacements:
        unit = next(u for u in data.units('C14') if u['native_unit_id'] == native_id)
        targets.append(cat.get_chunk(cat.get_unit_chunks(unit['unit_id'])[0]))
    targets.append(next(r for r in rows if r['document_id'] == 'C10'
                        and 'html-c10-unit:' in r['unit_id']))
    for row in targets:
        view = cat.open_chunk(row['chunk_id'])
        assert cat.validate_view(view)
        context = view['verified_parent']['consumer']['llm_context']
        assert context['qualification']
        assert view['verified_parent']['citation_locators']
        assert view['verified_parent']['publication_identity']
        if row['token_count'] > 384:
            assert cat.manifest['configurations'][row['configuration_id']]['total_tokens'] == 512
        if row['document_id'] == 'C10':
            assert context['qa_observations'] and 'RRF' in str(context['required_context'])
        for key in ['qualification', 'required_context']:
            forged = copy.deepcopy(view)
            forged['verified_parent']['consumer']['llm_context'][key] = 'stripped'
            with pytest.raises(ValueError, match='altered_stale_or_warning_stripped'):
                cat.validate_view(forged)
    expiry_unit = next(u for u in data.units('C01') if u['native_unit_id'].startswith('pdf-preserved:'))
    value = data.verified_unit(expiry_unit['unit_id'])
    expiry = value['consumer']['publication_expiration']
    assert expiry['status'] in {'VALID', 'EXPIRED'}
    if expiry['status'] == 'EXPIRED':
        assert expiry['warning']


def test_h4_cached_snapshot_does_not_survive_missing_live_witness(tmp_path):
    from rag_hub.dashboard_ui import load_dashboard
    from rag_hub.operational_selection import DURABLE
    from rag_hub.unified_bindings import BoundFiles
    from rag_hub.unified_models import sha

    data = load_dashboard(str(ROOT), selector=DURABLE)
    witness = tmp_path / 'witness'
    witness.write_bytes(b'evidence')
    lease = BoundFiles(tmp_path)
    lease.bind('witness', sha(b'evidence'))
    original = data._inspection
    data._inspection = lease
    witness.unlink()  # disposable lease fixture only, no corpus mutation
    try:
        with pytest.raises(ValueError, match='snapshot_invalidated'):
            load_dashboard(str(ROOT), selector=DURABLE)
    finally:
        data._inspection = original
