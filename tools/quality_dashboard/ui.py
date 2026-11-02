"""Telemetry UI: compact measured facts, explicit uncertainty, artifact drill-down."""
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from .adapter import explorer_html, load_dashboard
from .artifacts import ArtifactError

STYLE = """
<style>
.block-container {max-width:1320px;padding-top:2.5rem}
[data-testid="stMetric"] {background:#f1f5f9;border-radius:10px;padding:12px}
[data-testid="stMetricLabel"] {color:#38526a}
h1,h2,h3 {color:#17324d}
</style>
"""


def provenance(data, refs):
    for ref in dict.fromkeys(r for r in refs if r):
        item = data["references"].get(ref)
        if item:
            st.markdown("[Inspect artifact receipt]"
                        f"(?artifact={quote(ref)})")


def show_artifact(data):
    requested = st.query_params.get("artifact")
    if not requested:
        return
    item = data["references"].get(requested)
    if not item:
        st.warning("UNAVAILABLE — unknown artifact reference. No file was opened.")
        return
    with st.expander("Artifact provenance receipt", expanded=True):
        # Only registered relative path/hash metadata. Never serve arbitrary file bytes.
        st.text(item["artifact"])
        st.code(item["sha256"], language=None)
        st.caption("HASH_VERIFIED · recorded measurement, not a reusable source authorization. "
                   "Publisher payloads, raw provider responses and credentials are not served.")


def summary(data):
    s = data["summary"]
    cols = st.columns(4)
    cols[0].metric("Frozen questions", s["questions"])
    cols[1].metric("Mandatory evidence groups", s["groups"])
    cols[2].metric("Completed generation", f"{s['generated_questions']} / {s['questions']}")
    cols[3].metric("Deterministic checks recorded", f"{s['validated_questions']} / {s['generated_questions']}")


def home(data):
    st.title("RAG Intelligence Hub")
    st.caption("Retrieval, Evidence Integrity, Grounded Generation & Quality Evaluation")
    summary(data)
    st.markdown("### Explore the pipeline")
    left, right = st.columns(2)
    with left:
        st.page_link(st.session_state["explorer_page"], label="Candidate–Parent Explorer", icon="🔎")
        st.write("Detailed investigation of retrieved chunks, rankings, verified parents "
                 "and source relationships. The existing explorer is preserved.")
    with right:
        st.page_link(st.session_state["quality_page"], label="End-to-End Quality & Telemetry", icon="📊")
        st.write("Question-level evaluation across retrieval, evidence assembly, "
                 "grounded generation and answer validation.")
    s = data["summary"]
    st.markdown("### Available evidence")
    st.dataframe([{"Record": "Retrieval strategy comparisons", "Available": s["retrieval_evaluations"]},
                  {"Record": "M8 strategy / budget comparisons", "Available": s["delivery_evaluations"]},
                  {"Record": "Failed provider attempts (preserved)", "Available": s["failed_attempts"]},
                  {"Record": "Independently fully validated answers", "Available": s["fully_validated_answers"]}],
                 hide_index=True, width="stretch")
    st.info("Latest work: offline dashboard and deterministic validation — PENDING_REVIEW. "
            "Semantic answer review remains pending; refresh never runs generation.")
    with st.expander("Overview metric provenance"):
        st.dataframe(data["summary_metrics"], hide_index=True, width="stretch")
        provenance(data, [m["artifact_ref"] for m in data["summary_metrics"]])
    st.caption(f"Current experimental prompt: {data['current_prompt']} · {data['current_response_schema']}. "
               "Historical generation keeps its original prompt identity. Production settings are unchanged.")


def explorer(data):
    st.title("Candidate–Parent Explorer")
    st.caption("Existing sealed HTML/JavaScript explorer · embedded without rewriting it. "
               "Recorded metadata only; source content still requires the accepted verified reader.")
    components.html(explorer_html(data["store"]), height=1100, scrolling=True)
    st.page_link(st.session_state["quality_page"], label="Return to End-to-End Quality & Telemetry")


