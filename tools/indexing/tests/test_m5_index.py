"""Actual local Chroma controls; negative mutations affect disposable copies only."""

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from m5_index import (
    FIELDS,
    build,
    client,
    encoded,
    exclusive,
    expected,
    inspect,
    local,
    metadata,
    sha,
)

ROOT = Path(__file__).resolve().parents[3]
PAYLOAD = "data/indexes/m5-chroma-v1/verified-inputs.json"
SELECTOR = "config/vector-index-m5-v1-1.json"


def selector_hash(name=SELECTOR):
    return sha((ROOT / name).read_bytes())


@pytest.fixture(scope="session")
def payload():
    return json.loads((ROOT / PAYLOAD).read_bytes())


def test_exact_full_inventory(payload):
    rows, matrix = expected(ROOT, payload)
    actual = inspect(ROOT, SELECTOR, selector_hash())
    assert actual["records"] == len(rows) == 992
    assert len({r["metadata"]["unit_id"] for r in rows}) == 553
    assert len(actual["document_counts"]) == 16
    assert matrix.shape == (992, 384)
    assert actual["complete_parent_rehydration_required"] is True


def test_restart_exact_lookup_and_filter(payload):
    first = payload["rows"][0]
    command = [sys.executable, str(ROOT / "tools/indexing/m5_index.py"), "inspect",
               "--root", str(ROOT), "--selector", SELECTOR,
               "--selector-sha256", selector_hash(), "--chunk-id", first["id"],
               "--document", first["metadata"]["document_id"]]
    a = json.loads(subprocess.check_output(command, text=True))
    b = json.loads(subprocess.check_output(command, text=True))
    assert a["exact_record"] == b["exact_record"] == {
        "chunk_id": first["id"], "metadata": first["metadata"]}
    assert a["identity"] == b["identity"]
    assert a["matching_records"] == b["matching_records"] == 1


@pytest.mark.parametrize("did", ["C01", "C02", "C04", "C06", "C10", "C14", "C16"])
def test_metadata_filter(did, payload):
    value = inspect(ROOT, SELECTOR, selector_hash(), document=did)
    assert value["matching_records"] == sum(r["metadata"]["document_id"] == did
                                            for r in payload["rows"])


def test_repeat_build_is_verified_no_upsert():
    before = (ROOT / SELECTOR).read_bytes()
    value = build(ROOT, PAYLOAD, SELECTOR)
    assert value["repeated_build"] == "VERIFIED_UNCHANGED"
    assert (ROOT / SELECTOR).read_bytes() == before


@pytest.mark.parametrize("change", ["missing", "extra", "vector", "metadata", "text",
                                    "uri", "collection", "same_count_id", "parent_flag",
                                    "publication", "integer_parent_flag"])
def test_corruption_rejected(change, tmp_path, payload):
    selected = json.loads((ROOT / SELECTOR).read_bytes())
    original_manifest = ROOT / selected["manifest_path"]
    destination = ROOT / "data/indexes/m5-chroma-v1" / ("negative-" + tmp_path.name)
    shutil.copytree(original_manifest.parent, destination)
    new_selector = destination / "selection.json"
    selected["manifest_path"] = str((destination / "manifest.json").relative_to(ROOT))
    new_selector.write_bytes(encoded(selected))
    manifest = json.loads((destination / "manifest.json").read_bytes())
    db = client(destination / "chroma")
    row = payload["rows"][0]
    try:
        c = db.get_collection(manifest["collection"], embedding_function=None)
        if change == "missing":
            c.delete(ids=[row["id"]])
        elif change == "extra":
            c.add(ids=["UNAUTHORIZED"], embeddings=[np.ones(384).tolist()],
                  metadatas=[row["metadata"]])
        elif change == "vector":
            c.update(ids=[row["id"]], embeddings=[np.zeros(384).tolist()])
        elif change == "metadata":
            c.update(ids=[row["id"]], metadatas=[{**row["metadata"], "raw_text": "forbidden"}])
        elif change == "text":
            c.update(ids=[row["id"]], documents=["not authorized inside the index"],
                     embeddings=[np.ones(384).tolist()])
        elif change == "uri":
            c.update(ids=[row["id"]], uris=["file:///forbidden"])
        elif change == "same_count_id":
            c.delete(ids=[row["id"]])
            c.add(ids=["UNAUTHORIZED"], embeddings=[np.ones(384).tolist()],
                  metadatas=[row["metadata"]])
            assert c.count() == 992
        elif change == "parent_flag":
            c.update(ids=[row["id"]], metadatas=[{"complete_parent_rehydration_required": False}])
        elif change == "integer_parent_flag":
            c.update(ids=[row["id"]], metadatas=[{"complete_parent_rehydration_required": 1}])
        elif change == "publication":
            c.update(ids=[row["id"]], metadatas=[{"publication_sha256": "0" * 64}])
        else:
            c.modify(metadata={"schema": "wrong"})
    finally:
        db.close()
    diagnostic = {
        "missing": "m5_wrong_record_count", "extra": "m5_wrong_record_count",
        "same_count_id": "m5_missing_extra_duplicate_ids",
        "vector": "m5_vector_association_changed", "collection": "m5_incompatible_collection",
    }.get(change, "m5_unsupported_or_changed_payload")
    try:
        with pytest.raises(ValueError, match="^" + diagnostic + "$"):
            inspect(ROOT, str(new_selector.relative_to(ROOT)), sha(new_selector.read_bytes()))
    finally:
        shutil.rmtree(destination)  # Only the copy created by this test.


@pytest.mark.parametrize("field", ["unit_id", "qualification_sha256", "row_index",
                                   "input_text_sha256", "token_ids_sha256"])
