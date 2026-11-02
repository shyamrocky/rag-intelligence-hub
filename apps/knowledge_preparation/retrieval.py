"""Read-only question journey, using the existing verified completion adapter."""
from pathlib import Path

import streamlit as st

from apps.knowledge_preparation.retrieval_labels import group_rows, unit_rows
from tools.quality_dashboard.artifacts import ArtifactError
from tools.quality_dashboard.completion_adapter import load_completed
from tools.quality_dashboard.expanded_adapter import COHORT_FILTERS

ROOT = Path(__file__).resolve().parents[2]
UNAVAILABLE = "UNAVAILABLE"


def load():
    # Intentionally no cache: native readers recheck publication hashes on refresh.
    return load_completed(ROOT)


def coverage(record, key):
    target = record.get("target")
    if not target:
        return UNAVAILABLE
    if not record["group_ids"]:
        return "N/A — unsupported control"
    category, field = key
    return f"{target[category][field]}/{len(record['group_ids'])}"


def context_status(record):
    target = record.get("target")
    if not target:
        return UNAVAILABLE
    if not record["group_ids"]:
        return "Unsupported control — not an answerability judgment"
    return "Complete known-positive coverage" if target["m8"]["complete_question"] else "Partial known-positive coverage"


def display_method(method):
    if method == "FROZEN_15_STRICT_OR_JOINT_AND":
        return "Strict OR / joint-AND witness scoring"
    if method == "ORIGINAL_M9_OVERLAP_DIRECT_OR_PARENT_ALTERNATIVES":
        return "Historical overlap-hit scoring (separate from strict-witness scoring)"
    if method == "UNSUPPORTED_CONTROL_NO_POSITIVE_DENOMINATOR":
        return "Unsupported control — no positive-group denominator"
    if method:
        return "UNAVAILABLE — scoring method requires inspection in Technical details"
    return "Historical frozen strict-witness scoring"


def summary_rows(records):
    return [{"Question": r["question_id"], "Cohort": r["reference"]["cohort_label"],
             "Answerability": r["reference"]["answerability"],
             "Direct witnesses": coverage(r, ("retrieval", "complete_groups")),
             "Human-approved evidence groups located": coverage(r, ("retrieval", "parent_located_groups")),
             "Human-approved evidence groups delivered": coverage(r, ("m8", "delivered_groups")),
             "Context status": context_status(r),
             "Scoring method": display_method((r.get("completion") or {}).get("scoring_method"))}
            for r in records]


def receipts(data, record):
    refs = [data.get("reference_ref"), record.get("completion_report_ref")]
    refs += [m["artifact_ref"] for m in record["retrieval_measurements"] + record["m8_measurements"]
             if m["family"] == "BENCHMARK_COMPLETION"]
    refs += [data["store"].reference(name) for name in (
        "data/evals/ranking/dataset-v1/FROZEN_DATASET.json",
        "data/evals/m9/benchmark-v1/PROPOSED_EVIDENCE_LABELS.json") if name in data["store"].verified]
    rows = []
    for ref in dict.fromkeys(refs):
        item = data["store"].references.get(ref)
        if item:
            rows.append({"Artifact": item["artifact"], "SHA-256": item["sha256"], "Verification": item["status"]})
    with st.expander("Technical details & measurement provenance"):
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("Project-relative, verified artifact references only. No source payload or arbitrary file access.")
        if record.get("completion"):
            st.write("Recorded scoring method:", record["completion"].get("scoring_method", UNAVAILABLE))
            st.write("Recorded label provenance:", record["completion"].get("label_provenance", UNAVAILABLE))
            st.write("Recorded observation:", record["completion"].get("compatibility_or_measurement_checked_at_utc", UNAVAILABLE))
            st.code(record["completion"].get("M7_result_sha256", UNAVAILABLE), language=None)
            st.code((record.get("target") or {}).get("m8", {}).get("M8_package_sha256", UNAVAILABLE), language=None)