def overview_rows(data):
    rows = []
    for qid, r in data["records"].items():
        a = r["latest"]
        validation = a["validation"] if a else None
        rows.append({"Question": qid,
                     "M7 direct groups": f"{r['retrieval']['complete_groups']}/{len(r['group_ids'])}",
                     "M7 parent groups": f"{r['retrieval']['parent_located_groups']}/{len(r['group_ids'])}",
                     "M8 delivered": f"{r['m8']['delivered_groups']}/{len(r['group_ids'])}",
                     "Prompt readiness": "PROVIDER_QUALIFIED_HISTORICAL" if a else r["prompt"]["status"],
                     "Generation": a["response"]["status"] if a else "NOT_RUN",
                     "Post-generation": validation["overall_status"] if validation else
                     "PENDING_REVIEW" if a else "NOT_RUN",
                     "Estimated API cost USD": a["usage"].get("total_estimated_cost_usd") if a else None})
    return rows


def quality(data):
    st.title("End-to-End Quality & Telemetry")
    st.caption("Frozen known-positive evaluation · experimental RRF-30 → M8 128K BGE tokens. "
               "M9 is offline evaluation, not a runtime pipeline stage.")
    summary(data)
    s = data["summary"]
    with st.expander("End-to-End Quality Funnel — units and denominators"):
        st.markdown("### End-to-End Quality Funnel")
        st.dataframe([
            {"Layer": "M7 direct witnesses discovered", "Numerator": s["m7_direct_groups"],
             "Denominator": s["groups"], "Unit": "approved mandatory groups"},
            {"Layer": "M7 evidence-bearing parents located", "Numerator": s["m7_parent_groups"],
             "Denominator": s["groups"], "Unit": "approved mandatory groups"},
            {"Layer": "M8 verified evidence delivered", "Numerator": s["m8_groups"],
             "Denominator": s["groups"], "Unit": "approved mandatory groups"},
            {"Layer": "Complete M8 questions", "Numerator": s["m8_complete_questions"],
             "Denominator": s["questions"], "Unit": "benchmark questions"},
            {"Layer": "Generated answers", "Numerator": s["generated_questions"],
             "Denominator": s["questions"], "Unit": "benchmark questions; others NOT_RUN"},
            {"Layer": "Fully independently validated answers", "Numerator": s["fully_validated_answers"],
             "Denominator": s["generated_questions"], "Unit": "generated answers; semantic review pending"}],
            hide_index=True, width="stretch")
        st.caption("These stages use different units and denominators; this is not one common accuracy score.")
        with st.container():
            st.markdown("#### Generation totals — measured successful questions only")
            st.dataframe([{"Input tokens": s["input_tokens"], "Output tokens": s["output_tokens"],
                           "Usage-covered questions": s["measured_usage_questions"],
                           "Mean API latency ms": s["average_generation_latency_ms"],
                           "Known ESTIMATED_API_COST USD": s["known_estimated_api_cost_usd"],
                           "Cost-covered questions": s["cost_measured_questions"],
                           "Failed attempts": s["failed_attempts"]}], hide_index=True)
            st.write("Generated-answer status distribution", s["answer_statuses"])
            st.caption("Measured API usage; local cost calculation is not an invoice. Failed attempts with "
                       "unknown usage are excluded, not charged as zero. Latest completed result per question.")
    with st.expander("All-question journey overview"):
        st.dataframe(overview_rows(data), hide_index=True, width="stretch")
    qid = st.selectbox("Shared question", list(data["records"]), key="quality_question")
    r = data["records"][qid]
    st.text(r["question"])
    st.caption("Question → M7 candidates → M8 verified parents → Pre-generation → "
               "LLM generation → Post-generation validation")
    selected = r["attempts"]
    a = r["latest"]
    if selected:
        labels = {x["experiment"]: x for x in selected}
        default = list(labels).index(a["experiment"]) if a else 0
        choice = st.selectbox("Generation experiment", list(labels), index=default,
                              format_func=lambda x: x.split("/")[-1], key=f"attempt_{qid}")
        a = labels[choice]
        st.caption(f"Selected attempt: {choice.split('/')[-1]} · {a['status']} · "
                   "all three tabs use this question and attempt.")
    tabs = st.tabs(["Retrieval Pipeline Telemetry", "Generation — Output & Telemetry",
                    "Post-Generation Validation"])
    with tabs[0]:
        pipeline(data, r, a)
    with tabs[1]:
        generation(data, r, a)
    with tabs[2]:
        post_generation(data, r, a)
    st.markdown("### Evidence-linked investigation")
    st.page_link(st.session_state["explorer_page"], label="Open Candidate–Parent Explorer")
    st.caption("Use the same stable question ID in the preserved explorer. Full parents remain in the "
               "existing verified Chunk Inspector; they are not copied into this telemetry view.")
    with st.expander("Metric definitions and provenance"):
        st.dataframe(r["metrics"], hide_index=True, width="stretch")
        provenance(data, [m["artifact_ref"] for m in r["metrics"]] + [r["prompt_ref"]])


