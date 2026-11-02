"""Real pinned corpus and library controls; mutations touch disposable copies only."""

import contextlib
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.indexing.m5_index import encoded, local, sha
from tools.lexical.bindings import validate_payload
from tools.lexical.bm25_index import BM25Index, build, parameters, policy, tokenize

ROOT = Path(__file__).resolve().parents[3]
SELECTOR = "config/keyword-index-m6-v1.json"
PAYLOAD = "data/indexes/m6-bm25-v1/verified-inputs.json"


@pytest.fixture(scope="session")
def payload():
    return json.loads((ROOT / PAYLOAD).read_bytes())


@pytest.fixture(scope="session")
def index():
    return BM25Index(ROOT, selector=SELECTOR, selector_sha256=sha((ROOT / SELECTOR).read_bytes()))


@pytest.fixture(scope="session")
def isolated(tmp_path_factory, index):
    target = tmp_path_factory.mktemp("m6-private-clone")
    for name in index._files:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    yield target


@contextlib.contextmanager
def replace(path, raw):
    before = path.read_bytes()
    try:
        path.write_bytes(raw)
        yield
    finally:
        path.write_bytes(before)


def open_index(root):
    return BM25Index(root, selector=SELECTOR, selector_sha256=sha((root / SELECTOR).read_bytes()))


def test_exact_inventory(index, payload):
    report = index.inspect()
    _, rows = validate_payload(ROOT, payload)
    assert report["records"] == len(rows) == 992
    assert {r["chunk_id"] for r in rows} == {r["metadata"]["chunk_id"] for r in index._rows}
    assert len({r["unit_id"] for r in rows}) == 553
    assert len(report["document_counts"]) == 16
    assert report["complete_parent_rehydration_required"] is True
    assert all(set(r) == {"metadata", "tokens", "lexical_tokens_sha256"} for r in index._rows)


@pytest.mark.parametrize("query", ["BM25", "RRF", "ChromaDB", "GraphRAG", "RAG",
    "retrieval augmented generation", "all-MiniLM-L6-v2", "retrieval-augmented",
    "similarity_search", "400M", "0.25", "C++", "Precision_Ω"])
def test_representative_queries_deterministic_and_authorized(query, index):
    a = index.search(query, top_k=25)
    assert a == index.search(query, top_k=25)
    allowed = {r["metadata"]["chunk_id"] for r in index._rows}
    hits = a["candidates"]
    assert all(h["chunk_id"] in allowed for h in hits)
    assert [h["rank"] for h in hits] == list(range(1, len(hits) + 1))
    assert hits == sorted(hits, key=lambda r: (-r["score"], r["chunk_id"]))
    assert all(set(h) == {"chunk_id", "score", "rank", "document_id", "format",
                          "reference_classification"} for h in hits)
    assert "text" not in encoded(a).decode()


@pytest.mark.parametrize("query", ["", "   ", "()[]!!!", "zzzxnotinthecorpus918729"])
def test_empty_or_no_match(query, index):
    assert index.search(query)["candidates"] == []


def test_case_whitespace_and_punctuation(index):
    assert index.search("BM25!") == index.search("  bm25  ")


@pytest.mark.parametrize("value", [0, -1, 993, True, 1.5, "5", None])
def test_invalid_top_k(value, index):
    with pytest.raises(ValueError, match="top_k"):
        index.search("rag", top_k=value)


@pytest.mark.parametrize("value", [None, 3, ["rag"], {"query": "rag"}])
def test_invalid_query(value, index):
    with pytest.raises(TypeError, match="must_be_text"):
        index.search(value)


@pytest.mark.parametrize("filters", [{"document_id": "C99"}, {"format": "exe"},
    {"reference_classification": "UNRESTRICTED"}, {"admission_status": "HOLD"},
    {"section_id": "forged"}, {"unit_id": "forged"}, {"document_id": ["C01"]}, []])
def test_invalid_filters(filters, index):
    with pytest.raises(ValueError, match="filter"):
        index.search("rag", filters=filters)


@pytest.mark.parametrize("did", ["C01", "C02", "C04", "C06", "C10", "C14", "C16"])
def test_authorized_document_filters(did, index):
    result = index.search("the", top_k=992, filters={"document_id": did})
    assert all(r["document_id"] == did for r in result["candidates"])


