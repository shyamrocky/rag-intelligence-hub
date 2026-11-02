"""Cohort-aware master dashboard. Source authority and generation remain elsewhere."""
from pathlib import Path

import streamlit as st

from . import ui as historical_ui
from .artifacts import ArtifactError
from .completion_adapter import filter_completed as filter_questions
from .completion_adapter import load_completed as load_expanded
from .expanded_adapter import COHORT_FILTERS, NOT_MEASURED


def summary(data):
    s = data["summary"]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("Reconciled questions", s["questions"]),
        ("Answerable / unsupported", f"{s['answerable']} / {s['unsupported']}"),
        ("Generated / pending", f"{s['generation_completed']} / {s['pending_generation']}"),
        ("Post-generation checks", f"{s['post_checked']} / {s['generation_completed']}")]):
        col.metric(label, value)
    if 'attempt_records' in s:
        st.caption(f"{s['attempted_questions']} questions attempted · {s['attempted_without_parsed_answer']} without parsed answers · "
                   f"{s['never_attempted']} never attempted · {s['attempt_records']} total attempt records")
        st.caption(f"Measured cost across all attempts: ${s['measured_attempt_cost_usd']} · "
                   f"{s['unknown_cost_attempts']} attempts with unavailable cost. Reservations are separate.")
    st.caption(f"{s['mandatory_groups']} referenced mandatory groups across answerable records. "
               f"Frozen subset remains {data['frozen_data']['summary']['questions']} questions / "
               f"{data['frozen_data']['summary']['groups']} approved groups. Unsupported controls have no positive groups.")


def home(data):
    st.title("RAG Intelligence Hub")
    st.caption("Retrieval, Evidence Integrity, Grounded Generation & Quality Evaluation")
    summary(data)
    left, right = st.columns(2)
    with left:
        st.page_link(st.session_state["explorer_page"], label="Candidate–Parent Explorer", icon="🔎")
        st.write("The existing sealed explorer retains its original question scope and detailed candidate/parent navigation.")
    with right:
        st.page_link(st.session_state["quality_page"], label="End-to-End Quality & Telemetry", icon="📊")
        st.write("Expanded, cohort-aware historical evaluation, generation and post-generation records.")
    st.dataframe(data["cohorts"], hide_index=True, width="stretch")
    s = data["summary"]
    st.write(f"Historical M7 coverage: {s['M7_evaluated_questions']}/{s['questions']} questions · "
             f"M8 coverage in any historical configuration: {s['M8_evaluated_questions_any_configuration']}/{s['questions']}")
    st.info(f"RRF Top-30 / M8 128K has measurements for {s['M8_target_evaluated_questions']} questions. "
            "A historical Top-10 / 32K result does not establish Top-30 / 128K delivery.")
    for publication in data.get("completion_publications", []):
        st.write("RRF-30 / M8-128K completion measurements")
        st.dataframe(publication["cohorts"], hide_index=True)
        st.caption("Direct metrics retain separate strict and original M9 overlap definitions. Unsupported controls have no recall denominator.")
        historical_ui.provenance(data, [publication["results_ref"], publication["manifest_ref"], publication.get("report_ref"), publication.get("review_ref")])
    st.caption("Reconciliation and local M7/M8 measurements complete; owner review pending. "
               "No generation, provider, retrieval or evaluation script runs on refresh.")
    historical_ui.provenance(data, [data["reference_ref"]])


def overview(data, ids):
    rows = []
    for qid in ids:
        r = data["records"][qid]
        a, f = r["latest"], r["target"]
        rows.append({"Question": qid, "Cohort": r["reference"]["cohort_label"],
            "Answerability": r["reference"]["answerability"],
            "Labels": r["reference"]["evidence_label_status"],
            "M7 historical": "REUSED_HISTORICAL" if r["retrieval_measurements"] else "UNAVAILABLE",
            "M8 historical": "REUSED_HISTORICAL" if r["m8_measurements"] else "UNAVAILABLE",
            "M8 target delivered": (f"{f['m8']['delivered_groups']}/{len(r['group_ids'])}" if r["group_ids"] else "NOT_APPLICABLE_UNSUPPORTED") if f else NOT_MEASURED,
            "Generation": a["response"]["status"] if a else "NOT_RUN" if not r["attempts"] else "FAILED",
            "Post-generation": a["validation"]["overall_status"] if a and a["validation"] else
                               "PENDING_REVIEW" if a else "NOT_RUN"})
    return rows


