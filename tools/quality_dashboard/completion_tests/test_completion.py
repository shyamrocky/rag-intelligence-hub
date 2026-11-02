"""Sealed local measurement controls; never run retrieval or M8 on dashboard refresh."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from tools.quality_dashboard.artifacts import ArtifactError, digest
from tools.quality_dashboard.completion_adapter import load_completed, validate_measurement
from tools.quality_dashboard.expanded_adapter import load_expanded

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/evals/benchmark-completion/v1"
QUESTIONS = json.loads((OUT / "QUESTIONS_ONLY.json").read_bytes())["questions"]


@pytest.fixture(scope="module")
def completed():
    return load_completed(ROOT)


def read(name):
    return json.loads((OUT / name).read_bytes())


@pytest.mark.parametrize("qid", [q["question_id"] for q in QUESTIONS])
def test_each_measurement_and_exact_configuration(completed, qid):
    row = completed["records"][qid]
    result = read(f"m7/{qid}.json")
    case = read(f"m8/{qid}.json")
    measurement = row["completion"]
    assert measurement and measurement["status"] == "COMPLETE"
    validate_measurement(row["reference"], measurement, result, case)
    assert len(result["candidates"]) == 30
    assert result["query_sha256"] == row["reference"]["question_text_sha256"]
    assert case["budget_accounting"]["truncation"] is False
    assert case["budget_accounting"]["exact_llm_evidence_tokens"] <= 128000
    assert case.get("package_persisted") is False
    if not row["group_ids"]:
        assert measurement["m8"]["delivered_groups"] is None
        assert measurement["m8"]["complete_question"] is None


@pytest.mark.parametrize(
    "field",
    [
        "query",
        "budget",
        "truncation",
        "duplicate_parent",
        "omission",
        "count",
        "hash",
        "label",
        "false_control",
    ],
)
def test_reject_tampered_receipts(completed, field):
    qid = "M9-Q27" if field == "false_control" else "M9-Q02"
    q = completed["records"][qid]["reference"]
    m = copy.deepcopy(completed["records"][qid]["completion"])
    r = read(f"m7/{qid}.json")
    c = read(f"m8/{qid}.json")
    if field == "query":
        r["query_sha256"] = "0" * 64
    elif field == "budget":
        c["budget_accounting"]["limit"] = 129000
    elif field == "truncation":
        c["budget_accounting"]["truncation"] = True
    elif field == "duplicate_parent":
        c["actual_M8_included_parent_ids"].append(c["actual_M8_included_parent_ids"][0])
    elif field == "omission":
        c["omitted"][0]["partial_parent_returned"] = True
    elif field == "count":
        m["m8"]["exact_tokens"] += 1
    elif field == "hash":
        m["M7_result_sha256"] = "0" * 64
    elif field == "label":
        m["required_groups"] += 1
    elif field == "false_control":
        m["m8"]["delivered_groups"] = 0
    with pytest.raises(ArtifactError):
        validate_measurement(q, m, r, c)


def test_counts_and_reuse(completed):
    s = read("RESULTS.json")["summary"]
    assert (s["questions"], s["M7_reused"], s["M7_new"], s["M8_reused"], s["M8_new"]) == (
        34,
        17,
        17,
        15,
        19,
    )
    assert s["required_group_denominator"] == 40 and s["answerable_denominator"] == 31
    assert not s["blocked_question_ids"]
    assert completed["summary"]["M8_target_evaluated_questions"] == 34
    assert len(list((OUT / "native").glob("*.json"))) == 34
    assert not completed["rejected"]


def test_refresh_is_read_only_and_historical_generation_unchanged(completed, monkeypatch):
    import socket

    from tools.evidence.service import EvidenceService
    from tools.retrieval.service import RetrievalService

    def forbidden(*args, **kwargs):
        raise AssertionError("pipeline or network execution forbidden on refresh")

    monkeypatch.setattr(RetrievalService, "search", forbidden)
    monkeypatch.setattr(EvidenceService, "assemble", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    replay = load_completed(ROOT)
    assert digest(replay["completion_publications"]) == digest(completed["completion_publications"])
    old = load_expanded(ROOT)
    for qid in old["records"]:
        assert replay["records"][qid]["latest"] == old["records"][qid]["latest"]
    assert (
        replay["summary"]["generation_completed"] == 1
        and replay["summary"]["pending_generation"] == 33
    )


def test_runtime_has_no_labels_or_generation_imports():
    p = ROOT / "workspace/rag-implementation/v1/benchmark-completion-v1/run.py"
    import ast

    tree = ast.parse(p.read_text())
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any("generation" in name or "ranking" in name for name in imports)
    assert "FROZEN_DATASET" not in p.read_text() and "PROPOSED_EVIDENCE_LABELS" not in p.read_text()


def test_joint_and_and_equivalent_scoring_fixture():
    p = ROOT / "workspace/rag-implementation/v1/evidence-selection-experiment-v1/scoring.py"
    spec = importlib.util.spec_from_file_location("approved_scoring_control", p)
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    label = {
        "required_evidence_groups": [
            {
                "group_id": "g",
                "alternatives": [
                    {"unit_id": "p", "proposed_joint_positive_chunk_ids": ["a", "b"]},
                    {"unit_id": "q", "expected_relevant_chunk_ids": ["c"]},
                ],
            }
        ]
    }
    mapping = {"a": "p", "b": "p", "c": "q"}
    one = scorer.group_outcomes(label, ["a"], mapping, [])[0]
    assert not one["direct_witness_discovered"] and one["parent_located"] and not one["included"]
    assert scorer.group_outcomes(label, ["a", "b"], mapping, ["p"])[0]["included"]
    assert scorer.group_outcomes(label, ["c"], mapping, ["q"])[0]["direct_witness_discovered"]


def test_historical_fifteen_exact_receipts_not_reassembled(completed):
    for q in QUESTIONS:
        if q["M8_origin"] != "REUSE_HISTORICAL":
            continue
        case = read(f"m8/{q['question_id']}.json")
        old = json.loads((ROOT / case["source_path"]).read_bytes())
        assert case["M8_package_sha256"] == old["M8_package_sha256"]
        assert case["budget_accounting"] == old["budget_accounting"]
        assert case["actual_M8_assembly_seconds"] == old["actual_M8_assembly_seconds"]
        assert (
            case["live_compatibility"]
            == "EXACT_M7_BYTES_POLICY_AND_NATIVE_PARENT_OBLIGATIONS_MATCH"
        )


@pytest.mark.parametrize('defect', ['unknown_chunk', 'duplicate_chunk', 'source_metadata', 'wrong_release', 'rrf_score'])
def test_accepted_candidate_contract_fail_closed(defect):
    from tools.evidence.contract import M7_SELECTOR, M7_SHA, validate_candidates
    from tools.retrieval.contract import load_release

    release, _, inventory = load_release(ROOT, M7_SELECTOR, M7_SHA)
    result = read('m7/M9-Q02.json')
    if defect == 'unknown_chunk':
        result['candidates'][0]['chunk_id'] = 'FORGED'
    elif defect == 'duplicate_chunk':
        result['candidates'][1] = copy.deepcopy(result['candidates'][0])
    elif defect == 'source_metadata':
        result['candidates'][0]['document_id'] = 'C99'
    elif defect == 'wrong_release':
        result['release_identity'] = 'historical_wrong_release'
    else:
        result['candidates'][0]['rrf_score'] += 0.001
    with pytest.raises(ValueError):
        validate_candidates(result, release, inventory)


@pytest.mark.parametrize('defect', ['unsealed', 'wrong_status', 'wrong_configuration', 'traversal'])
def test_discovery_rejects_invalid_publication(tmp_path, monkeypatch, defect):
    from tools.quality_dashboard import completion_adapter
    from tools.quality_dashboard.artifacts import Store, sha
    from tools.quality_dashboard.expanded_adapter import MANIFEST_SHA

    target = tmp_path/'data/evals/benchmark-completion/bad'
    target.mkdir(parents=True)
    payload = target/'RESULTS.json'
    payload.write_text('{}')
    manifest = {'schema': 'benchmark-completion-manifest-1.0',
        'status': 'COMPLETED_SEALED_PENDING_OWNER_REVIEW',
        'expanded_benchmark_manifest_sha256': MANIFEST_SHA,
        'configuration': completion_adapter.CONFIGURATION,
        'files': {'RESULTS.json': sha(payload)}, 'input_bindings': {}}
    if defect == 'unsealed':
        manifest['files'] = {}
    elif defect == 'wrong_status':
        manifest['status'] = 'RUNNING'
    elif defect == 'wrong_configuration':
        manifest['configuration'] = {'top_k': 10}
    else:
        manifest['files'] = {'../../../../.env': sha(payload)}
    (target/'MANIFEST.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(completion_adapter, 'load_expanded', lambda root: {
        'store': Store(root), 'records': {}, 'cohorts': [], 'summary': {}, 'rejected': [], 'run_plan': {'questions': []}})
    result = completion_adapter.load_completed(tmp_path)
    assert len(result['rejected']) == 1 and not result['completion_publications']
