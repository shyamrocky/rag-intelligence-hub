"""Owned fixtures only; no private evidence or secrets in source tests."""
import json
from pathlib import Path

import pytest

from tools.quality_dashboard.artifacts import ArtifactError, Store, safe_path, sha


@pytest.mark.parametrize("name", ["../escape", "/etc/passwd", "data/../x", "data/.env",
                                  "data/secrets.toml", "data//x", "data\\x", ".git/index"])
def test_path_rejection(tmp_path, name):
    with pytest.raises(ArtifactError):
        safe_path(tmp_path, name)


def test_symlink_rejected(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "real").write_text("fixture")
    (tmp_path / "data/link").symlink_to(tmp_path / "real")
    with pytest.raises(ArtifactError, match="SYMLINK"):
        safe_path(tmp_path, "data/link")


def test_manifest_and_toctou(tmp_path):
    base = tmp_path / "data/example"
    base.mkdir(parents=True)
    source = base / "record.json"
    source.write_text('{"value": 7}')
    manifest = base / "MANIFEST.json"
    manifest.write_text(json.dumps({"schema": "fixture", "files": {"record.json": sha(source)}}))
    store = Store(tmp_path)
    store.manifest("data/example/MANIFEST.json", expected=sha(manifest), schema="fixture")
    assert store.json("data/example/record.json") == {"value": 7}
    source.write_text('{"value": 8}')
    with pytest.raises(ArtifactError, match="HASH"):
        store.json("data/example/record.json")


def test_duplicate_json_keys(tmp_path):
    (tmp_path / "data").mkdir()
    p = tmp_path / "data/duplicate.json"
    p.write_text('{"x": 1,"x":2}')
    store = Store(tmp_path)
    store.bind("data/duplicate.json", sha(p))
    with pytest.raises(ArtifactError, match="INVALID_ARTIFACT_JSON"):
        store.json("data/duplicate.json")


@pytest.mark.parametrize("payload", [{}, {"files": {}}, {"files": {"../escape": "a" * 64}}])
def test_unsealed_and_traversal_manifests(tmp_path, payload):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/manifest.json").write_text(json.dumps(payload))
    with pytest.raises(ArtifactError):
        Store(tmp_path).manifest("data/manifest.json")


def test_unknown_reference_never_opens_path(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(ArtifactError, match="UNBOUND"):
        store.json(".env")
    assert not store.references


def test_no_provider_or_evidence_execution_in_refresh_source():
    import ast

    base = Path(__file__).resolve().parents[1]
    for name in ("adapter.py", "artifacts.py", "ui.py"):
        tree = ast.parse((base / name).read_text())
        forbidden = {"OpenAI", "OpenAIAdapter", "EvidenceService", "GenerationService", "getenv"}
        assert not any(isinstance(n, ast.Name) and n.id in forbidden for n in ast.walk(tree))