def quality(data):
    st.title("End-to-End Quality & Telemetry")
    st.caption("Expanded benchmark reference layer · M9 is offline evaluation, not a runtime stage.")
    summary(data)
    with st.expander("Historical benchmark comparisons — preserve original denominators"):
        baseline = data["frozen_data"]
        st.caption("Cohorts A/B only: original frozen subset. These are saved strict-witness comparisons, "
                   "not expanded-benchmark aggregate scores.")
        labels = {r["cohort_id"]: r["cohort_label"] for r in data["cohorts"]}
        st.text(labels["A"] + " + " + labels["B"])
        st.dataframe([{"Strategy": name, "Direct groups": row["complete_groups"],
                       "Required groups": baseline["summary"]["groups"],
                       "Complete questions": row["complete_questions"],
                       "Question denominator": baseline["summary"]["questions"],
                       "Mean candidates": row["average_candidates"]}
                      for name, row in baseline["selection_comparison"].items()], hide_index=True)
        st.dataframe(baseline["budget_comparison"], hide_index=True)
        st.caption("Saved M8 arms: A RRF-10, B RRF-30, C supplementation Stage 1 private order adapter. "
                   "Reused rows are not additional independently executed experiments.")
        st.caption("Original M9 answerable scope is cohorts A/C; unsupported cohort D remains separate; "
                   "NLP cohort B was added later.")
        st.text(labels["A"] + " + " + labels["C"])
        st.dataframe([{"Mode": mode, "Answerable denominator": result["answerable_denominator"],
                       "Unsupported controls": result["unsupported_denominator"],
                       "Required group denominator": result["required_group_denominator"],
                       "Recall@10 macro": result["retrieval"]["10"]["equivalence_aware_Recall_macro"],
                       "Complete parent questions@10": result["retrieval"]["10"]["all_required_complete_count"],
                       "MRR@10": result["MRR_at_10"]}
                      for mode, result in baseline["original_m9"]["summary"].items()], hide_index=True)
        historical_ui.provenance(data, [baseline["original_m9"]["artifact_ref"]])
    with st.expander("Cohort coverage and measurement scope"):
        st.dataframe(data["cohorts"], hide_index=True, width="stretch")
        st.caption("M7/M8 evaluated means an actual historical measurement exists. "
                   "Post-validated counts deterministic receipts, including indeterminate qualifications; "
                   "it does not mean independently validated answers.")
    columns = st.columns(4)
    cohort = columns[0].selectbox("Cohort", list(COHORT_FILTERS), key="expanded_cohort")
    generation_filter = columns[1].selectbox("Generation status", ["All", "COMPLETED", "NOT_RUN", "FAILED_ONLY"], key="expanded_generation_filter")
    evaluation_filter = columns[2].selectbox("Evaluation availability", ["All", "M7 available", "M8 available", "Target M8 available", "Target M8 not measured"], key="expanded_evaluation_filter")
    answerability = columns[3].selectbox("Answerability", ["All", "Answerable", "Unsupported"], key="expanded_answerability")
    ids = filter_questions(data, cohort=cohort, generation=generation_filter,
                           evaluation=evaluation_filter, answerability=answerability)
    if not ids:
        st.info("No questions match these filters. No pipeline stage was executed.")
        return
    with st.expander("Filtered question journey overview"):
        st.dataframe(overview(data, ids), hide_index=True, width="stretch")
    if st.session_state.get("expanded_question") not in ids:
        st.session_state["expanded_question"] = ids[0]
    qid = st.selectbox("Shared question", ids, key="expanded_question",
        format_func=lambda q: q + " · " + data["records"][q]["reference"]["cohort_label"])
    r = data["records"][qid]
    st.text(r["question"])
    st.caption(r["reference"]["cohort_label"])
    st.caption("Question → M7 discovery → M8 verified delivery → Prompt preparation → Generation → Post-generation")
    a = r.get("latest_attempt") or r["latest"]
    if r["attempts"]:
        attempts = {x["experiment"]: x for x in r["attempts"]}
        chosen = st.selectbox("Generation experiment", list(attempts),
            index=list(attempts).index(a["experiment"]) if a else 0,
            format_func=lambda name: name.rsplit("/", 1)[-1], key="expanded_attempt_" + qid)
        a = attempts[chosen]
        st.caption("All tabs use this question and selected attempt. Generation metrics retain their exact bound configuration.")
    tabs = st.tabs(["Retrieval Pipeline Telemetry", "Generation — Output & Telemetry", "Post-Generation Validation"])
    with tabs[0]:
        pipeline(data, r, a)
    with tabs[1]:
        st.caption(r["reference"]["cohort_label"])
        from .response_ui import render as render_response
        render_response(data, r, a)
        if r["reference"]["answerability"] == "UNSUPPORTED":
            st.warning("An ABSTAINED declaration would not establish correct abstention; independent review is required. "
                       "An ANSWERED declaration would not establish corpus support.")
    with tabs[2]:
        post(data, r, a)
    with st.expander("Benchmark generation readiness — preparation only"):
        plan = next(x for x in data["run_plan"]["questions"] if x["question_id"] == qid)
        st.text(plan["historical_evidence_state"])
        st.text(plan["candidate_inputs"])
        for reason in plan["blockers"]:
            st.text(reason)
        st.caption("Historical measurements are not a reusable evidence authorization. Fresh live M8 validation "
                   "and exact per-request model/token/context/cost preflight require separate authorization.")
    st.page_link(st.session_state["explorer_page"], label="Open preserved Candidate–Parent Explorer")
    st.caption("Explorer scope remains the original frozen questions. Use original source-inspection interfaces "
               "for authoritative complete parents; the telemetry view never exposes parent payloads.")
    historical_ui.provenance(data, [data["reference_ref"]])