def test_forged_export_rejected(field, payload):
    forged = copy.deepcopy(payload)
    forged["rows"][0]["metadata"][field] = "forged"
    with pytest.raises(ValueError, match="not_exact_accepted_inventory"):
        expected(ROOT, forged)


def test_duplicate_export_rejected(payload):
    forged = copy.deepcopy(payload)
    forged["rows"][1] = forged["rows"][0]
    with pytest.raises(ValueError, match="not_exact_accepted_inventory"):
        expected(ROOT, forged)


def test_wrong_upstream_no_historical_fallback(payload):
    forged = copy.deepcopy(payload)
    forged["bindings"]["config/retrieval-chunks-m3-durable-v1.json"] = "0" * 64
    with pytest.raises(ValueError, match="wrong_upstream_selection"):
        expected(ROOT, forged)


def test_wrong_selector_hash():
    with pytest.raises(ValueError, match="binding_changed"):
        inspect(ROOT, SELECTOR, "0" * 64)


@pytest.mark.parametrize("kwargs,error", [({"chunk_id": "UNAUTHORIZED"}, "unknown_chunk"),
                                         ({"document": "C99"}, "unknown_document")])
def test_unknown_inventory_rejected(kwargs, error):
    with pytest.raises(ValueError, match=error):
        inspect(ROOT, SELECTOR, selector_hash(), **kwargs)


def test_missing_explicit_selection_fails():
    p = subprocess.run([sys.executable, str(ROOT / "tools/indexing/m5_index.py"), "inspect",
                        "--root", str(ROOT), "--selector", SELECTOR],
                       capture_output=True, text=True, check=False)
    assert p.returncode == 1 and "explicit_selector_hash_required" in p.stdout


def test_network_denial_positive_control():
    program = ("import sys;sys.path.insert(0,'tools/indexing');"
               "from m5_index import no_network;no_network();"
               "import socket;socket.getaddrinfo('example.com',443)")
    p = subprocess.run([sys.executable, "-c", program], cwd=ROOT,
                       capture_output=True, text=True, check=False)
    assert p.returncode != 0 and "m5_network_denied" in p.stderr


def test_duplicate_native_ids_rejected(tmp_path):
    import chromadb.errors

    db = client(tmp_path)
    try:
        c = db.create_collection("negative-duplicates", embedding_function=None)
        with pytest.raises(chromadb.errors.DuplicateIDError):
            c.add(ids=["same", "same"], embeddings=[np.ones(384).tolist()] * 2)
    finally:
        db.close()


def test_dimension_native_rejection(tmp_path):
    import chromadb.errors

    db = client(tmp_path)
    try:
        c = db.create_collection("negative-dimensions", embedding_function=None)
        c.add(ids=["a"], embeddings=[np.ones(384).tolist()])
        with pytest.raises(chromadb.errors.InvalidArgumentError):
            c.add(ids=["b"], embeddings=[[1.0, 2.0]])
    finally:
        db.close()


def test_lock_excludes_second_writer(tmp_path):
    with exclusive(tmp_path / "lock"), pytest.raises(FileExistsError), exclusive(tmp_path / "lock"):
        pass
    assert not (tmp_path / "lock").exists()


@pytest.mark.parametrize("name", ["../outside", "/outside"])
def test_escape_paths_rejected(tmp_path, name):
    with pytest.raises(ValueError, match="unsafe_path"):
        local(tmp_path, name)


def test_metadata_schema_does_not_store_source_text(payload):
    for row in payload["rows"]:
        assert set(row["metadata"]) == FIELDS
        assert row["metadata"]["complete_parent_rehydration_required"] is True
    assert hashlib.sha256(encoded(payload)).hexdigest() == sha(encoded(payload))


def test_metadata_missing_parent_requirement():
    with pytest.raises((KeyError, ValueError)):
        metadata({"complete_parent_rehydration_required": False}, "a", "b")


@pytest.mark.parametrize("field,value", [("schema", "unsupported-2.0"),
                                        ("identity", "0" * 64),
                                        ("collection", "legacy-unqualified"),
                                        ("records", 991)])
def test_rehashed_incompatible_manifest_rejected(tmp_path, field, value):
    selected = json.loads((ROOT / SELECTOR).read_bytes())
    manifest = json.loads((ROOT / selected["manifest_path"]).read_bytes())
    manifest[field] = value
    directory = ROOT / "data/indexes/m5-chroma-v1" / ("manifest-control-" + tmp_path.name)
    directory.mkdir()
    try:
        (directory / "manifest.json").write_bytes(encoded(manifest))
        selected["manifest_path"] = str((directory / "manifest.json").relative_to(ROOT))
        selected["manifest_sha256"] = sha(encoded(manifest))
        path = directory / "selection.json"
        path.write_bytes(encoded(selected))
        with pytest.raises(ValueError, match="release_incompatible"):
            inspect(ROOT, str(path.relative_to(ROOT)), sha(path.read_bytes()))
    finally:
        shutil.rmtree(directory)


def test_missing_installed_release_does_not_fall_back(tmp_path):
    selection = (ROOT / SELECTOR).read_bytes()
    (tmp_path / "selector.json").write_bytes(selection)
    with pytest.raises(FileNotFoundError):
        inspect(tmp_path, "selector.json", sha(selection))


def test_workspace_binding_rejected(payload):
    forged = copy.deepcopy(payload)
    forged["bindings"]["workspace/forbidden.json"] = "0" * 64
    with pytest.raises(ValueError, match="workspace_runtime_dependency"):
        expected(ROOT, forged)
