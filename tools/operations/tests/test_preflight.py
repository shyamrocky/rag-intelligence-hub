"""Fail-closed operational checks; native evidence gates are exercised by the real CLI."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))

from check_selection import (
    PROFILE,
    PROFILE_SHA256,
    bound,
    check_bindings,
    environment,
    load_profile,
)
from installation_manifest import validate_runtime


def test_actual_selected_binding_closure():
    report = check_bindings(ROOT, load_profile(ROOT, PROFILE, PROFILE_SHA256))
    assert report["files"] >= 465
    assert report["workspace_dependencies"] == 0


@pytest.mark.parametrize("path,digest", [
    ("", PROFILE_SHA256), ("latest", PROFILE_SHA256),
    ("config/vector-index-m5-v1.json", PROFILE_SHA256), (PROFILE, "0" * 64),
])
def test_no_profile_default_or_mixed_release(path, digest):
    with pytest.raises(ValueError, match="no_fallback"):
        load_profile(ROOT, path, digest)


def test_missing_and_modified_profile(tmp_path):
    with pytest.raises(ValueError, match="missing_or_unreadable"):
        load_profile(tmp_path, PROFILE, PROFILE_SHA256)
    p = tmp_path / PROFILE
    p.parent.mkdir()
    p.write_text("{}")
    with pytest.raises(ValueError, match="hash_mismatch"):
        load_profile(tmp_path, PROFILE, PROFILE_SHA256)


@pytest.mark.parametrize("name", ["../escape", "/tmp/foreign"])
def test_unsafe_bound_path(tmp_path, name):
    with pytest.raises(ValueError, match="unsafe_operational_path"):
        bound(tmp_path, name, "0" * 64)


def test_symlink_even_with_matching_bytes_is_rejected(tmp_path):
    import hashlib

    (tmp_path / "real").write_text("owned")
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(ValueError, match="unsafe_operational_path"):
        bound(tmp_path, "link", hashlib.sha256(b"owned").hexdigest())


@pytest.mark.parametrize("role", ["selection", "verification_components"])
def test_missing_or_foreign_components_fail_before_native_calls(tmp_path, role):
    profile = load_profile(ROOT, PROFILE, PROFILE_SHA256)
    broken = copy.deepcopy(profile)
    if role == "selection":
        name = next(iter(broken[role]))
        broken[role][name] = "0" * 64
        with pytest.raises(ValueError, match="hash_mismatch"):
            check_bindings(ROOT, broken)
    else:
        with pytest.raises(ValueError, match="missing_or_unreadable"):
            check_bindings(tmp_path, broken)


@pytest.mark.parametrize("field,value", [
    ("python_exact", "3.15.0"), ("machine", "x86_64"), ("system", "Linux"),
    ("distributions", {}),
])
def test_incompatible_runtime(field, value):
    p = load_profile(ROOT, PROFILE, PROFILE_SHA256)
    project = p["projects"][0]
    d = {"python_exact": p["python"], **p["platform"],
         "distributions": project["distributions"]}
    d[field] = value
    with pytest.raises(ValueError, match="incompatible_|differs_from"):
        validate_runtime(d, project, p)


def test_environment_ignores_inherited_override(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "foreign")
    monkeypatch.setenv("RAG_TEST_QA_RELEASE", "foreign")
    env = environment()
    assert "PYTHONPATH" not in env and "RAG_TEST_QA_RELEASE" not in env
    assert env["UV_OFFLINE"] == "1"


def test_cli_requires_explicit_selection():
    result = subprocess.run([sys.executable, str(TOOLS / "check_selection.py"),
                             "--root", str(ROOT)], capture_output=True, check=False)
    assert result.returncode == 2
    assert b"--profile" in result.stderr


def test_profile_not_a_new_admission_or_publication_identity():
    profile = json.loads((ROOT / PROFILE).read_text())
    assert profile["authority"] == "INSPECTION_CONFIGURATION_NOT_ADMISSION_OR_RELEASE"
    assert profile["implicit_fallback"] is False
    assert len(profile["projects"]) == 5
    assert len(profile["selection"]) == 6