def test_classification_filter_does_not_reclassify(index):
    for classification in {r["metadata"]["reference_classification"] for r in index._rows}:
        result = index.search("rag", filters={"reference_classification": classification})
        assert all(r["reference_classification"] == classification for r in result["candidates"])


def test_technical_token_contract():
    config = policy(ROOT)
    tokens = tokenize("BM25 RRF GraphRAG ChromaDB all-MiniLM-L6-v2 foo_bar obj.method C++ C# -0.25 93.4%", config)
    assert tokens == ["bm25", "rrf", "graphrag", "chromadb", "all-minilm-l6-v2",
        "all", "minilm", "l6", "v2", "foo_bar", "obj.method", "obj", "method",
        "c++", "c#", "-0.25", "93.4%"]
    assert tokenize("A  the AND", config) == ["a", "the", "and"]
    assert tokenize("\n\t", config) == []


def test_library_short_empty_and_negative_scores():
    config = policy(ROOT)
    engine = parameters([["same"], ["same"], []], config)
    scores = engine.get_scores(["same"])
    assert len(scores) == 3 and scores[0] == scores[1]
    assert scores[2] == 0  # Empty documents remain in the corpus.
    with pytest.raises(ValueError, match="empty_lexical_corpus"):
        parameters([[], []], config)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "historical", "text", "hold",
    "excluded", "context_only", "metadata", "qa_text", "wrong_m3", "wrong_m4", "wrong_m5", "fake_count"])
def test_untrusted_export_rejected(mutation, payload):
    bad = copy.deepcopy(payload)
    row = bad["rows"][0]
    if mutation == "missing":
        bad["rows"].pop()
    elif mutation == "duplicate":
        bad["rows"][1] = copy.deepcopy(row)
    elif mutation == "text":
        row["text"] += " altered"
        row["input_text_sha256"] = sha(row["text"].encode())
    elif mutation == "qa_text":
        row["text"] = "QA_OBSERVATION source has known ambiguity"
    elif mutation == "metadata":
        row["forbidden_text"] = "forged"
    elif mutation == "fake_count":
        bad["live_verified_chunks"] = True
    elif mutation.startswith("wrong_"):
        p = {"wrong_m3": "config/retrieval-chunks-m3-durable-v1.json",
             "wrong_m4": "config/embedding-artifacts-m4-durable-v1.json",
             "wrong_m5": "config/vector-index-m5-v1-1.json"}[mutation]
        bad["bindings"][p] = "0" * 64
    elif mutation in {"hold", "excluded"}:
        register = json.loads((ROOT / "data/validation/pdf/residual-recovery-v1/PDF_RESIDUAL_NON_ADMITTED_REGISTER.json").read_bytes())
        row["chunk_id"] = next(s["section_id"] for s in register["sections"]
                               if s["admission_status"] == mutation.upper())
    else:
        row["chunk_id"] = mutation + ":unauthorized-source"
    with pytest.raises(ValueError, match="m6_"):
        validate_payload(ROOT, bad)


@pytest.mark.parametrize("mutation", ["manifest", "index", "payload", "policy", "implementation",
                                      "source", "missing", "wrong_selector"])
def test_corrupt_persistent_files_rejected(mutation, isolated):
    selection = json.loads((isolated / SELECTOR).read_bytes())
    manifest_path = isolated / selection["manifest_path"]
    m = json.loads(manifest_path.read_bytes())
    paths = {"manifest": manifest_path, "index": isolated / m["records_path"],
             "payload": isolated / m["payload_path"], "policy": isolated / "config/bm25-preprocessing-v1.json",
             "implementation": isolated / "tools/lexical/bm25_index.py",
             "source": isolated / next(p for p in m["spec"]["bindings"] if p.endswith(".pdf")),
             "missing": isolated / m["records_path"], "wrong_selector": isolated / SELECTOR}
    path = paths[mutation]
    raw = path.read_bytes()
    if mutation == "missing":
        path.unlink()
        try:
            with pytest.raises((ValueError, OSError)):
                open_index(isolated)
        finally:
            path.write_bytes(raw)
    else:
        with replace(path, raw + b" altered"), pytest.raises((ValueError, OSError)):
            open_index(isolated)


def test_wrong_selector_hash(index):
    with pytest.raises(ValueError, match="binding_changed"):
        BM25Index(ROOT, selector=SELECTOR, selector_sha256="0" * 64)


