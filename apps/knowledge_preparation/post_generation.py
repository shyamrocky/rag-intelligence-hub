"""Final quality journey; reuse the unchanged local/signed Human Review workflow."""
from collections import Counter

import streamlit as st

from apps.knowledge_preparation.generation import ROOT, display, load, phase_rows, timing_for
from apps.knowledge_preparation.review_context import remember, remembered
from tools.benchmark_tracker.adapter import selected_attempt
from tools.quality_dashboard.artifacts import ArtifactError


def summary(record, attempt, tracker):
    qid = attempt["question_id"]
    st.subheader("Evidence supplied → Answer findings → Owner decision")
    st.caption(qid + " · " + record["reference"]["cohort_label"])
    with st.container(border=True):
        st.subheader("1 · Evidence supplied and cited")
        target = record.get("target")
        coverage = target.get("m8", {}) if target else {}
        missing = coverage.get("missing_group_ids", [])
        exact_package = bool(coverage.get("M8_package_sha256") and
                             coverage["M8_package_sha256"] == attempt["audit"].get("M8_package_sha256"))
        tokens = (attempt.get("row") or {}).get("evidence_BGE_tokens")
        if tokens is None and exact_package:
            tokens = coverage.get("exact_tokens")
        st.table([{"Measurement": label, "Recorded value": display(value)} for label, value in [
            ("Complete Evidence Units supplied", attempt.get("supplied_parents")),
            ("Evidence package size · BGE tokens", tokens),
            ("Distinct Evidence Units cited", len(attempt["cited_parent_ids"]) if attempt.get("response") else None),
        ]])
        if not record["group_ids"]:
            st.write("Unsupported benchmark question: no positive evidence-group denominator.")
            st.caption("Retrieved documents do not establish answerability. An abstention still needs evidence-aware review.")
        elif coverage:
            st.write("Saved evidence coverage: **" + ("Known evidence gaps" if missing else "All required human-approved evidence groups delivered") + "**")
            if missing:
                st.warning("Missing human-approved evidence: " + ", ".join(missing))
        else:
            st.info("Evidence delivery measurement unavailable.")
        st.caption("Saved coverage matches the selected request's evidence-package identity." if exact_package
                   else "Saved coverage is a historical benchmark reference; equivalence to the selected evidence package is not established.")
        st.caption("This is the saved benchmark delivery measurement, not a new semantic assessment. "
                   "Exact supplied evidence and request bindings are available in the trace on Human Review. "
                   "Complete evidence delivery does not prove a correct answer; a missing labeled group does not alone prove an incorrect answer.")
        response = attempt.get("response")
        if response:
            st.write("Model-declared response: **" + response["status"] + "** · "
                     + str(len(response.get("claims", []))) + " reported claims")
            with st.expander("Model-reported requirement coverage — not independent assessment"):
                st.dataframe(response.get("requirement_coverage", []), hide_index=True)
        else:
            st.warning("No accepted structured response. Returned output remains available for diagnostic triage where captured; it cannot be approved as a valid response.")
        st.page_link(st.session_state["kp_pages"]["Knowledge Retrieval"], label="Inspect evidence discovery and context delivery →")
        st.page_link(st.session_state["kp_pages"]["Pre-Generation"], label="Inspect saved prompt, token and cost qualification →")
    post = attempt.get("validation") or {}
    with st.container(border=True):
        st.subheader("2 · Recorded technical findings")
        st.write("Checks whether the response follows the required structure, cites authorized evidence, and reproduces "
                 "supporting quotations faithfully while tolerating harmless formatting differences.")
        st.caption("These checks do not establish factual correctness or answer completeness. Original findings remain unchanged; later assessments are separate.")
        st.table([{"Check": name, "What it checks": meaning, "Original finding": "Verified supplied evidence" if value == "LIVE_M8_VALIDATED" else display(value)} for name, meaning, value in [
            ("Response structure", "Required fields, types and status relationships.", post.get("structural_validation", post.get("structural"))),
            ("Source integrity", "Authentic, authorized evidence bound to the supplied request.", post.get("source_integrity")),
            ("Citation validity", "Cited Evidence Units belong to the authorized evidence.", post.get("citation_validity")),
        ]])
        counts = Counter(q.get("outcome") for q in post.get("quotation_fidelity", []) if q.get("outcome"))
        st.write("Original quotation fidelity: " + ("; ".join(f"{n} {kind}" for kind, n in sorted(counts.items())) or "NOT_MEASURED"))
        st.caption("Whitespace, verified PDF word splitting and other approved presentation differences are distinct from substantive misquotation. No answer text is silently repaired.")
        st.write("Original validation outcome: **" + post.get("overall_status", post.get("status", "UNAVAILABLE")) + "**")
        st.caption("REVIEW_REQUIRED is an overall outcome: essential assessments remain unresolved. It does not mean every technical check failed; read the individual findings above.")
    current = next(row for row in tracker["rows"] if row["Question"] == qid)
    with st.container(border=True):
        st.subheader("3 · Review guidance and recorded status")
        st.markdown("**Review guidance — what needs to be assessed**")
        st.caption("The table below lists review questions, not assessment results for this answer. Actual grounding, completeness and qualification findings are shown on the separate Human Review page when available.")
        st.table([
            {"Dimension": "Claim grounding", "What to assess": "Does authentic cited evidence support each material claim?"},
            {"Dimension": "Completeness", "What to assess": "Does the answer address every required part of the question?"},
            {"Dimension": "Qualifications and conflicts", "What to assess": "Are material limitations and conflicting evidence disclosed?"},
            {"Dimension": "Abstention", "What to assess": "If the model declined to answer, is its explanation justified by the supplied evidence?"},
        ])
        st.markdown("**Recorded findings and owner decision**")
        if current.get("Experiment") == attempt["experiment"]:
            st.write("Current owner review: **" + current["Owner review"] + "**")
            st.write(current["Main findings"].replace("M8 delivered", "Evidence assembly delivered"))
            if current.get("Reassessment reference"):
                st.write("Separate technical reassessment: **" + current["Validation"] + "**")
        else:
            st.info("Historical attempt selected. Current-attempt assessments and owner decisions are not transferred to this answer.")
        st.caption("Model declarations and provisional assessments are not independent acceptance. Unresolved semantic judgments remain REVIEW_REQUIRED. "
                   "OWNER_APPROVED_POC is a local owner decision, not cryptographically authenticated VALIDATED status.")
        timing = timing_for(attempt)
        with st.expander("Execution timing and exact assessment provenance"):
            if timing:
                st.table(phase_rows(timing))
            else:
                st.info("Stage timings: NOT_MEASURED")
            st.json({"request_sha256": attempt["audit"].get("request_sha256"),
                     "evidence_package_sha256": attempt["audit"].get("M8_package_sha256"),
                     "source": attempt.get("source"),
                     "assessment_reference": current.get("Reassessment reference")
                     if current.get("Experiment") == attempt["experiment"] else None})