def pipeline(data, r, attempt):
    st.subheader("Retrieval Pipeline Telemetry — M7 / M8 / M9 / Pre-Generation")
    cfg = r["retrieval_parameters"]
    st.write(f"Selected retrieval: hybrid RRF(k={cfg['rrf_k']}), Top-{cfg['top_k']} · "
             f"native depth {cfg['candidate_depth']} · filters {cfg['filters']}")
    st.dataframe([
        {"Measurement": "Direct-witness discovery", "Groups": r["retrieval"]["complete_groups"],
         "Required": len(r["group_ids"]), "Status": "REUSED_HISTORICAL"},
        {"Measurement": "Parent-location discovery", "Groups": r["retrieval"]["parent_located_groups"],
         "Required": len(r["group_ids"]), "Status": "REUSED_HISTORICAL"},
        {"Measurement": "Verified evidence delivered", "Groups": r["m8"]["delivered_groups"],
         "Required": len(r["group_ids"]), "Status": "REUSED_HISTORICAL"}],
        hide_index=True, width="stretch")
    st.caption("Direct witnesses use approved OR alternatives and joint-AND rules. A parent-only "
               "locator is not a direct witness; full M8 reconstruction may deliver its supporting passage.")
    m = r["m8"]
    st.write(f"Candidates: {m['candidate_count']} · included parents: {m['included_parents']} · "
             f"excluded parents: {m['omitted_parents']} · complete evidence: {m['complete_question']}")
    st.write(f"Evidence tokens: {m['exact_tokens']:,} BGE / {m['budget']:,} · "
             f"budget utilization {m['utilization']:.1%}")
    st.write(f"Parent-location → delivery loss: {m['parent_located_groups'] - m['delivered_groups']} group(s)")
    st.dataframe([{"Group": g["group_id"], "Direct witness": g["direct_witness_discovered"],
                   "Parent located": g["parent_located"], "Delivered": g["included"],
                   "Attribution": g["delivery_attribution"]} for g in m["group_outcomes"]],
                 hide_index=True, width="stretch")
    st.caption(f"Exclusions: {m['individually_oversized_parents']} individually oversized; "
               f"{m['displaced_parents']} displaced by earlier parents. "
               "BGE evidence tokens are not generator tokens.")
    st.markdown("#### Pre-generation — exact historical configuration")
    p = attempt["audit"] if attempt else r["prompt"]
    st.dataframe([{"Prompt": p.get("prompt_template", p.get("template_version")),
                   "Schema": p.get("response_schema", p.get("response_schema_version")),
                   "Source integrity": p["source_integrity"],
                   "Local preparation": p.get("prompt_assembly_status", p.get("status")),
                   "Provider qualification": "REUSED_HISTORICAL" if attempt else "UNAVAILABLE",
                   "Generator input tokens": p.get("generator_input_tokens"),
                   "Context fit": p.get("context_fit", {}).get("fits"),
                   "Output reserve": p.get("context_fit", {}).get("reserved_output_tokens"),
                   "Safety margin": p.get("context_fit", {}).get("safety_margin_tokens")}], hide_index=True)
    st.caption(f"Current default {data['current_prompt']} is separate from these historical runs; "
               "its generator count and model-context fit remain UNAVAILABLE until a new authorized preflight.")
    st.markdown("#### M9 — human-approved offline evaluation baseline")
    st.caption(f"{data['summary']['questions']} frozen questions / approved known-positive labels. Automatically scored measurements "
               "are distinct from human approval and observed M8 delivery. Unlabeled is unknown.")
    comparisons = []
    for strategy, row in data["selection_comparison"].items():
        comparisons.append({"Strategy": strategy, "Direct groups / all groups":
                            f"{row['complete_groups']}/{data['summary']['groups']}",
                            "Complete questions": row["complete_questions"],
                            "Mean candidates": row["average_candidates"]})
    st.dataframe(comparisons, hide_index=True, width="stretch")
    k = r["ranking_metrics"]
    st.dataframe([{"Saved RRF cutoff": n, "Macro group recall for this question": k[f"rrf_Recall{n}"],
                   "MRR@10": k["rrf_MRR10"]} for n in [5, 10, 20]], hide_index=True)
    st.warning("Retrieval precision: " + data["precision"])
    st.caption("nDCG: " + data["ndcg"])
    with st.expander("Historical M8 strategy / budget measurements"):
        st.dataframe(data["budget_comparison"], hide_index=True, width="stretch")
        st.caption("A: RRF-10; B: RRF-30 direct accepted M8 API; C: supplementation Stage 1 "
                   "through a private processing-order adapter, not production-equivalent M8 validation. "
                   "All displayed runs are reused historical measurements; no assembly runs on refresh.")
    scope = data["original_m9"]["scope"]
    with st.expander(f"Original M9 {scope['questions']}-question evaluation — separate scope"):
        st.caption(f"{scope['answerable']} answerable / {scope['unsupported']} unsupported. "
                   f"These historical metrics are not the {data['summary']['questions']}-question "
                   "experiment denominator; R01–R05 were added later.")
        relevant = [x for x in data["original_m9"]["per_question"]
                    if x["question_id"] == r["question_id"]]
        if relevant:
            rows = []
            for case in relevant:
                for cutoff, value in case["retrieval"]["at_k"].items():
                    rows.append({"Mode": case["mode"], "K": cutoff,
                                 "Equivalence-aware Recall@K": value["equivalence_aware_chunk_recall"],
                                 "Parent group coverage": value["parent_group_coverage"],
                                 "MRR@10": case["retrieval"]["reciprocal_rank_at_10"]})
            st.dataframe(rows, hide_index=True)
        else:
            st.info("NOT_RUN in original 29-question M9; evaluated in the frozen extension.")
        provenance(data, [data["original_m9"]["artifact_ref"]])


