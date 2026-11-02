"""Actual generation observations using the preserved benchmark and runner readers."""
from collections import Counter
from pathlib import Path

import streamlit as st

from tools.answer_quality.abstention import render_response
from tools.benchmark_tracker.adapter import build, returned_status, selected_attempt
from tools.human_review.observation_review import load_output, validate_target
from tools.human_review.response_diagnostics import capture_reference
from tools.quality_dashboard.artifacts import ArtifactError
from tools.quality_dashboard.completion_adapter import load_completed

ROOT = Path(__file__).resolve().parents[2]
UNAVAILABLE = "UNAVAILABLE"
STAGE_NAMES = {
    "SAVED_INPUT_VERIFICATION": "Saved retrieval input verification",
    "M8_EVIDENCE_ASSEMBLY": "Evidence reconstruction and assembly",
    "M8_SOURCE_VALIDATION": "Evidence source validation",
    "PROMPT_ASSEMBLY": "Prompt assembly",
    "MODEL_PREFLIGHT": "Model qualification overhead",
    "MODEL_METADATA": "Model access and capability check",
    "MODEL_TOKEN_COUNT": "Exact request-token count",
    "LLM_GENERATION": "Generation request",
    "POST_GENERATION_VALIDATION": "Post-generation validation",
    "ARTIFACT_PERSISTENCE": "Result persistence",
    "REQUEST_BINDING_AND_POLICY": "Request integrity and policy checks",
    "GENERATION_SERVICE_OVERHEAD": "Generation service overhead",
    "FINAL_SOURCE_CHECK": "Final source check",
}


PHASES = {
    "Request preparation": {"SAVED_INPUT_VERIFICATION", "M8_EVIDENCE_ASSEMBLY", "M8_SOURCE_VALIDATION",
                            "PROMPT_ASSEMBLY", "MODEL_PREFLIGHT", "MODEL_METADATA", "MODEL_TOKEN_COUNT",
                            "REQUEST_BINDING_AND_POLICY"},
    "Generation": {"LLM_GENERATION", "GENERATION_SERVICE_OVERHEAD"},
    "Post-generation": {"POST_GENERATION_VALIDATION", "ARTIFACT_PERSISTENCE", "FINAL_SOURCE_CHECK"},
}


def duration_label(milliseconds):
    return UNAVAILABLE if milliseconds is None else f"{milliseconds:,.0f} ms / {milliseconds / 1000:.2f} sec"


def phase_rows(timing):
    if not timing:
        return []
    rows = []
    total = timing["end_to_end_ms"]
    for phase, stages in PHASES.items():
        measured = [s["duration_ms"] for s in timing["stages"] if s["stage"] in stages and s["duration_ms"] is not None]
        elapsed = sum(measured) if measured else None
        rows.append({"Phase": phase, "Seconds": elapsed / 1000 if elapsed is not None else None,
                     "Share of end-to-end": 100 * elapsed / total if elapsed is not None and total > 0 else None})
    known = set().union(*PHASES.values())
    other = timing["unattributed_overhead_ms"] + sum(s["duration_ms"] for s in timing["stages"]
        if s["stage"] not in known and s["duration_ms"] is not None)
    if other > 0:
        rows.append({"Phase": "Other / uninstrumented time", "Seconds": other / 1000,
                     "Share of end-to-end": 100 * other / total if total > 0 else None})
    return rows


def load():
    data = load_completed(ROOT)
    return data, build(ROOT, data)


def display(value):
    if value is None:
        return UNAVAILABLE
    return f"{value:,}" if type(value) is int else str(value)


def timing_for(attempt):
    return attempt.get("run", {}).get("timings", {}).get(attempt["question_id"])


def timing_rows(timing):
    if not timing:
        return []
    return [{"Stage": STAGE_NAMES.get(row["stage"], "Other recorded stage"),
             "Phase": next((phase for phase, stages in PHASES.items() if row["stage"] in stages), "Other recorded stage"),
             "Measurement status": row["status"],
             "Exclusive seconds": round(row["duration_ms"] / 1000, 3) if row["duration_ms"] is not None else None}
            for row in timing["stages"]]


def render_candidate(candidate):
    """Display returned declarations without silently accepting a failed contract."""
    if not isinstance(candidate, dict):
        return
    if isinstance(candidate.get("answer"), str) and candidate["answer"]:
        st.markdown(candidate["answer"], unsafe_allow_html=False)
    if candidate.get("status") == "ABSTAINED":
        st.subheader("Unable to answer from available evidence")
    reasons = candidate.get("missing_information")
    if isinstance(reasons, list):
        for reason in reasons:
            if isinstance(reason, str):
                st.markdown(reason, unsafe_allow_html=False)


