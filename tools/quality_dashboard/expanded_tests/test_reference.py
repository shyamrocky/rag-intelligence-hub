"""Reference joins and historical arithmetic only; no new retrieval scores or labels."""
import copy
import json
from pathlib import Path

import pytest

from tools.quality_dashboard.artifacts import ArtifactError, Store, sha
from tools.quality_dashboard.expanded_adapter import (
    BENCHMARK,
    MANIFEST,
    MANIFEST_SHA,
    filter_questions,
    load_expanded,
    validate_reference,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def data():
    return load_expanded(ROOT)


def test_exact_cohort_reconciliation(data):
    s = data["summary"]
    assert (s["questions"], s["answerable"], s["unsupported"], s["mandatory_groups"]) == (34, 31, 3, 40)
    assert {r["cohort_id"]: r["Questions"] for r in data["cohorts"]} == {"A": 10, "B": 5, "C": 16, "D": 3}
    assert len(data["records"]) == len({r["question_id"] for r in data["records"].values()})
    assert len(data["frozen_data"]["records"]) == 15
    assert data["frozen_data"]["summary"]["groups"] == 22


def test_original_answerable_and_unsupported_membership(data):
    q = data["records"]
    assert {key for key, r in q.items() if r["reference"]["source_dataset"] == "m9/benchmark-v1"} == {f"M9-Q{i:02}" for i in range(1, 30)}
    assert {key for key, r in q.items() if r["reference"]["cohort_id"] == "B"} == {f"R{i:02}" for i in range(1, 6)}
    assert {key for key, r in q.items() if r["reference"]["cohort_id"] == "D"} == {"M9-Q27", "M9-Q28", "M9-Q29"}
    assert all(not q[key]["group_ids"] for key in ["M9-Q27", "M9-Q28", "M9-Q29"])
    assert not data["reference"]["summary"]["ambiguous_identities"]
    assert data["reference"]["summary"]["expected_total_discrepancy"] == 0


def test_remaining_is_not_assumed_successful(data):
    rows = data["remaining_report"]
    assert len(rows) == 16
    assert sum(r["complete_parent_group_discovery"] for r in rows) == 14
    assert {r["question_id"] for r in rows if not r["complete_parent_group_discovery"]} == {"M9-Q07", "M9-Q26"}
    q08 = next(r for r in rows if r["question_id"] == "M9-Q08")
    assert q08["complete_parent_group_discovery"] and q08["equivalence_aware_Recall_at_10"] == pytest.approx(2/3)
    assert sum(r["parent_groups_found"] for r in rows) == 16
    assert sum(r["required_groups"] for r in rows) == 18


@pytest.mark.parametrize("qid", [f"M9-Q{i:02}" for i in range(1, 30)] + [f"R{i:02}" for i in range(1, 6)])
def test_provenance_and_available_measurements(data, qid):
    row = data["records"][qid]
    assert row["reference"]["evidence_label_status"].startswith("OWNER_APPROVED")
    assert row["reference"]["original_question_id"] == qid
    for m in row["retrieval_measurements"] + row["m8_measurements"]:
        assert m["artifact_ref"] in data["references"] and m["method"] and m["version"]
        assert m["status"] == "REUSED_HISTORICAL"
    assert row["retrieval_measurements"] and row["m8_measurements"]


def test_missing_target_m8_not_inferred(data):
    q = data["records"]["M9-Q01"]
    assert q["frozen"] is None
    m7 = next(x for x in q["retrieval_measurements"] if x["mode"] == "hybrid")
    assert m7["values"]["at_k"]["10"]["all_required_groups_retrieved"]
    m8 = next(x for x in q["m8_measurements"] if x["mode"] == "hybrid" and x["budget"] == 32000)
    assert not m8["values"]["all_required_groups_included"]
    assert not any(x["budget"] == 128000 for x in q["m8_measurements"])


def test_real_q05_and_not_run_preserved(data):
    a = data["records"]["M9-Q05"]["latest"]
    assert a["usage"]["input_tokens"] == 86200 and a["usage"]["output_tokens"] == 848
    assert a["usage"]["total_estimated_cost_usd"] == "0.011198925"
    assert a["validation"]["overall_status"] == "INDETERMINATE"
    assert len(a["response"]["claims"]) == 2
    assert sum(r["latest"] is None for r in data["records"].values()) == 33
    assert "INSUFFICIENT RELEVANCE LABELS" in data["precision"]


@pytest.mark.parametrize("cohort,count", [("All Questions",34),("Original Difficult",10),("NLP",5),("Original Remaining",16),("Abstention",3)])
def test_cohort_filters(data, cohort, count):
    assert len(filter_questions(data, cohort=cohort)) == count


def test_other_filters(data):
    assert len(filter_questions(data, generation="NOT_RUN")) == 33
    assert filter_questions(data, generation="COMPLETED") == ["M9-Q05"]
    assert not filter_questions(data, generation="FAILED_ONLY")
    assert len(filter_questions(data, evaluation="M7 available")) == 34
    assert len(filter_questions(data, evaluation="M8 available")) == 34
    assert len(filter_questions(data, evaluation="Target M8 available")) == 15
    assert len(filter_questions(data, evaluation="Target M8 not measured")) == 19
    assert len(filter_questions(data, answerability="Unsupported")) == 3
    assert len(filter_questions(data, answerability="Answerable")) == 31


@pytest.mark.parametrize("change", ["duplicate", "question", "unsupported", "cohort"])
def test_invalid_reference_fail_closed(data, change):
    value = copy.deepcopy(data["reference"])
    if change == "duplicate":
        value["questions"].append(value["questions"][0])
    elif change == "question":
        value["questions"][0]["question_text"] += " altered"
    elif change == "unsupported":
        value["questions"][0]["answerability"] = "UNSUPPORTED"
    else:
        value["questions"][0]["cohort_id"] = "D"
    with pytest.raises(ArtifactError):
        validate_reference(value)


def test_plan_preparation_not_execution(data):
    plan = data["run_plan"]
    assert not plan["execution_authorized"] and len(plan["questions"]) == 34
    assert all(not q["eligible_for_execution_now"] for q in plan["questions"])
    assert sum(q["prior_success"] for q in plan["questions"]) == 1
    assert sum("REQUIRED_NATIVE_TOP50_RRF30_INPUTS_NOT_AVAILABLE" in q["blockers"] for q in plan["questions"]) == 17
    assert plan["generation_settings"]["model"] == "gpt-6-luna"
    assert plan["generation_settings"]["prompt_version"] == "grounded-generation-prompt-v2.1"
    assert plan["actual_generator_token_counts_for_new_requests"] == "UNAVAILABLE"


def test_sealed_reference_and_previous_implementation_intact():
    store = Store(ROOT)
    store.manifest(MANIFEST, expected=MANIFEST_SHA)
    store.manifest("data/evals/quality-dashboard/implementation-v1/MANIFEST.json",
                   expected="249f8b3034224d43c04f93bdd98c89e2010381a039afb16e88893a7907ecdf12")
    before = json.loads((ROOT/"workspace/rag-implementation/v1/expanded-benchmark-v1/PRESERVATION_BEFORE.json").read_text())["files"]
    working = {"workspace/rag-implementation/v1/MILESTONE_TRACKER.json", "workspace/rag-implementation/v1/MILESTONE_TRACKER.md"}
    assert not [n for n,h in before.items() if n not in working and sha(ROOT/n) != h]
    assert store.json(BENCHMARK)["summary"]["unique_questions"] == 34
