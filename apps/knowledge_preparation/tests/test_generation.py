"""Generation-page historical readback with execution and approval paths denied."""
import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import generation as view
from tools.quality_dashboard.artifacts import ArtifactError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("GENERATION_VIEW_MUST_BE_READ_ONLY")
    from tools.evidence.service import EvidenceService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.human_review import local_poc, observation_review
    from tools.pre_generation_gate.current import PromptAssemblyGate
    from tools.preflight_suite import runner
    from tools.retrieval.service import RetrievalService
    for cls, method in [(EvidenceService, "assemble"), (EvidenceService, "validate"),
                        (OpenAIAdapter, "verify_model"), (OpenAIAdapter, "count"),
                        (OpenAIAdapter, "invoke"), (PromptAssemblyGate, "prepare"),
                        (RetrievalService, "search")]:
        monkeypatch.setattr(cls, method, forbidden)
    monkeypatch.setattr(runner, "execute", forbidden)
    monkeypatch.setattr(local_poc, "decide", forbidden)
    monkeypatch.setattr(observation_review, "decide", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(local_poc, "local_access", lambda: {
        "bind": "127.0.0.1", "headers": {"host": "127.0.0.1:8516"}, "peer": "127.0.0.1"})


@pytest.fixture(scope="module")
def snapshot():
    return view.load()


def app(monkeypatch, snapshot):
    monkeypatch.setattr(view, "load", lambda: snapshot)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("generation")
    return result.run()


def select(result, qid):
    next(s for s in result.selectbox if s.label == "Question").select(qid).run()
    assert not result.exception and not result.error, qid


def test_totals_scope_and_abstention(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    assert not result.exception and not result.error
    assert [m.value for m in result.metric[:4]] == ["34", "29", "5", "36"]
    assert any("0.384996335" in m.value for m in result.markdown)
    assert len(next(s for s in result.selectbox if s.label == "Question").options) == 34
    assert not next(e for e in result.expander if e.label == "History / Technical details — select an attempt").proto.expanded
    select(result, "M9-Q28")
    assert any(s.value == "Unable to answer from available evidence" for s in result.subheader)
    assert any("ABSTAINED" in m.value for m in result.markdown)
    assert any("Model status: ABSTAINED" in c.value for c in result.caption)
    assert not result.form
    assert not any(b.label in {"Approve", "Reject", "Execute", "Run", "Record owner triage"} for b in result.button)
    result.run()
    assert result.session_state["gen_question"] == "M9-Q28"


def test_funded_answer_and_earlier_failure_are_separate(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    select(result, "M9-Q05")
    usage = next(t.value for t in result.table if "Measurement" in t.value.columns)
    assert usage.iloc[0]["Recorded value"] == "86,200"
    assert "0.011198925" in usage["Recorded value"].values
    assert any("NOT_MEASURED" in i.value for i in result.info)
    selector = next(s for s in result.selectbox if s.label == "Saved generation attempt")
    attempts = snapshot[0]["records"]["M9-Q05"]["attempts"]
    failed = next(i for i, attempt in enumerate(attempts) if not attempt.get("response"))
    selector.select(failed).run()
    assert not result.exception
    assert any("earlier attempt" in i.value for i in result.info)
    assert not any("Owner review state:" in m.value for m in result.markdown)
    assert any("Original returned text is unavailable" in i.value for i in result.info)


def test_rejected_output_raw_inspection_and_tamper_fail_closed(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    select(result, "M9-Q18")
    assert any("No accepted structured response" in w.value for w in result.warning)
    assert any("SCHEMA_OR_RELATIONSHIP_INVALID" in w.value for w in result.warning)
    assert any("did not pass the response contract" in c.value for c in result.caption)
    assert any("DIAGNOSTIC_TRIAGE_ONLY" in m.value for m in result.markdown)
    next(c for c in result.checkbox if c.label == "Show protected raw provider response").check().run()
    assert not result.exception and result.code
    assert '"output"' in result.code[0].value
    def corrupt(*args, **kwargs):
        raise ArtifactError("PRIVATE_DETAILS")
    monkeypatch.setattr(view, "capture_reference", corrupt)
    result.run()
    assert not result.exception and not result.code
    assert any("unavailable or unverified" in w.value for w in result.warning)
    assert not result.form


def test_all_questions_original_findings_and_stage_names(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    for qid in snapshot[0]["records"]:
        select(result, qid)
        assert not result.form
    select(result, "M9-Q04")
    assert any("Original technical outcome: **FAILED**" in m.value for m in result.markdown)
    assert any("OWNER_APPROVED_POC" in m.value for m in result.markdown)
    select(result, "R03")
    assert any("GROUNDING_REVIEW_REQUIRED" in m.value for m in result.markdown)
    assert any("Evidence assembly delivered" in m.value for m in result.markdown)
    select(result, "M9-Q12")
    assert any("Raw response unavailable" in i.value for i in result.info)
    for attempt in snapshot[0]["records"]["M9-Q02"]["attempts"]:
        timing = view.timing_for(attempt)
        if timing:
            assert not any("M8" in row["Stage"] for row in view.timing_rows(timing))


def test_invalid_publication_and_capture_unavailable(monkeypatch, snapshot):
    def corrupt():
        raise ArtifactError("PRIVATE_DETAILS")
    monkeypatch.setattr(view, "load", corrupt)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("generation")
    result.run()
    assert not result.exception and result.error
    assert "PRIVATE_DETAILS" not in result.error[0].value
    assert not result.metric
    assert view.timing_rows(None) == []


def test_capture_failure_does_not_claim_raw_artifact(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    monkeypatch.setattr(view, "load_output", lambda *args: {
        "state": "RAW_RESPONSE_UNAVAILABLE", "candidate": None, "text_parts": [], "refusals": []})
    monkeypatch.setattr(view, "capture_reference", lambda *args: ({"status": "RAW_RESPONSE_CAPTURE_FAILED"}, None))
    select(result, "M9-Q18")
    assert any("RAW_RESPONSE_CAPTURE_FAILED" in m.value for m in result.markdown)
    assert any("Raw response unavailable" in w.value for w in result.warning)
    assert not result.code
    assert not any(c.label == "Show protected raw provider response" for c in result.checkbox)


def test_latency_phases_use_exclusive_time_and_preserve_missing():
    timing = {"end_to_end_ms": 10000, "unattributed_overhead_ms": 500, "stages": [
        {"stage": "SAVED_INPUT_VERIFICATION", "duration_ms": 1000, "inclusive_ms": 3000},
        {"stage": "M8_EVIDENCE_ASSEMBLY", "duration_ms": 6000, "inclusive_ms": 9000},
        {"stage": "LLM_GENERATION", "duration_ms": 1800, "inclusive_ms": 2000},
        {"stage": "GENERATION_SERVICE_OVERHEAD", "duration_ms": 200, "inclusive_ms": 9000},
        {"stage": "POST_GENERATION_VALIDATION", "duration_ms": 300},
        {"stage": "FINAL_SOURCE_CHECK", "duration_ms": 100},
        {"stage": "ARTIFACT_PERSISTENCE", "duration_ms": 100},
    ]}
    phases = view.phase_rows(timing)
    assert [p["Seconds"] for p in phases] == [7, 2, 0.5, 0.5]
    assert sum(p["Share of end-to-end"] for p in phases) == pytest.approx(100)
    assert view.duration_label(6141.990083968267) == "6,142 ms / 6.14 sec"
    assert view.duration_label(None) == "UNAVAILABLE"
    assert view.phase_rows(None) == []
    missing = view.phase_rows({"end_to_end_ms": 1, "unattributed_overhead_ms": 1, "stages": []})
    assert all(p["Seconds"] is None for p in missing[:3])


def test_real_timing_phase_totals_match_and_detail_is_collapsed(monkeypatch, snapshot):
    for record in snapshot[0]["records"].values():
        for attempt in record["attempts"]:
            timing = view.timing_for(attempt)
            if timing:
                assert sum(p["Seconds"] or 0 for p in view.phase_rows(timing)) == pytest.approx(timing["end_to_end_ms"] / 1000)
    result = app(monkeypatch, snapshot)
    select(result, "M9-Q01")
    table = next(t.value for t in result.table if "Phase" in t.value.columns)
    assert list(table["Phase"][:3]) == ["Request preparation", "Generation", "Post-generation"]
    assert not next(e for e in result.expander if e.label == "Individual stage timings and full-precision technical details").proto.expanded
    assert any("Longest phase: Request preparation" in m.value for m in result.markdown)