def returned_output(attempt):
    if attempt.get("response") is not None:
        render_response(st, attempt["response"])
        return attempt["response"]
    st.warning("No accepted structured response. A returned answer may still exist in the captured output. "
               "The contract failure is preserved; it is not an independent factual-error judgment.")
    if not attempt.get("run"):
        st.info("Original returned text is unavailable for this historical attempt.")
        return None
    try:
        output = load_output(ROOT, attempt)  # Existing localhost + verified-capture boundary.
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        st.info("Captured returned output is unavailable or unverified. Protected inspection requires direct localhost access.")
        return None
    candidate = output.get("candidate")
    if isinstance(candidate, dict):
        st.caption("Captured model output below is untrusted and did not pass the response contract.")
        render_candidate(candidate)
        return candidate
    for text in output.get("text_parts", []) + output.get("refusals", []):
        st.text(text)
    if not output.get("text_parts") and not output.get("refusals"):
        st.info("Raw response unavailable. No original text can be recovered from a hash alone.")
    return None


def declarations(candidate):
    if not isinstance(candidate, dict):
        return
    st.caption("Model-reported claims, requirement coverage, qualifications and conflicts are declarations—not independent findings.")
    for title, key in [("Missing information", "missing_information"),
                       ("Relevant qualifications", "relevant_qualifications"), ("Reported conflicts", "conflicts_detected")]:
        with st.expander(title):
            items = candidate.get(key)
            if items:
                st.json(items)
            else:
                st.caption("None reported. An empty list does not establish compliance or absence of material issues.")
    with st.expander("Claims, citation IDs, supporting quotations and reported requirement coverage"):
        st.json({key: candidate.get(key) for key in ("claims", "requirement_coverage")})


def render_raw(attempt):
    with st.expander("Protected raw-response diagnostics"):
        if not attempt.get("run"):
            st.info("Raw capture not recorded for this historical attempt. Its structured answer, if present, remains preserved.")
            return
        try:
            validate_target(ROOT, attempt)
            receipt, path = capture_reference(ROOT, {"run": attempt["run"], "row": attempt["row"]})
            if receipt is None:
                st.info("Raw response unavailable—this historical execution did not retain a raw provider body.")
                return
            st.write("Capture outcome: " + receipt["status"])
            if path is None:
                st.warning("Raw response unavailable. Capture did not produce a verified readable artifact.")
                return
            st.caption("Verified protected artifact available. Provider output is untrusted data; viewing it does not validate the answer.")
            if st.checkbox("Show protected raw provider response", key="gen_raw_" + attempt["response_file_sha256"]):
                from tools.human_review.local_poc import require_localhost
                require_localhost()
                validate_target(ROOT, attempt)
                _, verified = capture_reference(ROOT, {"run": attempt["run"], "row": attempt["row"]})
                if verified is None:
                    raise ArtifactError("RAW_UNAVAILABLE")
                st.code(verified.read_bytes().decode("utf-8", errors="replace"), language="json")
        except (ArtifactError, ValueError, KeyError, OSError, TypeError):
            st.warning("Raw response unavailable or unverified. No unverified output is shown.")