def generation(data, r, attempt):
    st.subheader("Generation — LLM Output & Telemetry")
    if not attempt:
        st.info("NOT_RUN — no completed generation or failed attempt for this question.")
        return
    if not attempt["completed"]:
        st.error("FAILED — provider attempt; no generated answer. Usage/cost may be UNAVAILABLE.")
        st.write(attempt["audit"]["blocking_reasons"])
        st.caption("Use the sealed execution receipt for the precise provider error category. "
                   "An error mapping alone does not establish transient traffic or a retry policy.")
        st.dataframe([attempt["usage"]], hide_index=True)
        provenance(data, [attempt["audit_ref"]])
        return
    response, usage = attempt["response"], attempt["usage"]
    st.caption(f"{attempt['audit']['model']} · {response['status']} · "
               f"{attempt['audit']['prompt_template']} / {attempt['audit']['response_schema']}")
    st.text(response["answer"])
    claims = len(response["claims"])
    cited = len(attempt["cited_parent_ids"])
    quotes = sum(len(c["supporting_quotes"]) for c in response["claims"])
    st.write(f"Claims: {claims} · distinct cited parents: {cited} · supporting quotations: {quotes}")
    st.markdown("#### Model-reported declarations — not independently verified semantic findings")
    st.dataframe(response["requirement_coverage"], hide_index=True)
    st.write("Missing information", response["missing_information"])
    st.write("Reported conflicts", response["conflicts_detected"])
    st.write("Relevant qualifications", response["relevant_qualifications"])
    if attempt.get("qualification_review"):
        st.warning("Qualification-disclosure assessment: " + attempt["qualification_review"]["status"])
        provenance(data, [attempt["qualification_ref"]])
    st.markdown("#### Operational telemetry — measured API usage")
    columns = ("input_tokens", "cached_input_tokens", "cache_write_tokens", "cache_write_30m_tokens",
               "cache_write_12h_tokens", "output_tokens", "reasoning_tokens", "total_tokens",
               "latency_ms", "total_estimated_cost_usd", "cost_status", "pricing_version", "response_status")
    st.dataframe([{"Metric": key, "Value": str(usage.get(key, "UNAVAILABLE")),
                   "Status": "REUSED_HISTORICAL" if usage.get(key) is not None else "UNAVAILABLE"}
                  for key in columns], hide_index=True, width="stretch")
    st.caption("Input includes cached reads/writes; output includes reasoning tokens. "
               "These categories must not be added twice. ESTIMATED_API_COST is not an invoice.")
    st.markdown("#### Context-engineering indicators")
    supplied = attempt["supplied_parents"]
    st.metric("Cited-Parent Utilization", f"{cited}/{supplied} ({cited / supplied:.1%})" if supplied else "UNAVAILABLE")
    st.caption("Descriptive utilization, not retrieval precision. Uncited parents may still be useful context.")
    st.dataframe([{"Supplied parents": supplied, "Cited parents": cited, "Claims": claims,
                   "Input tokens / completed answer": usage.get("input_tokens"),
                   "Input tokens / model-reported claim": usage["input_tokens"] / claims if claims else None,
                   "Input tokens / independently supported claim": "PENDING_REVIEW",
                   "Output tokens": usage.get("output_tokens"),
                   "Cost / completed answer USD": usage.get("total_estimated_cost_usd")}], hide_index=True)
    st.caption("A token ratio is not evidence that the answer is faithful or complete.")
    provenance(data, [attempt["response_ref"], attempt["audit_ref"]])