def test_stale_cached_reader_fails_closed(isolated):
    reader = open_index(isolated)
    path = isolated / SELECTOR
    with replace(path, path.read_bytes() + b" "), pytest.raises(ValueError, match="binding_changed"):
        reader.search("rag")


def test_symlink_and_traversal_rejected(tmp_path):
    (tmp_path / "owned").write_text("owned")
    (tmp_path / "link").symlink_to(tmp_path / "owned")
    for name in ("../escape", "/tmp/foreign", "link"):
        with pytest.raises(ValueError, match="unsafe_path|symlink"):
            local(tmp_path, name)


def test_repeat_build_and_fresh_restart(index):
    value = build(ROOT, PAYLOAD, payload_sha256=sha((ROOT / PAYLOAD).read_bytes()), selector=SELECTOR)
    assert value["repeated_build"] is True
    command = [sys.executable, "-m", "tools.lexical.bm25_index", "search", "--root", str(ROOT),
        "--selector", SELECTOR, "--selector-sha256", sha((ROOT / SELECTOR).read_bytes()),
        "--query", "BM25", "--top-k", "8"]
    a = json.loads(subprocess.check_output(command, cwd=ROOT, text=True))
    b = json.loads(subprocess.check_output(command, cwd=ROOT, text=True))
    a.pop("seconds"); b.pop("seconds")
    assert a == b == index.search("BM25", top_k=8)


def test_incomplete_build_not_published(isolated):
    s = json.loads((isolated / SELECTOR).read_bytes())
    folder = (isolated / s["manifest_path"]).parent
    saved = folder.with_name("saved-for-negative")
    folder.rename(saved)
    (isolated / SELECTOR).unlink()
    try:
        with pytest.raises(ValueError, match="injected_incomplete"):
            build(isolated, PAYLOAD, payload_sha256=sha((isolated / PAYLOAD).read_bytes()),
                  selector=SELECTOR, fail_before_publish=True)
        assert not folder.exists() and not (isolated / SELECTOR).exists()
        assert not list(folder.parent.glob(".build-*"))
    finally:
        saved.rename(folder)
        (isolated / SELECTOR).write_bytes(encoded(s))


def test_rehashed_forged_index_is_not_authority(isolated):
    selected_path = isolated / SELECTOR
    selection = json.loads(selected_path.read_bytes())
    manifest_path = isolated / selection["manifest_path"]
    manifest = json.loads(manifest_path.read_bytes())
    records_path = isolated / manifest["records_path"]
    rows = json.loads(records_path.read_bytes())
    rows[0]["tokens"].append("unauthorized_qa_commentary")
    manifest["spec"]["records_sha256"] = sha(encoded(rows))
    selection["manifest_sha256"] = sha(encoded(manifest))
    with (replace(records_path, encoded(rows)), replace(manifest_path, encoded(manifest)),
          replace(selected_path, encoded(selection)), pytest.raises(ValueError, match="incompatible_release")):
        open_index(isolated)


def test_unsupported_policy_version_rejected(isolated):
    path = isolated / "config/bm25-preprocessing-v1.json"
    config = json.loads(path.read_bytes())
    config["schema"] = "unapproved-next-policy"
    with replace(path, encoded(config)), pytest.raises(ValueError, match="unsupported_tokenizer"):
        policy(isolated)


def test_wrong_runtime_rejected(monkeypatch):
    from tools.lexical.bm25_index import runtime
    monkeypatch.setattr("tools.lexical.bm25_index.platform.python_version", lambda: "3.15.0")
    with pytest.raises(ValueError, match="pinned_python"):
        runtime()


def test_fresh_rebuild_exact_bytes(isolated):
    original_selection = (isolated / SELECTOR).read_bytes()
    selection = json.loads(original_selection)
    folder = (isolated / selection["manifest_path"]).parent
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    backup = folder.with_name("rebuild-witness")
    folder.rename(backup)
    (isolated / SELECTOR).unlink()
    try:
        build(isolated, PAYLOAD, payload_sha256=sha((isolated / PAYLOAD).read_bytes()), selector=SELECTOR)
        assert (isolated / SELECTOR).read_bytes() == original_selection
        assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    finally:
        if folder.exists():
            shutil.rmtree(folder)
        backup.rename(folder)
        (isolated / SELECTOR).write_bytes(original_selection)
