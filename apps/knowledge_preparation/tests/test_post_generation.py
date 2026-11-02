"""Separate evaluation/review pages; exact navigation bindings and read-only refresh."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import human_review as review_view
from apps.knowledge_preparation import post_generation as view
from apps.knowledge_preparation.tests.test_generation import offline  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def snapshot():
    return view.load()


def app(monkeypatch, snapshot, route="post-generation-evaluation-human-review"):
    monkeypatch.setattr(view, "load", lambda: snapshot)
    monkeypatch.setattr(review_view, "load", lambda: snapshot)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash(route)
    return result.run()


def navigate(result, route):
    result._page_hash = calc_hash(route)
    result.run()
    assert not result.exception


def test_post_page_all_questions_is_read_only(monkeypatch, snapshot):
    def forbidden(*args, **kwargs):
        raise AssertionError("REVIEW_COMPONENT_MUST_NOT_RENDER_ON_EVALUATION_PAGE")
    monkeypatch.setattr(review_view, "render_review", forbidden)
    result = app(monkeypatch, snapshot)
    for qid in snapshot[0]["records"]:
        result.selectbox(key="post_question").select(qid).run()
        assert not result.exception and not result.error, qid
        assert not result.form
        assert not any(b.label in {"Approve", "Reject", "Request Changes", "Record owner triage"} for b in result.button)
    assert result.title[0].value == "Post-Generation Evaluation"
    assert [link.label for link in result.sidebar.get("page_link")][-2:] == ["Post-Generation Evaluation", "Human Review"]
    assert {"1 · Evidence supplied and cited", "2 · Recorded technical findings",
            "3 · Review guidance and recorded status"} <= {h.value for h in result.subheader}
    assert any("separate Human Review page" in c.value for c in result.caption)
    assert any(p.label == "Continue to Human Review →" for p in result.get("page_link"))


def test_exact_answer_handoff_approved_lock_and_return(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    result.selectbox(key="post_question").select("M9-Q04").run()
    assert not result.exception and not result.error
    original = dict(result.session_state["review_context"])
    measurements = next(t.value for t in result.table if "Measurement" in t.value.columns)
    assert list(measurements["Recorded value"][:2]) == ["16", "125,649"]
    assert any("Original validation outcome: **FAILED**" in m.value for m in result.markdown)
    navigate(result, "human-review")
    assert result.title[0].value == "Human Review"
    assert result.selectbox(key="unified-review-question").value == "M9-Q04"
    assert result.session_state["review_context"] == original
    assert any("OWNER_APPROVED_POC" in x.value for x in [*result.markdown, *result.info, *result.subheader])
    assert all(b.disabled for b in result.button if b.label in {"Approve", "Reject", "Request Changes"})
    assert not any(h.value == "1 · Evidence supplied and cited" for h in result.subheader)
    navigate(result, "post-generation-evaluation-human-review")
    assert result.selectbox(key="post_question").value == "M9-Q04"
    assert result.session_state["review_context"] == original
    assert not result.form


def test_known_gap_unsupported_and_rejected_review(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot, "human-review")
    for qid in ("R03", "M9-Q27", "M9-Q18", "M9-Q12"):
        result.selectbox(key="unified-review-question").select(qid).run()
        assert not result.exception, qid
        assert all(e.value.startswith("Approval blocked by technical validation.") for e in result.error), qid
        if qid == "R03":
            assert any("R03-G1" in w.value for w in result.warning)
        if qid == "M9-Q18":
            assert any(b.label == "Record owner triage" for b in result.button)
            assert not any(b.label == "Approve" for b in result.button)
    assert result.session_state["review_context"]["question_id"] == "M9-Q12"
    navigate(result, "post-generation-evaluation-human-review")
    assert result.selectbox(key="post_question").value == "M9-Q12"
    assert not result.form


def test_selected_attempt_and_q05_history_are_preserved(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot)
    result.selectbox(key="post_question").select("M9-Q05").run()
    attempts = snapshot[0]["records"]["M9-Q05"]["attempts"]
    index = result.selectbox(key="post_attempt_M9-Q05").value
    assert attempts[index]["response"]
    result.selectbox(key="post_question").select("M9-Q18").run()
    result.selectbox(key="post_attempt_M9-Q18").select(0).run()
    expected = dict(result.session_state["review_context"])
    navigate(result, "human-review")
    assert result.selectbox(key="unified-review-attempt-M9-Q18").value == 0
    assert result.session_state["review_context"] == expected
    assert not any(b.label == "Approve" for b in result.button)


def test_signed_advanced_still_separate(monkeypatch, snapshot):
    result = app(monkeypatch, snapshot, "human-review")
    result.radio(key="owner_review_mode").set_value("SIGNED_HUMAN_REVIEW (advanced)").run()
    assert not result.exception and not result.error
    assert any("own exact package selection" in c.value for c in result.caption)
    assert any(i.label == "Signing-key passphrase" for i in result.text_input)


@pytest.mark.parametrize("route", ["post-generation-evaluation-human-review", "human-review"])
def test_fail_closed_and_tampered_context(monkeypatch, snapshot, route):
    result = app(monkeypatch, snapshot, route)
    target = dict(result.session_state["review_context"])
    target["request_sha256"] = "0" * 64
    result.session_state["review_context"] = target
    result.run()
    assert not result.exception and result.error
    assert not result.form
    def broken():
        from tools.quality_dashboard.artifacts import ArtifactError
        raise ArtifactError("PRIVATE_DETAILS")
    monkeypatch.setattr(view, "load", broken)
    monkeypatch.setattr(review_view, "load", broken)
    result.run()
    assert not result.exception and result.error and not result.form
    assert "PRIVATE_DETAILS" not in result.error[0].value