def post_generation(data, r, attempt):
    st.subheader("Post-Generation Validation — Answer Quality")
    if not attempt or not attempt["completed"]:
        st.info("NOT_RUN — no completed answer to validate. This is not an answer failure.")
    else:
        v = attempt["validation"]
        if not v:
            st.warning("PENDING_REVIEW — no compatible sealed post-generation receipt yet.")
        else:
            st.write("Overall deterministic status:", v["overall_status"])
            st.dataframe(v["checks"], hide_index=True, width="stretch")
            st.warning("Qualification disclosure: " + v["qualification_status"])
            st.caption("Literal quote matches establish quotation fidelity, not semantic entailment. "
                       "C03's general mandatory metadata does not establish which restrictions must be disclosed.")
            provenance(data, [v["artifact_ref"]])
        st.markdown("#### Independent semantic evaluation")
        st.dataframe([{"Metric": key, "Status": "PENDING_REVIEW"} for key in
                      ["Answer correctness", "Claim faithfulness / semantic support", "Answer completeness",
                       "Requirement coverage", "Unsupported claims", "Material conflict handling",
                       "Partial-answer / abstention appropriateness"]], hide_index=True)
        review = attempt.get("engineering_review")
        if review:
            st.caption("Recorded engineering assessment: " + review["semantic_assessment_method"])
            st.text("Question parts: " + review["both_question_parts_answered"])
            st.caption("This review is distinct from an independent, owner-accepted semantic evaluation.")
            provenance(data, [attempt["engineering_review_ref"]])
    st.markdown("#### Supported cross-layer diagnoses")
    diagnoses = list(r["diagnoses"])
    if attempt and not attempt["completed"]:
        diagnoses.append({"category": "PROVIDER_FAILURE", "basis": "Sealed failed provider attempt"})
    if attempt and attempt["validation"]:
        diagnoses.extend(attempt["validation"].get("diagnoses", []))
    if diagnoses:
        st.dataframe(diagnoses, hide_index=True, width="stretch")
    else:
        st.caption("No additional qualified diagnosis recorded. NOT_RUN does not imply GENERATION_OMISSION.")


def main(root):
    st.set_page_config(page_title="RAG Intelligence Hub", page_icon="📚", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)  # UI-owned constant only.
    if st.sidebar.button("Refresh verified telemetry"):
        st.rerun()
    st.sidebar.caption("Local, read-only artifacts · no API calls · no source payload downloads")
    try:
        data = load_dashboard(root)
    except (ArtifactError, ValueError, KeyError, OSError, TypeError):
        st.error("UNAVAILABLE — required artifact integrity or compatibility check failed. "
                 "No unverified measurements are displayed.")
        st.stop()
    st.session_state["quality_data"] = data
    views = root / "apps/master_dashboard/views"
    pages = [st.Page(views / "home.py", title="Master Dashboard", icon="📚", default=True),
             st.Page(views / "explorer.py", title="Candidate–Parent Explorer", icon="🔎", url_path="explorer"),
             st.Page(views / "quality.py", title="End-to-End Quality & Telemetry", icon="📊", url_path="quality")]
    st.session_state["explorer_page"] = pages[1]
    st.session_state["quality_page"] = pages[2]
    show_artifact(data)
    st.navigation(pages).run()
    if data["rejected"]:
        st.sidebar.warning(f"{len(data['rejected'])} unsupported or unsealed artifact(s) excluded")
    st.sidebar.caption(f"{len(data['store'].verified)} artifact bindings verified this refresh")
    # UI has no generation buttons, SDK imports or live evidence cache.