def pipeline(data, r, attempt):
    st.subheader("Retrieval Pipeline Telemetry — M7 / M8 / M9 / Pre-Generation")
    st.caption(r["reference"]["cohort_label"])
    f = r["target"]
    if r.get("completion"):
        st.caption("Completion scoring method: " + r["completion"].get("scoring_method", "BLOCKED"))
        if r["completion"]["status"] == "BLOCKED":
            st.error("BLOCKED — " + r["completion"]["reason"])
    st.markdown("#### Current experimental journey: RRF Top-30 → M8 128K BGE tokens")
    if f:
        st.dataframe([{"Measurement": "Direct groups (method shown above)", "Count": (f["retrieval"]["complete_groups"] if r["group_ids"] else "NOT_APPLICABLE"), "Required": len(r["group_ids"])},
                      {"Measurement": "Evidence-parent groups located", "Count": (f["retrieval"]["parent_located_groups"] if r["group_ids"] else "NOT_APPLICABLE"), "Required": len(r["group_ids"])},
                      {"Measurement": "Groups actually delivered", "Count": (f["m8"]["delivered_groups"] if r["group_ids"] else "NOT_APPLICABLE"), "Required": len(r["group_ids"])}], hide_index=True)
        m = f["m8"]
        st.write(f"{m.get('measurement', 'REUSED_HISTORICAL')} · candidates {m['candidate_count']} · included parents {m['included_parents']} · "
                 f"omitted parents {m['omitted_parents']} · BGE tokens {m['exact_tokens']:,}/{m['budget']:,}")
        st.write(f"Complete-question delivery: {m['complete_question'] if r['group_ids'] else 'NOT_APPLICABLE_UNSUPPORTED'} · displaced {m['displaced_parents']} · "
                 f"individually oversized {m['individually_oversized_parents']}")
        st.caption("Direct-witness and parent-only discovery are distinct; complete-parent reconstruction can restore "
                   "a supporting passage absent from a selected detached chunk.")
    else:
        st.info(NOT_MEASURED)
        st.caption("No RRF-30/128K success or failure is inferred from historical M9 measurements.")
    if not r["group_ids"]:
        st.info("UNSUPPORTED CONTROL — no positive-group recall denominator; candidate/evidence presence is not answer support.")
    if r.get("completion") and r["completion"]["status"] == "COMPLETE":
        st.write("Missing group reasons", r["completion"]["m8"]["missing_reasons"])
        historical_ui.provenance(data, [r.get("completion_report_ref")])
    if attempt and attempt.get("preparation_audit"):
        p = attempt["preparation_audit"]
        st.dataframe([{"Preparation source integrity": p["source_integrity"],
            "Included parents": p["M8_counts"]["selected_parents"],
            "Evidence BGE tokens": p["M8_BGE_budget"]["exact_llm_evidence_tokens"],
            "Evidence BGE budget": p["M8_BGE_budget"]["limit"],
            "Prompt": p["template_version"], "Schema": p["response_schema_version"],
            "Generator input tokens": attempt["audit"]["generator_input_tokens"],
            "Model context fit": attempt["audit"]["context_fit"]["fits"]}], hide_index=True)
        st.caption("This is recorded generation-preparation telemetry, not a newly measured approved-group delivery score.")
    if attempt:
        st.caption("Selected generation attempt uses model " + attempt["audit"]["model"] + " / " + attempt["audit"]["prompt_template"])
        historical_ui.provenance(data, [attempt["audit_ref"]])
    elif f and f.get("prompt"):
        p = f["prompt"]
        st.caption(f"Historical preparation: {p['template_version']} / {p['response_schema_version']} · {p['status']}")
        historical_ui.provenance(data, [f["prompt_ref"]])
    else:
        st.caption("Pre-generation preparation: NOT_RUN for the target configuration.")
    st.caption("Current v2.1 request qualification remains unavailable until a separate preflight. "
               "No Q05 or BGE count is reused as another generator request’s token count.")
    st.markdown("#### M9 and historical strategy comparison — exact recorded configurations")
    choices = r["retrieval_measurements"]
    selected = st.selectbox("Historical retrieval measurement", range(len(choices)),
        format_func=lambda i: choices[i]["family"] + " · " + choices[i]["mode"] + " · " + str(choices[i]["top_k"]), key="historical_m7_" + r["question_id"])
    measurement = choices[selected]
    values = measurement["values"]
    if measurement["family"] == "M9_ORIGINAL_29":
        st.caption("Human approval refers to labels; computed retrieval metrics are separate measurements. "
                   "Original M9 direct-positive hits do not implement the later strict joint-AND witness test.")
        if r["reference"]["answerability"] == "UNSUPPORTED":
            st.info("UNSUPPORTED CONTROL — no positive-group recall/MRR denominator. Candidate presence is not answer support.")
            st.write("Candidates returned:", values["candidate_count"])
        else:
            st.dataframe([{"Cohort": r["reference"]["cohort_label"], "K": k,
                "Known-positive equivalence Recall@K": v["equivalence_aware_chunk_recall"],
                "Parent groups": v["parent_groups_retrieved"], "Required": values["required_group_denominator"],
                "Complete parent groups": v["all_required_groups_retrieved"],
                "Historical direct-positive group hits": v["direct_positive_group_hits"],
                "MRR@10": values["reciprocal_rank_at_10"]}
                for k, v in values["at_k"].items()], hide_index=True, width="stretch")
    else:
        st.dataframe([{k: v for k, v in values.items() if k in {"candidate_count", "candidates", "complete_groups",
            "groups_covered", "complete_question", "complete", "missing_groups", "parent_located_groups"}}
            | {"Cohort": r["reference"]["cohort_label"]}], hide_index=True)
    st.caption(measurement["method"])
    historical_ui.provenance(data, [measurement["artifact_ref"]])
    st.warning("Retrieval precision: " + data["precision"])
    st.caption("nDCG: UNAVAILABLE — NOT_MEASURED. Unlabeled candidates remain unknown.")
    st.markdown("#### Historical M8 evidence delivery")
    m8 = r["m8_measurements"]
    if m8:
        selected = st.selectbox("Historical M8 measurement", range(len(m8)),
            format_func=lambda i: f"{m8[i]['family']} · {m8[i]['mode']} Top-{m8[i]['top_k']} · {m8[i]['budget']:,} BGE", key="historical_m8_" + r["question_id"])
        obs, v = m8[selected], m8[selected]["values"]
        unsupported = r["reference"]["answerability"] == "UNSUPPORTED"
        st.dataframe([{"Cohort": r["reference"]["cohort_label"], "Status": obs["status"],
          "Groups delivered": "NOT_APPLICABLE_UNSUPPORTED" if unsupported else v.get("groups_included", v.get("delivered_groups")),
          "Required groups": "NOT_APPLICABLE_UNSUPPORTED" if unsupported else len(r["group_ids"]),
          "Complete question": "NOT_APPLICABLE_UNSUPPORTED" if unsupported else v.get("all_required_groups_included", v.get("complete_question")),
          "Included parents": len(v["included_parent_ids"]) if "included_parent_ids" in v else v.get("included_parents"),
          "Omitted parents": len(v["omitted_parents"]) if isinstance(v.get("omitted_parents"), list) else v.get("omitted_parents"),
          "Included BGE tokens": v.get("included_tokens", v.get("exact_tokens")),
          "Budget BGE": obs["budget"], "Utilization": v["utilization"],
          "Context status": v.get("status", v.get("M8_status"))}], hide_index=True, width="stretch")
        st.caption(obs["method"])
        if "omitted_parents" in v and isinstance(v["omitted_parents"], list):
            from collections import Counter

            st.write("Omission reasons", dict(Counter(p["reason"] for p in v["omitted_parents"])))
        elif "missing_reasons" in v:
            st.write("Missing group reasons", v["missing_reasons"])
        historical_ui.provenance(data, [obs["artifact_ref"]])
    else:
        st.info("UNAVAILABLE — no compatible historical M8 measurement")
    if r["reference"]["cohort_id"] == "C":
        saved = next(x for x in data["remaining_report"] if x["question_id"] == r["question_id"])
        st.caption("Original Remaining was selected by subset membership, not assumed successful retrieval.")
        st.dataframe([saved | {"Cohort": r["reference"]["cohort_label"]}], hide_index=True)


