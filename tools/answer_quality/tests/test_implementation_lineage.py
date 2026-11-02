"""Exact snapshot readback cannot substitute source data or accept new code tampering."""
from pathlib import Path

import pytest

from tools.generation_artifact_lineage import HISTORICAL_IMPLEMENTATIONS
from tools.quality_dashboard.artifacts import ArtifactError, Store, sha


@pytest.mark.parametrize('name', sorted(HISTORICAL_IMPLEMENTATIONS))
def test_reviewed_history_readback_and_tamper_controls(tmp_path, name):
    root = Path(__file__).resolve().parents[3]
    entry = HISTORICAL_IMPLEMENTATIONS[name]
    current = tmp_path / name
    archive = tmp_path / entry['snapshot']
    for target, source in [(current, root / name), (archive, root / entry['snapshot'])]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    store = Store(tmp_path)
    assert store.bind(name, entry['historical_sha256']) == archive
    assert store.references[store.ref_id(name)]['status'] == 'HISTORICAL_IMPLEMENTATION_SNAPSHOT_VERIFIED'
    assert sha(archive) == entry['historical_sha256']
    archive.write_text('tampered historical code')
    with pytest.raises(ArtifactError, match='SNAPSHOT_CHANGED'):
        store.bind(name, entry['historical_sha256'])
    archive.write_bytes((root / entry['snapshot']).read_bytes())
    current.write_text('unreviewed successor')
    with pytest.raises(ArtifactError, match='ARTIFACT_HASH_MISMATCH'):
        store.bind(name, entry['historical_sha256'])


@pytest.mark.parametrize('name', ['source/evidence.json', 'config/settings.json',
                                 'workspace/OWNER_AUTHORIZATION.json', 'tools/unreviewed.py'])
def test_no_source_configuration_request_or_arbitrary_code_waiver(tmp_path, name):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('original')
    old = sha(path)
    path.write_text('tampered')
    with pytest.raises(ArtifactError, match='ARTIFACT_HASH_MISMATCH'):
        Store(tmp_path).bind(name, old)
