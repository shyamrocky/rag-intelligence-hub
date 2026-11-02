"""Actual native gateways plus untrusted transport controls; no relevance labels."""

import copy
import json
import shutil
from pathlib import Path

import pytest

from tools.evidence.contract import M7_SELECTOR, M7_SHA, load_configuration, validate_candidates
from tools.evidence.service import EvidenceIntegrityError, EvidenceService
from tools.indexing.m5_index import encoded, sha
from tools.retrieval.contract import fuse
from tools.retrieval.service import RetrievalService

ROOT = Path(__file__).resolve().parents[3]
SELECTOR = "config/evidence-reconstruction-m8-v1.json"
SHA = sha((ROOT / SELECTOR).read_bytes())


@pytest.fixture(scope="session")
def service():
    return EvidenceService(ROOT, selector=SELECTOR, selector_sha256=SHA)


@pytest.fixture(scope="session")
def retrieval():
    value = RetrievalService(ROOT, selector=M7_SELECTOR, selector_sha256=M7_SHA)
    yield value
    value.close()


@pytest.fixture(scope="session")
def sample():
    # Actual accepted M7 delivery, source-free candidate metadata only.
    return json.loads((ROOT / "workspace/rag-implementation/v1/m7-hybrid-v1/CANDIDATE_EXAMPLE.json").read_bytes())


def transport(service, sample, cids):
    """Machine control using exact authorized IDs; never called a live search attestation."""
    value = copy.deepcopy(sample)
    hits = [{"chunk_id": cid, **service.inventory[cid], "rank": i, "score": float(len(cids) - i)}
            for i, cid in enumerate(sorted(cids), 1)]
    value.update(retrieval_mode="bm25", query_sha256=sha(b"M8_SOURCE_BINDING_CONTROL"),
        parameters={"top_k": max(1, len(cids)), "candidate_depth": max(1, len(cids)),
                    "rrf_k": 60, "filters": {}}, diagnostics={"origin": "MACHINE_CONTRACT_CONTROL"})
    value["candidates"] = fuse({"bm25": hits}, mode="bm25", top_k=max(1, len(cids)),
                               rrf_k=60, inventory=service.inventory, filters={})
    return value


@pytest.fixture(scope="session")
def single(service, sample):
    return transport(service, sample, [sample["candidates"][0]["chunk_id"]])


@pytest.fixture(scope="session")
def package(service, single):
    return service.assemble(single, token_budget=100000)


def test_complete_inventory_and_selected_chain(service):
    summary = service.corpus.catalog.get_corpus_summary()
    assert summary["documents"] == 16 and summary["sections"] == 3040
    assert summary["units"] == 553
    assert len(service.inventory) == len(service.artifacts.records) == 992
    assert not any(p.startswith(("workspace/", "archive/", "releases/")) for p in service.files)
    assert len(service.catalog.outcomes()) == 553


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid"])
def test_actual_live_m7_modes(service, retrieval, mode):
    result = retrieval.search("reciprocal rank fusion", mode=mode, top_k=2, candidate_depth=8,
                              filters={"document_id": "C10"})
    package = service.assemble(result, token_budget=100000)
    assert package["status"] == "VERIFIED_EVIDENCE"
    assert package["counts"]["candidates"] == len(result["candidates"])
    assert package["retrieval"]["mode"] == mode
    for item in package["parents"]:
        parent = item["evidence"]["verified_parent"]
        assert service.corpus.evidence.validate(parent)
        assert parent["citation_locators"]
        assert all(x["kind"] == "SOURCE_CONTENT" for x in parent["consumer"]["llm_context"]["source_content"])


def test_single_parent_deterministic_and_citations(service, single, package):
    assert package == service.assemble(single, token_budget=100000)
    assert package["counts"] == {"candidates": 1, "distinct_parents": 1,
                                  "selected_parents": 1, "omitted_parents": 0}
    block = package["parents"][0]["evidence"]
    view = service.artifacts.open_bound_chunk(single["candidates"][0]["chunk_id"])
    assert block["verified_parent"] == view["verified_parent"]
    assert block["citation_precision"]["contributing_chunks"][0]["lineage"] == view["chunk"]["lineage"]
    assert block["complete_parent_required"] is True


def test_five_chunks_one_parent_dedup(service, sample):
    rows = service.catalog.list_chunks(limit=1000)["items"]
    groups = {}
    for row in rows:
        groups.setdefault(row["unit_id"], []).append(row["chunk_id"])
    ids = next(ids[:5] for ids in groups.values() if len(ids) >= 5)
    result = transport(service, sample, ids)
    p = service.assemble(result, token_budget=100000)
    assert p["counts"]["distinct_parents"] == p["counts"]["selected_parents"] == 1
    assert len(p["diagnostics"]["deduplicated"]) == 4
    assert {c["chunk_id"] for c in p["parents"][0]["evidence"]["contributing_candidates"]} == set(ids)