def post(data, r, attempt):
    st.subheader("Post-Generation Validation — Answer Quality")
    st.caption(r["reference"]["cohort_label"])
    if attempt and not attempt['completed'] and attempt.get('validation'):
        st.warning('Contract invalid; available field-level checks remain visible. Independent semantic review is pending.')
        st.json(attempt['validation'])
        return
    if not attempt or not attempt["completed"]:
        st.info("NOT_RUN — no completed answer to validate. This is not an incorrect answer.")
        return
    result = attempt["validation"]
    if result:
        st.write("Deterministic status:", result["overall_status"])
        checks = result.get('checks')
        if checks is None:
            checks = [{'Dimension': key, 'Status': str(result.get(key, 'UNAVAILABLE'))} for key in
                ['structural_validation', 'citation_validity', 'source_integrity', 'semantic_status',
                 'qualification_status', 'material_qualifications', 'conflicts']]
        st.dataframe(checks, hide_index=True, width="stretch")
        with st.expander('Quotation fidelity and claim-level findings'):
            st.json({key: result.get(key, 'UNAVAILABLE') for key in
                ['quotation_fidelity', 'claim_grounding', 'completeness', 'diagnoses', 'review_reasons']})
        st.warning("Qualification applicability: " + result["qualification_status"])
        historical_ui.provenance(data, [result.get("artifact_ref") or attempt["audit_ref"]])
    else:
        st.warning("PENDING_REVIEW — deterministic validation receipt unavailable")
    st.dataframe([{"Metric": name, "Status": "PENDING_REVIEW"} for name in
        ["Claim semantic support", "Factual correctness", "Answer completeness", "Requirement coverage",
         "Abstention appropriateness", "Final independent validation"]], hide_index=True)
    if r["reference"]["answerability"] == "UNSUPPORTED":
        st.caption("Correct abstention and unsupported confident answers require independent judgments. "
                   "The model's declared status does not establish either conclusion.")
    if attempt.get("engineering_review"):
        st.caption(attempt["engineering_review"]["semantic_assessment_method"])
        historical_ui.provenance(data, [attempt["engineering_review_ref"]])
    st.caption("Exact quotes and authorized citations are deterministic checks, not semantic entailment. "
               "No response is rewritten and no new evaluator is introduced.")


