import copy
import json
from pathlib import Path

import pytest

from tools.quality_dashboard.adapter import FREEZE, discover_validations, load_dashboard, metric
from tools.quality_dashboard.artifacts import ArtifactError, Store, sha

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def measured():
    return load_dashboard(ROOT)


def test_frozen_accounting(measured):
    s = measured["summary"]
    assert (s["questions"], s["groups"]) == (15, 22)
    assert (s["m7_direct_groups"], s["m7_parent_groups"], s["m8_groups"]) == (20, 21, 19)
    assert s["m8_complete_questions"] == 12
    assert len({g for r in measured["records"].values() for g in r["group_ids"]}) == 22


def test_actual_generation(measured):
    a = measured["records"]["M9-Q05"]["latest"]
    assert a["response"]["status"] == "ANSWERED"
    assert (a["supplied_parents"], len(a["cited_parent_ids"]), len(a["response"]["claims"])) == (17, 1, 2)
    assert (a["usage"]["input_tokens"], a["usage"]["output_tokens"], a["usage"]["total_tokens"]) == (86200, 848, 87048)
    assert a["usage"]["total_estimated_cost_usd"] == "0.011198925"
    assert a["usage"]["latency_ms"] == pytest.approx(8336.271291947924)
    assert a["response"]["relevant_qualifications"] == []


def test_failed_attempt_and_not_run(measured):
    assert measured["summary"]["failed_attempts"] == 1
    assert measured["summary"]["generated_questions"] == 1
    assert sum(not r["attempts"] for r in measured["records"].values()) == 14
    q05 = measured["records"]["M9-Q05"]
    assert len(q05["attempts"]) == 2
    failed = next(a for a in q05["attempts"] if not a["completed"])
    assert failed["response"] is None
    assert failed["usage"]["total_estimated_cost_usd"] is None


def test_no_invented_precision_or_semantic_metrics(measured):
    assert "INSUFFICIENT RELEVANCE LABELS" in measured["precision"]
    assert measured["semantic_review"] == "PENDING_REVIEW"
    assert measured["summary"]["fully_validated_answers"] == 0
    assert measured["original_m9"]["scope"] == {"questions": 29, "answerable": 26, "unsupported": 3}


@pytest.mark.parametrize("qid", ["M9-Q04", "M9-Q05", "M9-Q09", "M9-Q10", "M9-Q11", "M9-Q13", "M9-Q16",
                                  "M9-Q21", "M9-Q23", "M9-Q25", "R01", "R02", "R03", "R04", "R05"])
def test_question_metrics_and_safe_provenance(measured, qid):
    row = measured["records"][qid]
    assert row["m8"]["budget"] == 128000
    assert row["m8"]["candidate_count"] == 30
    for value in row["metrics"]:
        assert value["artifact_ref"] in measured["references"]
        assert value["method"] and value["version"]
        assert not measured["references"][value["artifact_ref"]]["artifact"].startswith("/")
    assert row["prompt"]["M8_package_sha256"] == row["m8_case"]["M8_package_sha256"]
    # No large source packages are in dashboard records.
    assert "llm_evidence" not in row and "parents" not in row


def test_direct_vs_parent_only(measured):
    r = measured["records"]["M9-Q05"]
    assert r["retrieval"]["complete_groups"] == 0
    assert r["retrieval"]["parent_located_groups"] == 1
    assert r["m8"]["delivered_groups"] == 1


def test_metric_denominators(tmp_path):
    source = tmp_path / "record.json"
    source.write_text("{}")
    store = Store(tmp_path)
    store.bind("record.json", sha(source))
    with pytest.raises(ArtifactError):
        metric(store, "invalid", 2, "record.json", "fixture", "fixture", numerator=2, denominator=1)


def test_future_validation_autodiscovery(tmp_path):
    root = tmp_path
    out = root / "data/evals/post-generation/new-v2"
    out.mkdir(parents=True)
    response = root / "data/response.json"
    response.write_text("{}")
    value = {"schema": "post-generation-validation-1.0", "question_id": "Q-A",
             "response_file_sha256": sha(response), "M8_package_sha256": "package",
             "semantic_status": "PENDING_REVIEW", "fully_validated": False,
             "overall_status": "INDETERMINATE", "qualification_status": "QUALIFICATION_APPLICABILITY_UNDETERMINED", "checks": [{"check": "Owned fixture", "status": "MEASURED", "outcome": "PASS"}]}
    record = out / "VALIDATION.json"
    record.write_text(json.dumps(value))
    (out / "MANIFEST.json").write_text(json.dumps({"schema": "post-generation-validation-manifest-1.0",
        "status": "COMPLETED_SEALED", "dataset_freeze_manifest_sha256": FREEZE,
        "input_bindings": {"data/response.json": sha(response)}, "files": {"VALIDATION.json": sha(record)}}))
    attempt = {"completed": True, "response_file_sha256": sha(response),
               "audit": {"M8_package_sha256": "package"}, "validation": None}
    rows = {"Q-A": {"attempts": [attempt]}}
    rejected = []
    assert len(discover_validations(Store(root), rows, rejected)) == 1
    assert attempt["validation"]["semantic_status"] == "PENDING_REVIEW" and not rejected
    before = copy.deepcopy(attempt)
    record.write_text('{"tampered":true}')
    assert not discover_validations(Store(root), rows, rejected)
    assert len(rejected) == 1 and attempt == before


