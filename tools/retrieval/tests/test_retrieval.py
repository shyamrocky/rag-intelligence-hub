"""Engineering controls, not a human-reviewed retrieval relevance benchmark."""

import copy
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tools.indexing.m5_index import sha
from tools.retrieval.contract import (
    PREFIX,
    fuse,
    load_release,
    native_hits,
    validate_query_vector,
)
from tools.retrieval.service import RetrievalService

ROOT = Path(__file__).resolve().parents[3]
SELECTOR = "config/hybrid-retrieval-m7-v1.json"


def selected(root=ROOT):
    return {"selector": SELECTOR, "selector_sha256": sha((root / SELECTOR).read_bytes())}


@pytest.fixture(scope="session")
def service():
    value = RetrievalService(ROOT, **selected())
    yield value
    value.close()


@pytest.fixture(scope="session")
def clone(tmp_path_factory, service):
    root = tmp_path_factory.mktemp("m7-private-validation")
    for name in service.files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    return root


def stable(result):
    return {k: v for k, v in result.items() if k != "diagnostics"}


def test_exact_inventory_and_authority(service):
    assert len(service.inventory) == 992
    assert len({r["document_id"] for r in service.inventory.values()}) == 16
    assert not any(n.startswith("workspace/") for n in service.files)
    assert service.manifest["spec"]["parents"] == 553


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid"])
@pytest.mark.parametrize("query", ["How does RAG combine retrieval with generation?", "BM25 RRF",
    "all-MiniLM-L6-v2", "retrieval-augmented generation", "similarity_search 400M"])
def test_live_modes_authorized_deterministic(service, mode, query):
    a = service.search(query, mode=mode, top_k=5, candidate_depth=12)
    b = service.search(query, mode=mode, top_k=5, candidate_depth=12)
    assert stable(a) == stable(b)
    assert a["authority"] == "CANDIDATES_ONLY_NOT_AUTHORIZED_EVIDENCE"
    assert a["complete_parent_rehydration_required"] is True
    assert [h["rank"] for h in a["candidates"]] == list(range(1, len(a["candidates"]) + 1))
    assert len({h["chunk_id"] for h in a["candidates"]}) == len(a["candidates"])
    for hit in a["candidates"]:
        assert hit["chunk_id"] in service.inventory
        assert hit["complete_parent_rehydration_required"] is True
        assert "text" not in hit and "source_content" not in hit
        assert hit["rrf_score"] is None if mode != "hybrid" else hit["rrf_score"] > 0
    if mode != "bm25":
        assert a["diagnostics"]["workers"]["query_binding"] == b["diagnostics"]["workers"]["query_binding"]


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid"])
@pytest.mark.parametrize("query", ["", " \n ", "()!!!"])
def test_empty_and_punctuation_no_candidates(service, mode, query):
    assert service.search(query, mode=mode)["candidates"] == []


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid"])
@pytest.mark.parametrize("filters", [{"document_id": "C01"}, {"format": "markdown"},
    {"reference_classification": "ILLUSTRATIVE_REFERENCE"},
    {"document_id": "C04", "format": "pdf"}])
def test_filters_keep_authorized_scope(service, mode, filters):
    result = service.search("retrieval", mode=mode, filters=filters, top_k=3, candidate_depth=6)
    assert all(all(h[k] == v for k, v in filters.items()) for h in result["candidates"])


@pytest.mark.parametrize("params", [{"mode": "unknown"}, {"top_k": 0}, {"top_k": True},
    {"top_k": 993}, {"top_k": 1.5}, {"candidate_depth": 0}, {"candidate_depth": 993},
    {"candidate_depth": 3, "top_k": 5}, {"rrf_k": 0}, {"rrf_k": True}, {"rrf_k": 10001},
    {"filters": {"section_id": "HOLD"}}, {"filters": {"document_id": "C99"}},
    {"filters": {"format": ["pdf"]}}, {"filters": {"reference_classification": "UNRESTRICTED"}},
    {"filters": {"admission_status": "HOLD"}}])
def test_invalid_parameters_fail(service, params):
    with pytest.raises((ValueError, TypeError)):
        service.search("RAG", **params)


@pytest.mark.parametrize("query", [None, 4, ["RAG"], "x" * 16385, "\ud800"])
def test_invalid_queries(service, query):
    with pytest.raises((ValueError, TypeError)):
        service.search(query)


