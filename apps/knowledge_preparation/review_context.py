"""Source-bound, session-only navigation context; never an approval or execution token."""
import streamlit as st

from tools.benchmark_tracker.adapter import selected_attempt
from tools.quality_dashboard.artifacts import ArtifactError


def identity(attempt):
    return {"question_id": attempt["question_id"], "experiment": attempt["experiment"],
            "result_sha256": attempt["response_file_sha256"],
            "request_sha256": attempt["audit"].get("request_sha256"),
            "evidence_package_sha256": attempt["audit"].get("M8_package_sha256")}


def remembered(records):
    target = st.session_state.get("review_context")
    if target is None:
        return None
    if not isinstance(target, dict):
        raise ArtifactError("INVALID_REVIEW_NAVIGATION_CONTEXT")
    record = records.get(target.get("question_id"))
    if record:
        for attempt in record["attempts"]:
            if identity(attempt) == target:
                return record, attempt
    raise ArtifactError("STALE_OR_UNVERIFIED_REVIEW_NAVIGATION_CONTEXT")


def remember(attempt):
    target = identity(attempt)
    st.session_state["review_context"] = target
    return target


class ReviewLayout:
    """Place the existing question selector above review controls; delegate decisions unchanged."""

    def __init__(self, selector, records):
        self.selector = selector
        self.records = records

    def __getattr__(self, name):
        return getattr(st, name)

    def selectbox(self, label, options, **kwargs):
        key = kwargs.get("key", "")
        if key.startswith("unified-review-attempt-") and key not in st.session_state:
            record = self.records[key.removeprefix("unified-review-attempt-")]
            chosen = selected_attempt(record)
            kwargs["index"] = next(i for i, item in enumerate(record["attempts"])
                                   if item["experiment"] == chosen["experiment"])
        if key != "unified-review-question":
            return st.selectbox(label, options, **kwargs)
        if kwargs["key"] not in st.session_state:
            prior = st.session_state.get("gen_question", st.session_state.get("pg_question"))
            kwargs["index"] = options.index(prior) if prior in options else 0
        with self.selector:
            result = st.selectbox(label, options, **kwargs)
            st.markdown(self.records[result]["question"])
        return result


def selected(data):
    """Mirror the existing review component's exact question and attempt selection."""
    qid = st.session_state.get("unified-review-question")
    record = data["records"].get(qid)
    if not record or not record["attempts"]:
        return None
    index = st.session_state.get("unified-review-attempt-" + qid, len(record["attempts"]) - 1)
    if type(index) is not int or not 0 <= index < len(record["attempts"]):
        raise ArtifactError("INVALID_SELECTED_REVIEW_ATTEMPT")
    return record, record["attempts"][index]