def test_invalid_semantic_certificate_rejected(tmp_path):
    out = tmp_path / "data/evals/post-generation/fake-v1"
    out.mkdir(parents=True)
    record = out / "VALIDATION.json"
    record.write_text(json.dumps({"schema": "post-generation-validation-1.0", "question_id": "Q-A",
        "response_file_sha256": "x", "M8_package_sha256": "y", "semantic_status": "CERTIFIED",
        "fully_validated": True}))
    (out / "MANIFEST.json").write_text(json.dumps({"schema": "post-generation-validation-manifest-1.0",
        "status": "COMPLETED_SEALED", "dataset_freeze_manifest_sha256": FREEZE,
        "input_bindings": {}, "files": {"VALIDATION.json": sha(record)}}))
    rows = {"Q-A": {"attempts": [{"completed": True, "response_file_sha256": "x",
                                 "audit": {"M8_package_sha256": "y"}, "validation": None}]}}
    rejected = []
    assert not discover_validations(Store(tmp_path), rows, rejected)
    assert rejected and rows["Q-A"]["attempts"][0]["validation"] is None


def test_future_generation_normalization(tmp_path):
    from tools.pre_generation_gate.response_v2 import synthetic_example
    from tools.quality_dashboard.adapter import normalize_attempt

    store = Store(tmp_path)
    base = tmp_path / "data/evals/generation/next-v1"
    base.mkdir(parents=True)
    answer = synthetic_example()
    # This is an owned normal-answer fixture, not the live instructional example.
    text = json.dumps(answer).replace("EXAMPLE-UNIT-001", "UNIT-owned-fixture")
    response = base / "GENERATED_RESPONSE.json"
    response.write_text(text)
    audit = base / "GENERATION_AUDIT.json"
    audit.write_text(json.dumps({"schema": "generation-result-1.0", "generation_executed": True,
        "source_integrity": "LIVE_M8_VALIDATED", "response_status": "completed", "status": "GENERATED_STRUCTURE_VALID",
        "model": "fixture-model", "prompt_template": "grounded-generation-prompt-v2.1", "request_sha256": "0" * 64,
        "response_schema": "grounded-response-2.0", "M8_package_sha256": "fixture-package",
        "usage": {"usage_status": "MEASURED_API_USAGE", "input_tokens": 20, "output_tokens": 8, "total_tokens": 28}}))
    manifest = base / "MANIFEST.json"
    manifest.write_text(json.dumps({"schema": "quality-generation-experiment-1.0",
        "status": "COMPLETED_SEALED", "question_id": "Q-A", "dataset_freeze_manifest_sha256": FREEZE,
        "files": {p.name: sha(p) for p in [response, audit]}}))
    name = manifest.relative_to(tmp_path).as_posix()
    value = store.manifest(name)
    questions = {"Q-A": {"question": "Owned fixture question"}}
    cases = {("Q-A", "B", 128000): {"M8_package_sha256": "fixture-package",
                                   "actual_M8_included_parent_ids": ["UNIT-owned-fixture"]}}
    result = normalize_attempt(store, name, value, questions, cases)
    assert result["completed"] and result["response"]["status"] == "ANSWERED"
    assert result["usage"]["total_tokens"] == 28
    value["status"] = "RUNNING"
    with pytest.raises(ArtifactError, match="UNSEALED"):
        normalize_attempt(store, name, value, questions, cases)


def test_preservation_of_existing_files():
    from tools.quality_dashboard.artifacts import sha

    before = json.loads((ROOT / "workspace/rag-implementation/v1/master-dashboard-v1/PRESERVATION_BEFORE.json").read_text())["files"]
    working = {"workspace/rag-implementation/v1/MILESTONE_TRACKER.json",
               "workspace/rag-implementation/v1/MILESTONE_TRACKER.md"}
    assert not [name for name, fingerprint in before.items()
                if name not in working and sha(ROOT / name) != fingerprint]


def test_current_post_validation_receipt(measured):
    result = measured["records"]["M9-Q05"]["latest"]["validation"]
    assert result["overall_status"] == "INDETERMINATE"
    assert result["quote_checks"]["all_verbatim"]
    assert all(c["native_citations_present"] for c in result["citation_checks"])
    assert result["qualification_status"] == "QUALIFICATION_APPLICABILITY_UNDETERMINED"
    assert not result["fully_validated"] and not result["answer_rewritten"]
    assert measured["summary"]["validated_questions"] == 1


def test_tracker_historical_records_unchanged():
    before_path = ROOT / "workspace/rag-implementation/v1/master-dashboard-v1/TRACKER_BEFORE.json"
    if before_path.exists():
        before = json.loads(before_path.read_text())
        after = json.loads((ROOT / "workspace/rag-implementation/v1/MILESTONE_TRACKER.json").read_text())
        assert {key: after[key] for key in before} == before


@pytest.mark.parametrize("usage", [{"input_tokens": True}, {"input_tokens": -1},
                                   {"latency_ms": float("nan")}, {"total_estimated_cost_usd": "NaN"}, {"total_estimated_cost_usd": "bad"},
                                   {"protected_source_text": "never display"},
                                   {"model": "<script>"}])
def test_malformed_or_unrecognized_usage_rejected(usage):
    from tools.quality_dashboard.adapter import validate_usage_fields

    with pytest.raises(ArtifactError):
        validate_usage_fields(usage)


def test_missing_validation_qualification_status_rejected():
    from tools.quality_dashboard.adapter import valid_validation_shape

    assert not valid_validation_shape({"schema": "post-generation-validation-1.0",
        "overall_status": "MEASURED", "checks": [{"check": "fixture", "status": "MEASURED", "outcome": "PASS"}]})
