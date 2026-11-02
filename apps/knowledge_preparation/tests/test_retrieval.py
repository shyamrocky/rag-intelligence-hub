"""Read-only retrieval workspace checks against sealed historical measurements."""
import socket
from pathlib import Path

import pytest
from streamlit.string_util import clean_text
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import retrieval
from tools.quality_dashboard.artifacts import ArtifactError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("NO_NETWORK_OR_PIPELINE_EXECUTION")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    from apps.knowledge_preparation import views
    monkeypatch.setattr(views, "load", forbidden)
    from tools.evidence.service import EvidenceService
    monkeypatch.setattr(EvidenceService, "__init__", forbidden)


@pytest.fixture(scope="module")
def measurements():
    return retrieval.load()


def app(monkeypatch, measurements):
    monkeypatch.setattr(retrieval, "load", lambda: measurements)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("knowledge-retrieval")
    return result.run()


def select(result, label):
    return next(s for s in result.selectbox if s.label == label)


def test_real_inventory_and_gap_classification(measurements):
    records = measurements["records"]
    assert len(records) == 34
    assert sum(len(r["group_ids"]) for r in records.values()) == 40
    assert sum(r["reference"]["answerability"] == "UNSUPPORTED" for r in records.values()) == 3
    assert all(r["target"] for r in records.values())
    gaps = {q for q, r in records.items() if r["group_ids"] and not r["target"]["m8"]["complete_question"]}
    assert gaps == {"R03", "R04", "M9-Q23", "M9-Q26"}
    assert records["R03"]["target"]["m8"]["missing_group_ids"] == ["R03-G1"]
    assert retrieval.coverage(records["M9-Q27"], ("m8", "delivered_groups")).startswith("N/A")
    unavailable = records["R03"] | {"target": None}
    assert retrieval.context_status(unavailable) == "UNAVAILABLE"
    assert retrieval.coverage(unavailable, ("m8", "delivered_groups")) == "UNAVAILABLE"


def test_scope_tabs_and_question_context(monkeypatch, measurements):
    result = app(monkeypatch, measurements)
    assert not result.exception and not result.error
    assert result.title[0].value == "Knowledge Retrieval"
    assert [t.label for t in result.tabs] == ["Search & Ranking", "Selected Top-30", "Evidence Reconstruction", "Context Assembly"]
    assert len(select(result, "Question").options) == 34
    assert not next(e for e in result.expander if e.label == "Filter questions").proto.expanded
    assert not next(e for e in result.expander if e.label == "Benchmark summary & question journeys").proto.expanded
    assert {s.label for s in result.selectbox} == {"Question", "Question cohort", "Benchmark answerability"}
    for qid in measurements["records"]:
        select(result, "Question").select(qid).run()
        assert not result.exception and not result.error, qid
        assert all(result.tabs[i].subheader[0].value.startswith(qid) for i in (1, 2, 3))
        assert len(result.tabs[1].dataframe[0].value) == 30
        assert any(m.value == f"#### Coverage against {qid}’s human-approved evidence labels" for m in result.tabs[3].markdown)
        iframe = result.get("iframe")[0].proto.srcdoc
        assert f'"question_id": "{qid}"' in iframe
        assert '<select id="question-select" hidden>' in iframe
        assert 'outside selected Top-30' in iframe
        assert '15 frozen questions' not in iframe
        assert 'Search rank #' in iframe and 'Combined RRF score' in iframe
        assert 'Final RRF rank #' in iframe
        assert not any("evidence-group mappings failed" in w.value for w in result.warning)
    select(result, "Question cohort").select("NLP").run()
    select(result, "Question").select("R03").run()
    assert any("R03-G1" in w.value for w in result.warning)
    result.run()
    assert result.session_state["kr_question"] == "R03"
    select(result, "Question cohort").select("All Questions").run()
    select(result, "Benchmark answerability").select("Unsupported").run()
    assert not result.exception and not result.error
    assert [m.value for m in result.metric] == ["3", "3/3", "N/A", "N/A"]
    assert any("INSUFFICIENT RELEVANCE LABELS" in c.value for c in result.caption)
    assert not result.button
    assert not any(".env" in clean_text(str(df.value)) for df in result.dataframe)


def test_empty_filter_and_binding_failure(monkeypatch, measurements):
    result = app(monkeypatch, measurements)
    select(result, "Question cohort").select("Abstention").run()
    select(result, "Benchmark answerability").select("Answerable").run()
    assert not result.exception
    assert any("No questions match" in i.value for i in result.info)
    def broken():
        raise ArtifactError("PRIVATE_PAYLOAD_MUST_NOT_LEAK")
    monkeypatch.setattr(retrieval, "load", broken)
    result.run()
    assert not result.exception
    assert "bindings failed verification" in result.error[0].value
    assert "PRIVATE_PAYLOAD" not in result.error[0].value
    assert not result.dataframe


