"""Fixed H4 stack selection and session isolation, without alternate evidence paths."""

from pathlib import Path

import pytest

from rag_hub.operational_selection import (
    DURABLE,
    HISTORICAL,
    MODES,
    PILOT,
    PREMIGRATION,
    resolve_selection,
    switch_release,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('selector,counts', [
    (HISTORICAL, (550, 893)), (PILOT, (61, 88)),
    (PREMIGRATION, (553, 992)), (DURABLE, (553, 992)),
])
def test_trusted_compatible_selection(selector, counts):
    selection = resolve_selection(ROOT, selector)
    assert (selection.spec['catalog_units'], selection.spec['chunks']) == counts
    assert selection.manifest['summary']['units'] == counts[0]
    selection.check()


@pytest.mark.parametrize('selector', ['', 'latest', 'config/retrieval-chunks-m3-qualified-v2.json',
                                      '../config/retrieval-chunks-v2.json'])
def test_unselected_mode_fails_without_fallback(selector):
    with pytest.raises(ValueError, match='unsupported_operational_release'):
        resolve_selection(ROOT, selector)


def test_missing_and_forged_selector_fail_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_selection(tmp_path, DURABLE)
    path = tmp_path / DURABLE
    path.parent.mkdir()
    path.write_text('{}')
    with pytest.raises(ValueError, match='binding_changed'):
        resolve_selection(tmp_path, DURABLE)


def test_missing_manifest_and_changed_witness_invalidate_selection(tmp_path):
    selection = resolve_selection(ROOT, DURABLE)
    selector_path = tmp_path / DURABLE
    selector_path.parent.mkdir(parents=True)
    selector_path.write_bytes((ROOT / DURABLE).read_bytes())
    with pytest.raises(FileNotFoundError):
        resolve_selection(tmp_path, DURABLE)
    import json
    manifest = json.loads(selector_path.read_text())['manifest_path']
    dest = tmp_path / manifest
    dest.parent.mkdir(parents=True)
    dest.write_bytes((ROOT / manifest).read_bytes())
    copied = resolve_selection(tmp_path, DURABLE)
    dest.write_text('{}')
    with pytest.raises(ValueError, match='snapshot_invalidated'):
        copied.check()
    dest.write_bytes((ROOT / manifest).read_bytes())
    with pytest.raises(ValueError, match='snapshot_invalidated'):
        copied.check()
    assert selection.key == resolve_selection(ROOT, DURABLE).key


def test_cache_keys_and_clear_all_lineage_selections():
    keys = [resolve_selection(ROOT, selector).key for selector in MODES]
    assert len(set(keys)) == 4
    state = {'view': 'Chunk Inspector', 'selected_unit': 'old', 'selected_section': 'old',
             'document': 'C01', 'chunk_entered': 'old', 'chunk_selected': 'old',
             'chunk_unit_filter': 'old', 'chunk_section_filter': 'old',
             'page:C01:All:': 3, 'assembly_unit': 'old'}
    assert switch_release(state, keys[0])
    assert state == {'view': 'Chunk Inspector', '_operational_identity': keys[0]}
    state['selected_unit'] = 'still-valid'
    assert not switch_release(state, keys[0])
    assert state['selected_unit'] == 'still-valid'
    assert switch_release(state, keys[3])
    assert 'selected_unit' not in state