def render():
    from apps.knowledge_preparation.bot_records import source
    from apps.knowledge_preparation.run_summary import render as render_summary
    st.title("Post-Generation Evaluation")
    st.write("Inspect evidence delivery, recorded technical findings and review readiness.")
    st.caption("Read-only saved findings · No model calls, evaluation execution or owner decisions")
    overview = render_summary(ROOT, loader=load, key='post-overview')
    if source('Post-Generation Evaluation', data=overview[2] if overview else None):
        return
    st.info("Evidence supplied → Model response → Technical checks → Human Review")
    try:
        data, tracker = overview[:2] if overview else load()
        records = {qid: record for qid, record in data["records"].items() if record["attempts"]}
        if not records:
            st.info("NOT_RUN — no verified generation attempts.")
            return
        context = remembered(records)
        target = st.session_state.get("review_context")
        if context and (st.session_state.get("post_applied_context") != target
                        or "post_question" not in st.session_state
                        or "post_attempt_" + context[1]["question_id"] not in st.session_state):
            record, attempt = context
            st.session_state["post_question"] = attempt["question_id"]
            st.session_state["post_attempt_" + attempt["question_id"]] = record["attempts"].index(attempt)
        ids = list(records)
        if st.session_state.get("post_question") not in ids:
            prior = st.session_state.get("gen_question", st.session_state.get("pg_question"))
            st.session_state["post_question"] = prior if prior in ids else ids[0]
        qid = st.selectbox("Question", ids, key="post_question",
                           format_func=lambda q: q + " — " + records[q]["question"])
        record = records[qid]
        st.markdown(record["question"])
        default = selected_attempt(record)
        with st.expander("Generation attempt history — original results preserved"):
            index = st.selectbox("Exact response / attempt", range(len(record["attempts"])),
                index=record["attempts"].index(default), key="post_attempt_" + qid,
                format_func=lambda i: f"Attempt {i + 1} · " + record["attempts"][i]["status"])
        attempt = record["attempts"][index]
        st.session_state["post_applied_context"] = remember(attempt)
        summary(record, attempt, tracker)
        st.page_link(st.session_state["kp_pages"]["Human Review"], label="Continue to Human Review →")
        st.caption("The selected question and exact answer attempt follow this link. Reviewing or approving an answer requires explicit action on Human Review.")
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        st.error("UNAVAILABLE — generation, review or selected-answer bindings failed verification. No acceptance is inferred.")