def main(root):
    st.set_page_config(page_title="RAG Intelligence Hub", page_icon="📚", layout="wide")
    st.markdown(historical_ui.STYLE, unsafe_allow_html=True)
    if st.sidebar.button("Refresh verified telemetry"):
        st.rerun()
    st.sidebar.caption("Expanded benchmark · read-only artifacts · no API calls")
    try:
        data = load_expanded(root)
    except (ArtifactError, ValueError, KeyError, OSError, TypeError):
        st.error("UNAVAILABLE — expanded benchmark or measurement bindings failed verification.")
        st.stop()
    st.session_state["expanded_data"] = data
    st.session_state["quality_data"] = data  # Preserved explorer wrapper consumes only store/navigation.
    views = Path(root) / "apps/master_dashboard/views"
    pages = [st.Page(views / "coverage_home.py", title="Master Dashboard", icon="📚", default=True),
             st.Page(views / "explorer.py", title="Candidate–Parent Explorer", icon="🔎", url_path="explorer"),
             st.Page(views / "coverage_quality.py", title="End-to-End Quality & Telemetry", icon="📊", url_path="quality")]
    st.session_state["explorer_page"], st.session_state["quality_page"] = pages[1:]
    historical_ui.show_artifact(data)
    st.navigation(pages).run()
    if data["rejected"]:
        st.sidebar.warning(f"{len(data['rejected'])} incompatible or unsealed artifacts excluded")
    st.sidebar.caption(f"{len(data['store'].verified)} bindings verified on refresh")