def test_multiple_parents_rank_order(service, sample):
    p = service.assemble(sample, token_budget=100000)
    ranks = [min(c["rank"] for c in i["evidence"]["contributing_candidates"]) for i in p["parents"]]
    assert len(p["parents"]) > 1 and ranks == sorted(ranks)


def test_exact_boundary_and_one_token_short(service, single, package):
    n = package["parents"][0]["token_count"]
    exact = service.assemble(single, token_budget=n)
    insufficient = service.assemble(single, token_budget=n - 1)
    assert exact["status"] == "VERIFIED_EVIDENCE"
    assert exact["budget"]["exact_llm_evidence_tokens"] == n
    assert insufficient["status"] == "INSUFFICIENT_EVIDENCE_FOR_BUDGET"
    assert not insufficient["parents"] and not insufficient["llm_evidence"]
    assert insufficient["diagnostics"]["omitted"][0]["partial_parent_returned"] is False


def test_budget_skips_atomic_parent_retains_later_fit(service, sample):
    full = service.assemble(sample, token_budget=100000)
    smallest = min(p["token_count"] for p in full["parents"])
    p = service.assemble(sample, token_budget=smallest)
    assert p["counts"]["omitted_parents"] > 0
    assert p["counts"]["selected_parents"] >= 1
    assert p["budget"]["exact_llm_evidence_tokens"] <= smallest
    assert all(not o["partial_parent_returned"] for o in p["diagnostics"]["omitted"])


@pytest.mark.parametrize("budget", [0, -1, True, 1.5, "1000", None, 1000001])
def test_invalid_budget_not_a_no_results_outcome(service, single, budget):
    with pytest.raises(EvidenceIntegrityError):
        service.assemble(single, token_budget=budget)


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid"])
def test_empty_actual_search(service, retrieval, mode):
    result = retrieval.search("", mode=mode)
    p = service.assemble(result, token_budget=1)
    assert p["status"] == "NO_RETRIEVAL_CANDIDATES"
    assert p["counts"]["selected_parents"] == 0 and p["budget"]["exact_llm_evidence_tokens"] == 0


@pytest.mark.parametrize("field,value", [
    ("schema", "historical"), ("authority", "APPROVED"),
    ("complete_parent_rehydration_required", False), ("release_identity", "0" * 64),
    ("selection", {}), ("index_release_bindings", {}), ("query_sha256", "fake"),
    ("retrieval_mode", "unknown"), ("parameters", {}), ("candidates", {}),
])
def test_forged_envelope(service, sample, field, value):
    p = copy.deepcopy(sample); p[field] = value
    with pytest.raises(EvidenceIntegrityError):
        service.assemble(p, token_budget=100000)


@pytest.mark.parametrize("field,value", [
    ("chunk_id", "rc:historical:forged"), ("document_id", "C04"), ("format", "pdf"),
    ("reference_classification", "HOLD"), ("rank", 2), ("rank", True),
    ("complete_parent_rehydration_required", False), ("contributing_retrievers", ["fake"]),
    ("rrf_score", 2.0), ("vector_distance", -1), ("vector_distance", float("nan")),
    ("vector_rank", 0), ("bm25_rank", True), ("retrieval_mode", "vector"),
])
def test_forged_candidate(service, sample, field, value):
    p = copy.deepcopy(sample); p["candidates"][0][field] = value
    with pytest.raises(EvidenceIntegrityError):
        service.assemble(p, token_budget=100000)


@pytest.mark.parametrize("field", ["text", "verified_parent", "source_content", "unit_id", "source_slice"])
def test_detached_payload_never_used(service, sample, field):
    p = copy.deepcopy(sample); p["candidates"][0][field] = "forged source content"
    with pytest.raises(EvidenceIntegrityError):
        service.assemble(p, token_budget=100000)


def test_duplicate_conflicting_candidates(service, sample):
    p = copy.deepcopy(sample)
    p["candidates"][1] = copy.deepcopy(p["candidates"][0]); p["candidates"][1]["rank"] = 2
    with pytest.raises(EvidenceIntegrityError):
        service.assemble(p, token_budget=100000)


