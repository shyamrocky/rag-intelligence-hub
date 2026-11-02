"""Historical story readback: same 8514 data, no re-execution or inflated scope."""
import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import offline_evaluation as view
from tools.quality_dashboard.artifacts import ArtifactError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("OFFLINE_UI_MUST_NOT_EXECUTE_PIPELINE")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    from tools.evidence.service import EvidenceService
    from tools.retrieval.service import RetrievalService
    monkeypatch.setattr(EvidenceService, "__init__", forbidden)
    monkeypatch.setattr(RetrievalService, "__init__", forbidden)


@pytest.fixture(scope="module")
def data():
    return view.load()


def app(monkeypatch, data):
    monkeypatch.setattr(view, "load", lambda: data)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("offline-retrieval-evaluation")
    return result.run()


def test_story_scope_metrics_and_readonly_refresh(monkeypatch, data):
    result = app(monkeypatch, data)
    assert not result.exception and not result.error
    assert result.title[0].value == "Offline Retrieval Evaluation"
    assert [m.value for m in result.metric] == ["34", "31 / 3", "40", "15"]
    assert any(c.value == "questions · 22 human-approved evidence groups" for c in result.caption)
    assert len([h for h in result.subheader if h.value[:2].isdigit()]) == 8
    assert any("Keep RRF" in m.value for m in result.markdown)
    assert any("8 of 15 questions; MiniLM did so for 10 of 15" in m.value for m in result.markdown)
    assert any("19 of 22 required evidence groups" in m.value and "12 of 15 questions all their required evidence" in m.value for m in result.markdown)
    assert any("39 of 40 groups" in m.value and "36 of 40 groups" in m.value
               and "27 of 31 answerable questions" in m.value for m in result.markdown)
    assert any("8514 stays available" in c.value for c in result.caption)
    assert not result.button
    assert not next(e for e in result.expander if e.label == "Question-level historical comparisons").proto.expanded
    selector = next(s for s in result.selectbox if s.label == "Evaluation question")
    assert len(selector.options) == 34
    selector.select("R03").run()
    assert not result.exception and not result.error
    assert any("Recorded delivery gaps" in w.value for w in result.warning)
    result.run()
    assert result.session_state["oe_question"] == "R03"
    next(s for s in result.selectbox if s.label == "Evaluation cohort").select("Abstention").run()
    assert not result.exception
    assert next(s for s in result.selectbox if s.label == "Evaluation question").options == ["M9-Q27", "M9-Q28", "M9-Q29"]
    assert any("N/A — unsupported control" in m.value for m in result.markdown)
    assert not any("precision" in df.value.columns and "calculated" in str(df.value) for df in result.dataframe)


def test_saved_comparison_denominators(data):
    selections = {r["Strategy"]: r for r in view.selection_rows(data)}
    assert selections["RRF Top-10"]["Direct witness groups"] == 14
    assert selections["RRF Top-30"]["Direct witness groups"] == 20
    assert selections["Intersection-first Stage 1"]["Candidate memberships"] == 506
    assert selections["RRF supplementation Stage 1"]["Candidate memberships"] == 448
    assert all(r["Question denominator"] == 15 and r["Required group denominator"] == 22 for r in selections.values())
    budgets = view.budget_rows(data)
    assert len(budgets) == 24
    selected = next(r for r in budgets if r["Strategy"] == "RRF Top-30" and r["Evidence budget (BGE tokens)"] == 128000)
    assert selected["Delivered groups"] == 19 and selected["Complete questions"] == 12
    rows, timing = view.ranker_rows(data)
    assert next(r for r in rows if r["Ranker"] == "RRF(k=60)" and r["Cohort"] == "all_fifteen")["Recall@10 (macro)"] == pytest.approx(0.6444444444444445)
    assert timing["cross_encoder"]["p50_seconds"] > timing["rrf"]["p50_seconds"]
    assert data["summary"]["questions"] == 34 and data["summary"]["mandatory_groups"] == 40


def test_unverified_history_fails_closed(monkeypatch, data):
    original = data["store"].manifest
    def broken(name, **kwargs):
        if name == view.EXTRAS["signals"][0]:
            raise ArtifactError("PRIVATE_DETAILS_DO_NOT_LEAK")
        return original(name, **kwargs)
    monkeypatch.setattr(data["store"], "manifest", broken)
    result = app(monkeypatch, data)
    assert not result.exception
    assert "pinned manifest verification" in result.error[0].value
    assert "PRIVATE_DETAILS" not in result.error[0].value
    assert not result.metric and not result.dataframe


def test_missing_baseline_fails_closed(monkeypatch):
    def broken():
        raise ArtifactError("PRIVATE_PAYLOAD")
    monkeypatch.setattr(view, "load", broken)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("offline-retrieval-evaluation")
    result.run()
    assert not result.exception
    assert result.error and not result.metric
    assert "PRIVATE_PAYLOAD" not in result.error[0].value