def test_independent_native_distance_oracle(service):
    query = "How do retrievers find relevant passages?"
    packet = service._request("encode", {"query": query})["result"]
    vector = validate_query_vector(packet, query)
    result = service.search(query, mode="vector", top_k=20)
    selection = json.loads((ROOT / "config/embedding-artifacts-m4-durable-v1.json").read_bytes())
    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    matrix = np.load(ROOT / manifest["vectors_path"], allow_pickle=False)
    records = [json.loads(line) for line in (ROOT / manifest["records_path"]).read_text().splitlines()]
    distances = [(float(np.sum((matrix[r["row_index"]] - vector) ** 2)), r["chunk_id"]) for r in records]
    distances.sort()
    assert [h["chunk_id"] for h in result["candidates"]] == [cid for _, cid in distances[:20]]
    assert np.allclose([h["vector_distance"] for h in result["candidates"]],
                       [d for d, _ in distances[:20]], atol=2e-6, rtol=2e-6)


def test_bm25_unchanged_public_api_parity(service):
    selection = service.manifest["spec"]["selections"]["m6"]
    process = subprocess.run([str(ROOT / "tools/lexical/.venv/bin/python"), "-m",
        "tools.lexical.bm25_index", "search", "--root", str(ROOT), "--selector", selection["path"],
        "--selector-sha256", selection["sha256"], "--query", "BM25", "--top-k", "5"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=120)
    original = json.loads(process.stdout)["candidates"]
    result = service.search("BM25", mode="bm25", top_k=5, candidate_depth=5)["candidates"]
    assert [(h["chunk_id"], h["bm25_rank"], h["bm25_score"]) for h in result] == [
        (h["chunk_id"], h["rank"], h["score"]) for h in original]


def test_rrf_live_rank_oracle_and_disagreement(service):
    query = "What is reciprocal rank fusion?"
    lists = {}
    for mode in ["vector", "bm25"]:
        hits = service.search(query, mode=mode, top_k=15, candidate_depth=15)["candidates"]
        lists[mode] = {h["chunk_id"]: h[mode + "_rank"] for h in hits}
    expected = {cid: sum(1 / (60 + rows[cid]) for rows in lists.values() if cid in rows)
                for cid in set().union(*lists.values())}
    ordered = sorted(expected, key=lambda cid: (-expected[cid], cid))[:10]
    result = service.search(query, top_k=10, candidate_depth=15)["candidates"]
    assert [h["chunk_id"] for h in result] == ordered
    assert all(h["rrf_score"] == expected[h["chunk_id"]] for h in result)
    assert list(lists["vector"]) != list(lists["bm25"])


def tiny_inventory():
    return {cid: {"document_id": "C01", "format": "pdf", "reference_classification": "STANDARD_REFERENCE"}
            for cid in ["a", "b", "c"]}


def hit(cid, rank, metric, value):
    return {"chunk_id": cid, "rank": rank, metric: value, **tiny_inventory()[cid]}


def test_rrf_one_list_only_ties_and_deduplication():
    lists = {"vector": [hit("a", 1, "distance", 0.1), hit("b", 2, "distance", 0.2)],
             "bm25": [hit("c", 1, "score", 999999.0), hit("b", 2, "score", -30.0)]}
    result = fuse(lists, mode="hybrid", top_k=3, rrf_k=60, inventory=tiny_inventory(), filters={})
    assert [r["chunk_id"] for r in result] == ["b", "a", "c"]
    assert result[0]["rrf_score"] == 2 / 62
    assert result[1]["rrf_score"] == result[2]["rrf_score"] == 1 / 61
    assert result[1]["contributing_retrievers"] == ["vector"]
    assert result[2]["bm25_score"] == 999999.0


@pytest.mark.parametrize("defect", ["duplicate", "rank", "nan", "metadata", "extra_text", "historical", "order"])
def test_reject_forged_native_lists(defect):
    hits = [hit("a", 1, "distance", 0.1), hit("b", 2, "distance", 0.2)]
    if defect == "duplicate": hits[1]["chunk_id"] = "a"
    if defect == "rank": hits[0]["rank"] = True
    if defect == "nan": hits[0]["distance"] = math.nan
    if defect == "metadata": hits[0]["document_id"] = "C02"
    if defect == "extra_text": hits[0]["text"] = "not evidence"
    if defect == "historical": hits[0]["chunk_id"] = "historical:chunk"
    if defect == "order": hits[0]["distance"] = 0.3
    with pytest.raises(ValueError):
        native_hits(hits, "vector", tiny_inventory(), {})


def test_no_hybrid_fallback():
    with pytest.raises(ValueError, match="no_fallback"):
        fuse({"bm25": []}, mode="hybrid", top_k=3, rrf_k=60, inventory=tiny_inventory(), filters={})


@pytest.mark.parametrize("defect", ["dimension", "nan", "norm", "hash", "query", "policy", "model", "tokens", "extra"])
def test_forged_vector_bridge(service, defect):
    query = "RAG"
    packet = copy.deepcopy(service._request("encode", {"query": query})["result"])
    if defect == "dimension": packet["vector"].pop()
    if defect == "nan": packet["vector"][0] = math.nan
    if defect == "norm": packet["vector"] = [0.0] * 384
    if defect == "hash": packet["vector_sha256"] = "0" * 64
    if defect == "query": packet["query_sha256"] = "0" * 64
    if defect == "policy": packet["policy"] = "document"
    if defect == "model": packet["model_configuration_sha256"] = "0" * 64
    if defect == "tokens": packet["tokens"] = 513
    if defect == "extra": packet["approved_evidence"] = True
    with pytest.raises(ValueError):
        validate_query_vector(packet, query)


@pytest.mark.parametrize("path", [SELECTOR, "config/vector-index-m5-v1-1.json",
    "config/keyword-index-m6-v1.json", "config/unified-durable-selection-v1.json",
    "config/bm25-preprocessing-v1.json", "tools/retrieval/worker.py",
    "config/m4-embedding-baseline-v1.json", "tools/embeddings/uv.lock"])
def test_changed_release_files_fail_closed(clone, path):
    target = clone / path
    raw = target.read_bytes()
    try:
        target.write_bytes(raw + b" ")
        with pytest.raises(ValueError):
            load_release(clone, SELECTOR, sha((ROOT / SELECTOR).read_bytes()))
    finally:
        target.write_bytes(raw)


def test_missing_bm25_record_file_fails(clone):
    s = json.loads((clone / "config/keyword-index-m6-v1.json").read_bytes())
    m = json.loads((clone / s["manifest_path"]).read_bytes())
    target = clone / m["records_path"]
    raw = target.read_bytes()
    try:
        target.unlink()
        with pytest.raises(FileNotFoundError):
            RetrievalService(clone, **selected())
    finally:
        target.write_bytes(raw)


def test_corrupt_chroma_physical_file_fails(clone):
    s = json.loads((clone / SELECTOR).read_bytes())
    m = json.loads((clone / s["manifest_path"]).read_bytes())
    target = clone / next(iter(m["spec"]["vector_store"]["physical_witnesses"]))
    raw = target.read_bytes()
    try:
        target.write_bytes(b"corrupted")
        with pytest.raises(ValueError):
            RetrievalService(clone, **selected())
    finally:
        target.write_bytes(raw)


def test_stale_cached_service_rejected(clone):
    s = RetrievalService(clone, **selected())
    target = clone / "config/keyword-index-m6-v1.json"
    raw = target.read_bytes()
    try:
        target.write_bytes(raw + b" ")
        with pytest.raises(ValueError):
            s.search("BM25", mode="bm25")
    finally:
        target.write_bytes(raw)
        s.close()


def test_over_budget_query_never_truncates():
    s = RetrievalService(ROOT, **selected())
    try:
        with pytest.raises(ValueError, match="over_budget_no_truncation"):
            s.search("retrieval " * 600, mode="vector")
        with pytest.raises(ValueError, match="service_closed"):
            s.search("RAG")
    finally:
        s.close()


def test_dead_worker_no_silent_fallback():
    s = RetrievalService(ROOT, **selected())
    try:
        s.search("BM25", mode="bm25")
        s._workers["bm25"].process.kill()
        s._workers["bm25"].process.wait(timeout=10)
        with pytest.raises(ValueError, match="no_fallback"):
            s.search("RAG", mode="hybrid")
        assert not s._workers
    finally:
        s.close()


def test_fresh_process_repeat(service):
    args = [str(ROOT / ".venv/bin/python"), "-m", "tools.retrieval.service", "--root", str(ROOT),
        "--selector", SELECTOR, "--selector-sha256", selected()["selector_sha256"],
        "--query", "BM25 RRF", "--top-k", "5", "--candidate-depth", "12"]
    fresh = json.loads(subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                    timeout=180, check=True).stdout)
    assert stable(fresh) == stable(service.search("BM25 RRF", top_k=5, candidate_depth=12))
    assert fresh["diagnostics"]["workers"]["query_binding"] == service.search(
        "BM25 RRF", top_k=5, candidate_depth=12)["diagnostics"]["workers"]["query_binding"]


def test_query_instruction_separate_from_documents(service):
    packet = service._request("encode", {"query": "RAG"})["result"]
    assert packet["encoded_text_sha256"] == sha((PREFIX + "RAG").encode())
    config = json.loads((ROOT / "config/m4-embedding-baseline-v1.json").read_bytes())
    assert config["encoding"]["document_prompt"] == ""