@pytest.mark.parametrize("kind", ["source", "context", "qualification", "citations", "precision", "llm_text", "count", "parent", "expiry"])
def test_modified_or_stripped_package_rejected(service, single, package, kind):
    p = copy.deepcopy(package); b = p["parents"][0]["evidence"]
    context = b["verified_parent"]["consumer"]["llm_context"]
    if kind == "source": context["source_content"] = [{"kind": "SOURCE_CONTENT", "text": "invented"}]
    if kind == "context": context["required_context"] = []
    if kind == "qualification": context["qualification"] = {}
    if kind == "citations": b["verified_parent"]["citation_locators"] = []
    if kind == "precision": b["citation_precision"]["parent"] = "EXACT_GLYPH_COORDINATES"
    if kind == "llm_text": p["llm_evidence"] = "bare detached fragment"
    if kind == "count": p["budget"]["exact_llm_evidence_tokens"] = 0
    if kind == "parent": b["unit_id"] = "forged"
    if kind == "expiry": b["verified_parent"]["consumer"]["publication_expiration"] = {"status": "VALID"}
    with pytest.raises(EvidenceIntegrityError):
        service.validate(p, single)


def test_valid_serialize_rechecks_and_no_detached_package_input(service, single, package):
    assert service.serialize(package, single) == encoded(package)
    with pytest.raises(EvidenceIntegrityError):
        service.assemble(package, token_budget=100000)


@pytest.fixture(scope="session")
def clone(tmp_path_factory, service):
    root = tmp_path_factory.mktemp("m8-disposable-bindings")
    for name in service.files:
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, p)
    return root


@pytest.mark.parametrize("name", [SELECTOR, M7_SELECTOR, "config/pdf-durable-admission-publication-v1.json",
    "config/unified-durable-selection-v1.json", "config/retrieval-chunks-m3-durable-v1.json",
    "config/embedding-artifacts-m4-durable-v1.json", "config/vector-index-m5-v1-1.json",
    "config/keyword-index-m6-v1.json", "config/bge-tokenizer-v1.json", "tools/evidence/service.py"])
def test_mutated_binding_disposable_copy_fails(clone, name):
    p = clone / name; original = p.read_bytes()
    try:
        p.write_bytes(original + b" ")
        with pytest.raises(ValueError):
            load_configuration(clone, SELECTOR, SHA)
    finally:
        p.write_bytes(original)


def test_missing_index_file_fails_not_empty(clone):
    name = "config/keyword-index-m6-v1.json"
    p = clone / name; old = p.read_bytes(); p.unlink()
    try:
        with pytest.raises((ValueError, OSError)):
            load_configuration(clone, SELECTOR, SHA)
    finally:
        p.write_bytes(old)


def test_stale_result_lease_after_component_change(service, clone):
    from tools.retrieval.contract import check_files

    check_files(clone, service.files)
    p = clone / "tools/evidence/token_worker.py"; old = p.read_bytes()
    try:
        p.write_bytes(old + b"# altered\n")
        with pytest.raises(ValueError):
            check_files(clone, service.files)
    finally:
        p.write_bytes(old)


@pytest.mark.parametrize("did", ["C04", "C06", "C10", "C14"])
def test_special_scopes_exact_native_content(service, sample, did):
    rows = service.catalog.list_chunks(did, limit=1000)["items"]
    if did == "C04":
        rows = [r for r in rows if service.catalog.manifest["configurations"][r["configuration_id"]].get(
                "schema") == "m3-qualified-config-1.0"]
    elif did == "C10":
        rows = [r for r in rows if r["chunk_id"] == sample["candidates"][0]["chunk_id"]]
    ids = list(dict.fromkeys(r["unit_id"] for r in rows))
    # All four protected C04 units; representative other native scopes.
    chosen = [next(r["chunk_id"] for r in rows if r["unit_id"] == uid) for uid in ids[:4 if did == "C04" else 1]]
    p = service.assemble(transport(service, sample, chosen), token_budget=100000)
    assert p["counts"]["selected_parents"] == len(chosen)
    for item in p["parents"]:
        b = item["evidence"]; parent = b["verified_parent"]
        assert service.corpus.evidence.validate(parent)
        assert parent["consumer"]["llm_context"]["qualification"]["mandatory"]
        assert parent["citation_locators"]
        if did == "C04":
            source = parent["consumer"]["llm_context"]["source_content"]
            assert source[0]["restricted_projection"]["consumable_text"]
            assert parent["consumer"]["llm_context"]["qa_observations"]


def test_source_and_qa_never_flattened(package):
    for item in package["parents"]:
        context = item["evidence"]["verified_parent"]["consumer"]["llm_context"]
        assert isinstance(context["source_content"], list)
        assert all(o["kind"] == "QA_OBSERVATION" for o in context["qa_observations"])
        assert context["qualification"]["kind"] == "QUALIFICATION"


def test_raw_input_extra_root_field_rejected(service, sample):
    p = copy.deepcopy(sample); p["source_text"] = "not evidence"
    with pytest.raises(EvidenceIntegrityError): service.assemble(p, token_budget=100000)