@pytest.mark.parametrize("defect", ["question", "score", "parent", "native_hash"])
def test_explorer_binding_failures(measurements, monkeypatch, defect):
    from copy import deepcopy

    from apps.knowledge_preparation.retrieval_explorer import build
    store = measurements["store"]
    original = store.json
    def altered(name):
        value = original(name)
        if name == "data/evals/benchmark-completion/v1/m7/M9-Q01.json":
            value = deepcopy(value)
            if defect == "question":
                value["query_sha256"] = "0" * 64
            elif defect == "score":
                value["candidates"][0]["rrf_score"] += 1
            elif defect == "native_hash":
                key = next(iter(value["diagnostics"]["native_inputs"]))
                value["diagnostics"]["native_inputs"][key] = "0" * 64
        if defect == "parent" and name == "data/evals/benchmark-completion/v1/m8/M9-Q01.json":
            value = deepcopy(value)
            value["considered_parent_ids"] = []
        return value
    monkeypatch.setattr(store, "json", altered)
    with pytest.raises(ArtifactError):
        build(measurements, "M9-Q01")


def test_all_native_inputs_and_selected_parent_links(measurements):
    from apps.knowledge_preparation.retrieval_explorer import build
    for qid, record in measurements["records"].items():
        payload, case = build(measurements, qid)
        question = payload["questions"][0]
        assert question["question"] == record["question"]
        assert len(question["bm25"]) == len(question["vector"]) == 50
        assert len(question["rrf"]) == 30
        selected = [r["chunk_id"] for r in question["rrf"]]
        assert selected == case["considered_chunk_ids"]
        assert {payload["chunks"][cid]["unit_id"] for cid in selected} == set(case["considered_parent_ids"])
        assert len(question["pool"]) == len({r["chunk_id"] for mode in ("bm25", "vector") for r in question[mode]})
        assert "mandatory_evidence_group_ids" not in payload


def test_group_mappings_and_recorded_unit_tokens(measurements):
    from apps.knowledge_preparation.retrieval_explorer import build
    from apps.knowledge_preparation.retrieval_labels import group_rows, unit_rows
    total = 0
    for qid, record in measurements["records"].items():
        _, case = build(measurements, qid)
        groups = group_rows(measurements, record, case)
        assert {g["Human-approved evidence group"] for g in groups} == set(record["group_ids"])
        total += len(groups)
        assert sum(g["Coverage"] == "Covered" for g in groups) == (record["target"]["m8"]["delivered_groups"] or 0)
        units = unit_rows(case)
        assert len(units) == case["counts"]["distinct_parents"]
        assert sum(u["Outcome"] == "Included" for u in units) == len(case["actual_M8_included_parent_ids"])
        for omitted in case["omitted"]:
            row = next(u for u in units if u["Evidence Unit ID"] == omitted["unit_id"])
            assert row["BGE tokens"] == str(omitted["token_count"])
    assert total == 40
    record = measurements["records"]["M9-Q04"]
    _, case = build(measurements, "M9-Q04")
    groups = group_rows(measurements, record, case)
    assert len(groups) == 3 and all(g["Coverage"] == "Covered" for g in groups)
    units = unit_rows(case)
    assert len(units) == 26 and sum(u["Outcome"] == "Included" for u in units) == 16
    assert all("not recorded" in u["BGE tokens"] for u in units if u["Outcome"] == "Included")
    assert all("remaining evidence budget" in u["Reason"] for u in units if u["Outcome"] == "Excluded")
    assert case["budget_accounting"]["exact_llm_evidence_tokens"] == 125649


def test_group_mapping_never_promotes_missing_evidence(measurements):
    from copy import deepcopy

    from apps.knowledge_preparation.retrieval_explorer import build
    from apps.knowledge_preparation.retrieval_labels import group_rows, unit_rows
    _, case = build(measurements, "M9-Q04")
    record = deepcopy(measurements["records"]["M9-Q04"])
    record["completion"]["group_outcomes"][0]["alternatives"][0]["unit_id"] = "unauthorized-unit"
    with pytest.raises(ArtifactError):
        group_rows(measurements, record, case)
    synthetic = {"considered_parent_ids": ["a"], "actual_M8_included_parent_ids": [], "obligations": [],
                 "omitted": [{"unit_id": "a", "reason": "PARENT_EXCEEDS_TOTAL_BUDGET", "token_count": 129000, "remaining_tokens": 128000}]}
    assert unit_rows(synthetic)[0]["Reason"] == "Evidence Unit exceeds the total evidence budget"