def render():
    from apps.knowledge_preparation.bot_records import source
    if source('Knowledge Retrieval'):
        return
    from apps.knowledge_preparation.retrieval_explorer import html as explorer_html

    st.title("Knowledge Retrieval")
    st.write("Find relevant evidence in the prepared knowledge.")
    with st.container(border=True):
        st.subheader("Retrieval pipeline")
        st.write("Question → BM25 + BGE search → Combine results → Deduplicate by exact Chunk ID → RRF ranking → Select Top-30 → Reconstruct complete parents → Assemble context")
        st.caption("BGE converts the question into a vector for semantic search; BM25 performs lexical search. Each returns Top-50 results, "
                   "followed by combination, exact Chunk ID deduplication and final Top-30 selection.")
        st.caption("Inspect saved results. No searches, evidence reconstruction or provider calls run when browsing.")
    try:
        data = load()
    except (ArtifactError, OSError, ValueError, KeyError, TypeError):
        st.error("UNAVAILABLE — benchmark or measurement bindings failed verification. No pipeline stage was executed.")
        return
    records = list(data["records"].values())
    with st.expander("Filter questions"):
        left, right = st.columns(2)
        cohort = left.selectbox("Question cohort", list(COHORT_FILTERS), key="kr_cohort")
        answerability = right.selectbox("Benchmark answerability", ["All", "Answerable", "Unsupported"], key="kr_answerability")
        st.caption("Benchmark classifications help navigation; retrieval does not determine answerability from document presence.")
        st.markdown("**Original Difficult:** 10 original questions selected to stress-test retrieval, not necessarily current failures.  \n"
                    "**NLP:** Five realistic user queries (R01–R05).  \n"
                    "**Original Remaining:** The other 16 original answerable questions; not automatically easy.  \n"
                    "**Abstention:** Three controls whose requested answers lack approved corpus support.")
    scoped = [r for r in records
              if (COHORT_FILTERS[cohort] is None or r["reference"]["cohort_id"] == COHORT_FILTERS[cohort])
              and (answerability == "All" or (r["reference"]["answerability"] == "UNSUPPORTED") == (answerability == "Unsupported"))]
    if not scoped:
        st.info("No questions match this scope. No retrieval was run.")
        return
    ids = [r["question_id"] for r in scoped]
    if st.session_state.get("kr_question") not in ids:
        st.session_state["kr_question"] = ids[0]
    qid = st.selectbox("Question", ids, key="kr_question",
                       format_func=lambda q: q + " · " + data["records"][q]["question"])
    r = data["records"][qid]
    st.write(r["question"])
    st.caption(r["reference"]["cohort_label"] + " · Benchmark: " + r["reference"]["answerability"])
    st.caption("Saved configuration: BM25 Top-50 + BGE Top-50 · RRF k=60 · Selected Top-30 · Evidence Reconstruction & Context Assembly budget: **128,000 (128K) BGE tokens**")
    try:
        html, payload, case = explorer_html(data, qid)
    except (ArtifactError, OSError, ValueError, KeyError, TypeError):
        st.error("UNAVAILABLE — selected question's Explorer inputs failed verification. No fallback to another question.")
        return
    question = payload["questions"][0]
    selected_rows = []
    included = set(case["actual_M8_included_parent_ids"])
    omitted = {p["unit_id"]: p["reason"] for p in case["omitted"]}
    for hit in question["rrf"]:
        parent = payload["chunks"][hit["chunk_id"]]["unit_id"]
        selected_rows.append({"RRF rank": hit["rank"], "Document": hit["document_id"], "Chunk ID": hit["chunk_id"],
                              "Evidence Unit ID": parent, "BM25 rank": hit["bm25_rank"], "BGE rank": hit["vector_rank"],
                              "Combined RRF score": hit["rrf_score"],
                              "Evidence Unit delivery": "Included" if parent in included else omitted.get(parent, "UNAVAILABLE")})
    tabs = st.tabs(["Search & Ranking", "Selected Top-30", "Evidence Reconstruction", "Context Assembly"])
    with tabs[0]:
        st.iframe(html, height=1100, alt="Saved search and ranking journey for " + qid)
        st.caption("Explorer display reused from the historical view. All 100 native occurrences remain visible; only the saved Top-30 proceed to Evidence Reconstruction. "
                   "Native candidates outside Top-30 are not assigned invented downstream RRF ranks.")
        st.caption("Retrieval precision: UNAVAILABLE — INSUFFICIENT RELEVANCE LABELS")
    st.caption("To inspect source content, open Knowledge Preparation → Chunks & Lineage. Match the exact Chunk ID within the source/Evidence Unit selectors; "
               "inspect the complete parent Evidence Unit with its context and qualifications. The selectors show full IDs in technical details.")
    st.page_link(st.session_state["kp_pages"]["Chunks & Lineage"], label="Inspect source content in Chunks & Lineage", icon=":material/schema:")
    with tabs[1]:
        st.subheader(f"{qid} — Selected Top-30")
        st.dataframe(selected_rows, hide_index=True, width="stretch")
        st.caption("Native ranks, saved RRF order and Evidence Unit mappings connect the same question to Context Assembly. No reranking.")
    target = r.get("target")
    accounting = case["budget_accounting"]
    chain = (f"**{len(question['rrf'])} chunks → {case['counts']['distinct_parents']} Evidence Units → "
             f"{len(included)} included · {len(omitted)} excluded**")
    tokens = accounting["exact_llm_evidence_tokens"]
    budget = accounting["limit"]
    units = unit_rows(case)
    with tabs[2]:
        st.subheader(f"{qid} — Evidence Reconstruction")
        st.write(chain)
        st.write(f"Evidence size: **{tokens:,} / {budget:,} BGE tokens**")
        st.caption("Evidence Unit ID is the complete parent Evidence Unit used in Knowledge Preparation. Multiple selected chunks can point to the same unit.")
        st.caption("Evidence Units are included whole, never truncated. An exclusion may mean the unit cannot fit within the remaining budget "
                   "or individually exceeds the total budget; the recorded reason below distinguishes them.")
        st.dataframe(units, hide_index=True, width="stretch")
        st.caption("Per-unit BGE counts include the serialized evidence and required context/qualifications. Missing historical counts are unavailable, not estimated. "
                   "Per-unit reservations need not sum to the exact serialized package total because framing is counted separately.")
        with st.expander("Inspect chunk-to-Evidence Unit relationships"):
            st.dataframe([{k: row[k] for k in ("RRF rank", "Document", "Chunk ID", "Evidence Unit ID", "Evidence Unit delivery")}
                          for row in selected_rows], hide_index=True, width="stretch")
    with tabs[3]:
        st.subheader(f"{qid} — Context Assembly")
        st.markdown("#### Evidence delivered to context")
        st.write(chain)
        st.write(f"Evidence size: **{tokens:,} / {budget:,} BGE tokens**")
        if target:
            m = target["m8"]
            st.write(f"Excluded for remaining-budget limits: **{m['displaced_parents']}** · "
                     f"Individually exceeds total budget: **{m['individually_oversized_parents']}**")
        with st.expander("Inspect included and excluded Evidence Units"):
            st.dataframe(units, hide_index=True, width="stretch")
        st.markdown(f"#### Coverage against {qid}’s human-approved evidence labels")
        if r["group_ids"]:
            try:
                groups = group_rows(data, r, case)
            except (ArtifactError, OSError, ValueError, KeyError, TypeError, StopIteration):
                st.warning("UNAVAILABLE — approved evidence-group mappings failed verification.")
            else:
                covered = sum(row["Coverage"] == "Covered" for row in groups)
                required = len(groups)
                if covered == required:
                    st.write(f"**All {required} required human-approved evidence groups covered.**")
                else:
                    st.write(f"**{covered} of {required} required human-approved evidence groups covered.**")
                total = sum(len(row["group_ids"]) for row in records)
                st.caption(f"Each question has its own requirements; {qid} has {required}. The complete benchmark contains {total} human-approved evidence groups.")
                st.dataframe(groups, hide_index=True, width="stretch")
                if covered < required:
                    missing = [row["Human-approved evidence group"] for row in groups if row["Coverage"] != "Covered"]
                    st.warning("Missing approved evidence groups: " + ", ".join(missing))
        else:
            st.info("No positive evidence-group requirements assigned — unsupported benchmark control.")
        st.caption("Coverage confirms that expected evidence reached the context. It does not establish that the generated answer used it correctly. "
                   "Evidence groups are used for Offline Retrieval Evaluation, not to select or repair context.")
        st.caption("BGE evidence tokens are not generator tokens. Pre-generation qualification is separate; these receipts confer no new execution authority.")
    if not r["group_ids"]:
        st.info("Unsupported control: retrieved documents do not establish answerability. No positive-group recall is assigned.")
    with st.expander("Benchmark summary & question journeys"):
        measured = [row for row in scoped if row.get("target")]
        positives = [row for row in measured if row["group_ids"]]
        columns = st.columns(4)
        values = [("Questions in scope", len(scoped)), ("Saved retrieval / context measurements", f"{len(measured)}/{len(scoped)}"),
                  ("All required Evidence Units located", f"{sum(row['target']['retrieval']['complete_parent_question'] for row in positives)}/{len(positives)}" if positives else "N/A"),
                  ("All required human-approved evidence groups delivered", f"{sum(row['target']['m8']['complete_question'] for row in positives)}/{len(positives)}" if positives else "N/A")]
        for col, (label, value) in zip(columns, values):
            col.metric(label, value)
        st.dataframe(summary_rows(scoped), hide_index=True, width="stretch")
        st.caption("Known-positive coverage, not precision or answer quality. Scoring methods remain separate; unsupported controls have no positive-group denominator.")
    receipts(data, r)
    if data["rejected"]:
        st.warning(f"{len(data['rejected'])} incompatible or unsealed artifact records excluded by the native reader.")