def test_contract_rejects_authorized_id_with_conflicting_rank(service, sample):
    p = copy.deepcopy(sample); p["candidates"].reverse()
    with pytest.raises(ValueError): validate_candidates(p, service.m7, service.inventory)


def test_C14_bibliography_and_three_appendices_remain_separate(service, sample):
    native_ids = ['3e2beb72996c1337f96faee2', 'd2cdf35ce50452daa3e6181b',
                  '2264d5177709cb80a8c67762', '927c731b2d70ec0478a3f01f']
    rows = service.catalog.list_chunks('C14', limit=1000)['items']
    cids = [next(r['chunk_id'] for r in rows if r['unit_id'].endswith(s)) for s in native_ids]
    p = service.assemble(transport(service, sample, cids), token_budget=1000000)
    assert p['counts']['selected_parents'] == 4
    for item in p['parents']:
        parent = item['evidence']['verified_parent']
        q = parent['consumer']['llm_context']['qualification']
        text = json.dumps(q).lower()
        if parent['unit_id'].endswith(native_ids[0]):
            assert 'bibliographic attribution only' in text
        else:
            assert 'appendix research narrative only' in text
            assert 'bibliographic attribution only' not in text


def test_expired_PDF_is_informational_but_not_strippable(service, sample):
    row = next(r for r in service.catalog.list_chunks('C06', limit=1000)['items']
               if 'pdf-preserved:C06-candidate-b00030' in r['unit_id'])
    result = transport(service, sample, [row['chunk_id']])
    p = service.assemble(result, token_budget=100000)
    parent = p['parents'][0]['evidence']['verified_parent']
    expiration = parent['consumer']['publication_expiration']
    assert expiration['status'] == 'EXPIRED' and expiration['warning']
    assert any(o.get('issue_id') == 'PDF_PUBLICATION_EXPIRED'
               for o in parent['consumer']['llm_context']['qa_observations'])
    altered = copy.deepcopy(p)
    altered['parents'][0]['evidence']['verified_parent']['consumer'].pop('publication_expiration')
    with pytest.raises(EvidenceIntegrityError): service.validate(altered, result)


def test_C10_qualified_table_RRF_context_and_QA_origin(service, sample):
    source = json.loads((ROOT / 'data/indexes/m5-chroma-v1/verified-inputs.json').read_bytes())
    cid = source['rows'][0]['id']
    assert source['rows'][0]['metadata']['document_id'] == 'C10'
    p = service.assemble(transport(service, sample, [cid]), token_budget=100000)
    context = p['parents'][0]['evidence']['verified_parent']['consumer']['llm_context']
    assert any(x.get('table') for x in context['source_content'])
    assert context['required_context']
    assert any('scor' in json.dumps(o).lower() and o['kind'] == 'QA_OBSERVATION'
               for o in context['qa_observations'])
    assert context['qualification']['mandatory']


def test_C06_benchmark_attribution_is_retained(service, sample):
    row = next(r for r in service.catalog.list_chunks('C06', limit=1000)['items']
               if 'pdf-preserved:C06-candidate-b00030' in r['unit_id'])
    p = service.assemble(transport(service, sample, [row['chunk_id']]), token_budget=100000)
    parent = p['parents'][0]['evidence']['verified_parent']
    native = service.corpus.evidence.get_verified_unit(row['unit_id'])
    assert parent['consumer']['llm_context']['qualification'] == native['consumer']['llm_context']['qualification']
    assert parent['consumer']['llm_context']['required_context'] == native['consumer']['llm_context']['required_context']
    assert parent['publication_identity'] == native['publication_identity']


def test_HOLD_and_excluded_sections_have_no_candidate_authority(service, sample):
    for status in ['HOLD', 'EXCLUDED']:
        sections = service.corpus.catalog.list_sections(filters={'admission_status': status}, limit=1)['items']
        sid = sections[0]['section_id']
        assert not service.catalog.get_section_chunks(sid)
        result = copy.deepcopy(sample)
        result['candidates'][0]['chunk_id'] = sid
        with pytest.raises(EvidenceIntegrityError): service.assemble(result, token_budget=100000)


def test_large_bibliography_is_omitted_intact_under_small_budget(service, sample):
    row = next(r for r in service.catalog.list_chunks('C14', limit=1000)['items']
               if r['unit_id'].endswith('3e2beb72996c1337f96faee2'))
    result = transport(service, sample, [row['chunk_id']])
    p = service.assemble(result, token_budget=384)
    assert p['status'] == 'INSUFFICIENT_EVIDENCE_FOR_BUDGET'
    assert p['diagnostics']['omitted'][0]['reason'] == 'PARENT_EXCEEDS_TOTAL_BUDGET'
    assert not p['llm_evidence'] and not p['parents']
