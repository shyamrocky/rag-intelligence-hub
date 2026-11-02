"""Saved preparation observations only; pipeline and provider entry points forbidden."""
import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import pre_generation as view
from tools.quality_dashboard.artifacts import ArtifactError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("READ_ONLY_PREPARATION_UI")
    from tools.evidence.service import EvidenceService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.pre_generation_gate.current import PromptAssemblyGate
    from tools.preflight_suite import runner
    from tools.retrieval.service import RetrievalService
    for cls, method in [(EvidenceService, "assemble"), (EvidenceService, "validate"),
                        (OpenAIAdapter, "verify_model"), (OpenAIAdapter, "count"),
                        (OpenAIAdapter, "invoke"), (PromptAssemblyGate, "prepare"),
                        (RetrievalService, "search")]:
        monkeypatch.setattr(cls, method, forbidden)
    monkeypatch.setattr(runner, "execute", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def snapshot():
    return view.load()


def app(monkeypatch, snapshot):
    monkeypatch.setattr(view, "load", lambda: snapshot)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("pre-generation")
    return result.run()


def test_question_inventory_versions_readonly_refresh(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    assert not result.exception and not result.error
    assert [m.value for m in result.metric[:3]] == ["34", "33", "34"]
    assert len(next(s for s in result.selectbox if s.label == "Question").options) == 34
    next(s for s in result.selectbox if s.label == "Question").select("M9-Q02").run()
    assert not result.exception and not result.error
    assert any("grounded-generation-prompt-v2.2" in m.value for m in result.markdown)
    assert any("Historical observation" in w.value for w in result.warning)
    assert not result.button
    assert not next(e for e in result.expander if e.label == "History / Technical details").proto.expanded
    assert result.code and "ABSTAINED" in result.code[0].value
    assert not any("publisher payload" in c.value for c in result.code)
    assert result.metric[-2].value == "127840"
    result.run()
    assert result.session_state["pg_question"] == "M9-Q02"
    next(s for s in result.selectbox if s.label == "Question").select("R03").run()
    assert any("R03-G1" in m.value for m in result.markdown)
    next(s for s in result.selectbox if s.label == "Question").select("M9-Q27").run()
    assert any("no positive evidence-group denominator" in c.value for c in result.caption)


def test_historical_question_and_unavailable_tokens(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    next(s for s in result.selectbox if s.label == "Question").select("M9-Q05").run()
    assert not result.exception and not result.error
    assert result.metric[-3].value == "17"
    assert any("grounded-generation-prompt-v2" in m.value for m in result.markdown)
    table = next(table.value for table in result.table if "Measurement" in table.value.columns)
    assert table.iloc[0]["Saved observation (tokens / result)"] == "86,200"
    assert any("recorded provider count receipt" in c.value for c in result.caption)
    assert not result.button


def test_artifact_failure_and_prompt_mismatch(monkeypatch, snapshot):
    def bad():
        raise ArtifactError("PRIVATE_DETAILS")
    monkeypatch.setattr(view, "load", bad)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("pre-generation")
    result.run()
    assert not result.exception and result.error
    assert "PRIVATE_DETAILS" not in result.error[0].value
    assert not result.metric
    assert view.prompt_instructions("grounded-generation-prompt-v2.2", "0" * 64) is None
    assert view.prompt_instructions("../../.env", "0" * 64) is None
    assert {qid for qid in snapshot[0]["records"]} == {
        *[f"M9-Q{i:02d}" for i in range(1, 30)], *[f"R{i:02d}" for i in range(1, 6)]}


def test_all_questions_and_local_only_observation(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    for qid in snapshot[0]["records"]:
        next(s for s in result.selectbox if s.label == "Question").select(qid).run()
        assert not result.exception and not result.error, qid
        assert result.session_state["pg_question"] == qid
        assert not result.button
    next(s for s in result.selectbox if s.label == "Question").select("M9-Q02").run()
    selector = next(s for s in result.selectbox if s.label == "Saved preparation check")
    selector.select(0).run()
    assert not result.exception and not result.error
    assert any("Local evidence and prompt checks passed" in m.value for m in result.markdown)
    table = next(table.value for table in result.table if "Measurement" in table.value.columns)
    assert table.iloc[0]["Saved observation (tokens / result)"] == "UNAVAILABLE"
    assert any("grounded-generation-prompt-v2.1" in m.value for m in result.markdown)


def test_context_allocation_and_summary_semantics():
    rows, formula = view.measurement_rows({"input_tokens": 87615,
        "context_fit": {"reserved_output_tokens": 4096, "safety_margin_tokens": 1024, "fits": True}})
    assert formula == "87,615 + 4,096 + 1,024 = 92,735 tokens"
    total = next(row for row in rows if row["Measurement"] == "Total context allocation")
    assert total["Saved observation (tokens / result)"] == "92,735"
    assert list(total) == ["Measurement", "Description", "Saved observation (tokens / result)"]
    rows, formula = view.measurement_rows({"input_tokens": 87615})
    assert formula is None
    assert next(row for row in rows if row["Measurement"] == "Total context allocation")["Saved observation (tokens / result)"] == "UNAVAILABLE"
    assert "Model qualification was not established" in view.saved_summary({"status": "LOCAL_VALIDATED"})
    assert "blocked" in view.saved_summary({"status": "BLOCKED_CONTEXT"})
    assert "qualification was recorded" in view.saved_summary({"status": "MODEL_QUALIFIED"})
