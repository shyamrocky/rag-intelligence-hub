"""Dedicated owner-review page; existing local and signed controls are unchanged."""
import streamlit as st

from apps.knowledge_preparation.generation import ROOT, load
from apps.knowledge_preparation.review_context import ReviewLayout, remember, remembered, selected
from tools.human_review.poc_ui import render as render_review
from tools.quality_dashboard.artifacts import ArtifactError


def render():
    from apps.knowledge_preparation.bot_records import source
    from apps.knowledge_preparation.run_summary import render as render_summary
    st.title("Human Review")
    st.write("Read the answer, inspect its evidence and findings, and record an explicit owner decision.")
    st.caption("No automatic approval or generation · Existing confirmation and technical safeguards remain enforced")
    overview = render_summary(ROOT, loader=load, key='review-overview')
    if source('Human Review', data=overview[2] if overview else None):
        return
    try:
        data, _ = overview[:2] if overview else load()
        context = remembered(data["records"])
        target = st.session_state.get("review_context")
        if context and (st.session_state.get("review_applied_context") != target
                        or "unified-review-question" not in st.session_state
                        or "unified-review-attempt-" + context[1]["question_id"] not in st.session_state):
            record, attempt = context
            qid = attempt["question_id"]
            st.session_state["unified-review-question"] = qid
            st.session_state["unified-review-attempt-" + qid] = record["attempts"].index(attempt)
            st.session_state["poc_confirmed"] = False
            st.session_state["assessment_confirmed"] = False
        st.page_link(st.session_state["kp_pages"]["Post-Generation Evaluation"], label="← Post-Generation Evaluation")
        selector = st.container()
        render_review(ReviewLayout(selector, data["records"]), ROOT)
        if st.session_state.get("owner_review_mode", "LOCAL_POC_REVIEW") == "LOCAL_POC_REVIEW":
            current = selected(data)
            if current:
                st.session_state["review_applied_context"] = remember(current[1])
        else:
            st.caption("Signed advanced review uses its own exact package selection and authentication; local question context does not approve a signed target.")
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        st.error("Review details unavailable or unverified. No acceptance is inferred; verify the selected answer and preserved history before making a decision.")