def render():
    from apps.knowledge_preparation.bot_records import source
    if source('Generation'):
        return
    st.title("Generation")
    st.write("What the model returned, what execution measured, and what still needs review.")
    st.caption("Read-only saved live results · No generation, retries, evaluation or owner decisions on refresh")
    st.info("Prepared request → Model response → Response capture and contract checks → Technical validation → Human Review")
    try:
        data, tracker = load()
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        st.error("UNAVAILABLE — generation or tracker artifact bindings failed verification.")
        return
    summary = tracker["summary"]
    for col, label, count in zip(st.columns(4),
            ["Questions attempted", "Accepted structured responses", "Without accepted response", "Real attempt records"],
            [summary["attempted_questions"], summary["generation_completed"],
             summary["attempted_without_parsed_answer"], summary["attempt_records"]], strict=True):
        with col.container(border=True):
            st.metric(label, count)
    st.write("**Measured-use estimated cost across all real attempts:** $" + summary["measured_attempt_cost_usd"])
    st.caption(f"{summary['unknown_cost_attempts']} attempt(s) have unavailable cost. Failed attempts can still incur cost. "
               "These estimates are not invoices or account balances. Mock results are excluded from these totals.")
    with st.expander("Benchmark results and batch totals"):
        st.dataframe([{key: row.get(key) for key in ("Stage", "Question", "Model status", "Contract", "Validation", "Owner review",
                                                    "Estimated API cost USD", "Attempts")}
                      for row in tracker["rows"]], hide_index=True, width="stretch")
        st.dataframe(tracker["batches"], hide_index=True, width="stretch")
        st.caption("Model status is a declaration; on a rejected contract it is untrusted. Parsed responses do not establish answer correctness.")
    records = data["records"]
    ids = list(records)
    if st.session_state.get("gen_question") not in ids:
        prior = st.session_state.get("pg_question", st.session_state.get("kr_question"))
        st.session_state["gen_question"] = prior if prior in ids else ids[0]
    qid = st.selectbox("Question", ids, key="gen_question",
                       format_func=lambda question_id: f"{question_id} — {records[question_id]['question']}")
    record = records[qid]
    st.caption(record["reference"]["cohort_label"])
    st.markdown(record["question"])
    attempt = selected_attempt(record)
    if not attempt:
        st.info("NOT_RUN — no verified real generation attempt.")
        return
    with st.expander("History / Technical details — select an attempt"):
        attempts = record["attempts"]
        default = next(i for i, item in enumerate(attempts) if item["experiment"] == attempt["experiment"])
        index = st.selectbox("Saved generation attempt", range(len(attempts)), index=default,
                             format_func=lambda i: f"Attempt {i + 1} · "
                             f"{'Structured response retained' if attempts[i].get('response') else 'No accepted structured response'}",
                             key="gen_attempt_" + qid)
        attempt = attempts[index]
        st.caption("Latest native attempt is the default. The original funded answer is the historical default. "
                   "Earlier attempts remain separate; reviews do not transfer across answers.")
    current = next(row for row in tracker["rows"] if row["Question"] == qid)
    is_current = current.get("Experiment") == attempt["experiment"]
    if not is_current:
        st.info("Viewing an earlier attempt. Current-attempt reassessments and owner decisions are not applied to this output.")
    audit, usage = attempt["audit"], attempt.get("usage", {})
    declared, contract, _ = returned_status(ROOT, attempt)
    with st.container(border=True):
        st.subheader("1 · Model response")
        contract_label = "Structured response accepted" if contract == "ACCEPTED_STRUCTURED_RESPONSE" else "Structured response rejected"
        st.write(f"Model-declared status: **{declared}** · Response contract: **{contract_label}**")
        st.caption("Model: " + str(audit.get("model", UNAVAILABLE)) + " · Prompt: " + str(audit.get("prompt_template", UNAVAILABLE))
                   + " · Response schema: " + str(audit.get("response_schema", UNAVAILABLE)))
        candidate = returned_output(attempt)
        declarations(candidate)
    with st.container(border=True):
        st.subheader("2 · Actual usage and estimated cost")
        measurements = [
            ("Input tokens", "Actual recorded input usage for this attempt, not a preflight estimate.", usage.get("input_tokens")),
            ("Cached input reads", "Input tokens served from an existing provider cache; part of input usage.", usage.get("cached_input_tokens")),
            ("Cache-write tokens", "Recorded cache-write usage; not added again to total tokens.", usage.get("cache_write_tokens")),
            ("Output tokens", "Actual recorded output usage.", usage.get("output_tokens")),
            ("Reasoning tokens", "Recorded reasoning-token detail; not added again to output usage.", usage.get("reasoning_tokens")),
            ("Total usage tokens", "Recorded provider total—not input plus every cached/reasoning subcategory.", usage.get("total_tokens")),
            ("Generation request duration", "Recorded local request/adapter elapsed time, not the whole question workflow or independently reported provider inference time.", duration_label(usage.get("latency_ms"))),
            ("Actual-usage-based estimated cost · USD", "Estimated from measured usage and its historical pricing policy; not an invoice.", usage.get("total_estimated_cost_usd")),
        ]
        st.table([{"Measurement": label, "Description": description, "Recorded value": display(value)}
                  for label, description, value in measurements])
        st.caption("Missing usage remains unavailable; an unknown cost is not treated as zero. Preflight ceilings and reservations are separate from actual-use estimates.")
    with st.container(border=True):
        st.subheader("3 · Execution latency breakdown")
        timing = timing_for(attempt)
        if not timing:
            st.info("NOT_MEASURED — no sealed stage-timing receipt for this attempt.")
        else:
            st.metric("Question end-to-end duration", f"{timing['end_to_end_ms'] / 1000:,.2f} sec")
            phases = phase_rows(timing)
            st.table([{"Phase": row["Phase"], "Duration · seconds":
                       f"{row['Seconds']:,.3f}" if row["Seconds"] is not None else "NOT_MEASURED",
                       "Share of end-to-end": f"{row['Share of end-to-end']:.1f}%"
                       if row["Share of end-to-end"] is not None else UNAVAILABLE} for row in phases])
            measured = [row for row in phases if row["Seconds"] is not None]
            if measured:
                slowest = max(measured, key=lambda phase: phase["Seconds"])
                share = f" ({slowest['Share of end-to-end']:.1f}% of end-to-end time)" if slowest["Share of end-to-end"] is not None else ""
                st.markdown(f"**Longest phase: {slowest['Phase']} — {slowest['Seconds']:,.2f} sec{share}.**")
            st.caption("Request preparation includes saved-input checks, evidence reconstruction/source validation, prompt "
                       "assembly, request-policy checks and model qualification. Generation includes the request and service "
                       "overhead. Post-generation includes response validation, persistence and the final source check.")
            st.caption("Exclusive measured durations are grouped once, without counting nested work twice. "
                       "Other / uninstrumented time is shown separately. Display rounding can create small visible differences.")
            with st.expander("Individual stage timings and full-precision technical details"):
                st.dataframe(timing_rows(timing), hide_index=True, width="stretch")
                st.json({"end_to_end_ms": timing["end_to_end_ms"], "stages": timing["stages"],
                         "unattributed_overhead_ms": timing["unattributed_overhead_ms"],
                         "recorded_generation_adapter_ms": usage.get("latency_ms")})
            st.caption("End-to-end excludes shared run setup, timing-receipt publication and shared final sealing. "
                       "Provider-reported inference latency is not independently measured here.")
    with st.container(border=True):
        st.subheader("4 · Technical findings and Human Review handoff")
        post = attempt.get("validation") or {}
        st.write("Original technical outcome: **" + post.get("overall_status", post.get("status", "NOT_RUN")) + "**")
        completeness = post.get("completeness")
        completeness = completeness.get("outcome") if isinstance(completeness, dict) else completeness
        st.table([{"Quality dimension": label, "Original recorded finding": display(value)} for label, value in [
            ("Response structure", post.get("structural_validation", post.get("structural"))),
            ("Citation and source integrity", post.get("citation_validity")),
            ("Semantic grounding", post.get("semantic_status")),
            ("Requirement completeness", completeness),
            ("Material qualifications", post.get("material_qualifications", post.get("qualification_status"))),
            ("Conflicts", post.get("conflicts")),
        ]])
        counts = Counter(q.get("outcome") for q in post.get("quotation_fidelity", []) if q.get("outcome"))
        if counts:
            st.write("Original quotation fidelity: " + "; ".join(f"{number} {kind}" for kind, number in sorted(counts.items())))
        for issue in audit.get("response_diagnostics", []):
            st.warning("Response contract finding: " + issue.get("code", "UNAVAILABLE") + " · field " + str(issue.get("path", []))
                       + " · " + str(issue.get("rule", "See technical provenance")))
        if is_current:
            if current.get("Reassessment reference"):
                st.write("Latest separate technical assessment: **" + current["Validation"] + "**")
            st.write("Owner review state: **" + current["Owner review"] + "**")
            st.write(current["Main findings"].replace("M8 delivered", "Evidence assembly delivered"))
        st.caption("Original verdicts are preserved. Mechanical checks, model declarations, separate assessments and owner decisions "
                   "are different findings. Local POC approval is not cryptographically authenticated formal validation.")
        st.page_link(st.session_state["kp_pages"]["Post-Generation Evaluation"], label="Post-Generation Evaluation →")
        st.page_link(st.session_state["kp_pages"]["Human Review"], label="Human Review →")
        st.caption("The separate 8516 Human Review page includes the existing owner review controls. The preserved Master Dashboard also remains available; "
                   "8514 must be running only when using that preserved link. No approval controls are enabled on the Generation page.")
        st.link_button("Open preserved Human Review on 8514 ↗", "http://127.0.0.1:8514/generation-runner")
    render_raw(attempt)
    with st.expander("Technical details — exact attempt provenance"):
        st.json({"experiment": attempt["experiment"], "status": attempt["status"],
                 "request_sha256": audit.get("request_sha256"), "evidence_package_sha256": audit.get("M8_package_sha256"),
                 "result_sha256": attempt["response_file_sha256"], "pricing_version": usage.get("pricing_version"),
                 "response_status": audit.get("response_status"), "recorded_generation_adapter_ms": usage.get("latency_ms"),
                 "blocking_reasons": audit.get("blocking_reasons", []),
                 "source": attempt.get("source"),
                 "separate_assessment_reference": current.get("Reassessment reference") if is_current else None})
    if tracker["unverified_review_records"] or tracker["unverified_assessment_records"]:
        st.caption("Some review or assessment records failed verification and were not used to establish acceptance.")
