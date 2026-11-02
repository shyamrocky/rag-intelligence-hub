"""Learning journey over the same sealed readers used by canonical 8514. No evaluator."""
from pathlib import Path

import streamlit as st

from tools.quality_dashboard.artifacts import ArtifactError
from tools.quality_dashboard.completion_adapter import load_completed

ROOT = Path(__file__).resolve().parents[2]
# Existing sealed studies supplement (not replace) the canonical reader's records.
EXTRAS = {
    "signals": ("data/evals/evidence-signals/experiment-v1/EXPERIMENT_MANIFEST.json", "ac318cfd67cf139e47fbe5a4f03f379c7aaa9ddce05e1afe932251a732ecc80a"),
    "atomic": ("data/evals/evidence-selection/experiment-v1/EXPERIMENT_MANIFEST.json", "621b526d270d2a2bbf0edeff4317941efc4f655f7c50d2c18b30da6b8fc0db83"),
    "intersection": ("data/evals/intersection-selection/experiment-v1/EXPERIMENT_MANIFEST.json", "e03351fa40653a3256cc7b92ee69d141a6a5994fffb16c56d15ff8b69f2eb14f"),
}
NAMES = {"rrf_top10": "RRF Top-10", "rrf_top20": "RRF Top-20", "rrf_top30": "RRF Top-30",
         "intersection_stage1": "Intersection-first Stage 1", "intersection_stage2": "Intersection-first Stage 2",
         "stage1": "RRF supplementation Stage 1", "stage2": "RRF supplementation Stage 2", "full_union": "Full native union"}
ARMS = {"A": "RRF Top-10", "B": "RRF Top-30", "C": "Supplementation Stage 1 (experimental processing order)"}


def load():
    return load_completed(ROOT)


def provenance(data, names):
    with st.expander("Measurements & provenance"):
        rows = []
        for name in dict.fromkeys(names):
            if name in data["store"].verified:
                rows.append({"Artifact": name, "SHA-256": data["store"].verified[name], "Status": "HASH_VERIFIED"})
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("Verified project-relative references. No arbitrary file access or protected source payload is served.")


def chapter(number, title, scope, question, tested, finding, learning):
    st.subheader(f"{number:02d} · {title}")
    st.caption(scope)
    st.markdown(f"**What we asked:** {question}")
    st.markdown(f"**What we tested:** {tested}")
    st.markdown(f"**What we observed:** {finding}")
    st.markdown(f"**What we learned / decided:** {learning}")


def ranker_rows(data):
    store = data["store"]
    metrics = store.json("data/evals/ranking/phase3-experiment-v1/RETRIEVAL_METRICS.json")
    perf = store.json("data/evals/ranking/phase3-experiment-v1/PERFORMANCE_SUMMARY.json")
    rows = []
    for cohort, methods in metrics["summaries"].items():
        for method, row in methods.items():
            rows.append({"Cohort": cohort, "Ranker": "RRF(k=60)" if method == "rrf" else "MiniLM + approved windows",
                         "Questions": row["question_denominator"], "Human-approved evidence groups": row["required_group_denominator"],
                         "Recall@5 (macro)": row["at_k"]["5"]["Recall_macro"], "Recall@10 (macro)": row["at_k"]["10"]["Recall_macro"],
                         "Recall@20 (macro)": row["at_k"]["20"]["Recall_macro"], "MRR@10": row["MRR_at_10"],
                         "Complete questions @10": row["at_k"]["10"]["complete_questions"]})
    return rows, perf["scenarios"]["full"]


def selection_rows(data):
    scope = data["frozen_data"]["summary"]
    return [{"Strategy": NAMES[name], "Question denominator": scope["questions"], "Required group denominator": scope["groups"],
             "Direct witness groups": row["complete_groups"], "Complete questions": row["complete_questions"],
             "Candidate memberships": row["total_candidates"], "Average candidates per question": row["average_candidates"]}
            for name, row in data["frozen_data"]["selection_comparison"].items() if name in NAMES]


def budget_rows(data):
    return [{"Strategy": ARMS[row["arm"]], "Evidence budget (BGE tokens)": row["budget"],
             "Delivered groups": row["groups_delivered"], "Required group denominator": row["group_denominator"],
             "Complete questions": row["complete_questions"], "Question denominator": row["question_denominator"],
             "Mean evidence BGE tokens": row["mean_tokens"], "Measurement": row["measurement"]}
            for row in data["frozen_data"]["budget_comparison"]]


def drilldown(data):
    from tools.quality_dashboard.expanded_adapter import COHORT_FILTERS

    st.subheader("Follow one question across experiments")
    cohort = st.selectbox("Evaluation cohort", list(COHORT_FILTERS), key="oe_cohort")
    ids = [q for q, r in data["records"].items() if COHORT_FILTERS[cohort] is None or r["reference"]["cohort_id"] == COHORT_FILTERS[cohort]]
    if st.session_state.get("oe_question") not in ids:
        st.session_state["oe_question"] = ids[0]
    qid = st.selectbox("Evaluation question", ids, key="oe_question")
    record = data["records"][qid]
    st.write(record["question"])
    st.caption(record["reference"]["cohort_label"])
    st.write("Human-approved evidence groups:", ", ".join(record["group_ids"]) or "None assigned — unsupported control")
    tables = []
    for measurement in record["retrieval_measurements"]:
        values = measurement["values"]
        tables.append({"Family": measurement["family"], "Configuration": str(measurement["mode"]) + " · Top-" + str(measurement["top_k"]),
                       "Measurement": measurement["status"], "Method": measurement["method"], "Receipt": measurement["artifact_ref"]})
        # Keep differing original overlap/rank metrics inspectable through the canonical projection.
        with st.expander(f"Retrieval measurement · {measurement['family']} · {measurement['mode']} · Top-{measurement['top_k']}"):
            st.json({k: v for k, v in values.items() if k not in {"candidates", "parents"}})
    for measurement in record["m8_measurements"]:
        v = measurement["values"]
        unsupported = not record["group_ids"]
        tables.append({"Family": measurement["family"], "Configuration": f"{measurement['mode']} · Top-{measurement['top_k']} · {measurement['budget']:,} BGE",
                       "Measurement": measurement["status"], "Method": measurement["method"], "Receipt": measurement["artifact_ref"]})
        with st.expander(f"Evidence delivery · {measurement['family']} · {measurement['mode']} · {measurement['budget']:,} BGE"):
            st.write("Delivered human-approved evidence groups:", "N/A — unsupported control" if unsupported else v.get("groups_included", v.get("delivered_groups", "UNAVAILABLE")))
            st.write("Required groups:", "N/A" if unsupported else len(record["group_ids"]))
            st.write("Complete-question delivery:", "N/A" if unsupported else v.get("all_required_groups_included", v.get("complete_question", "UNAVAILABLE")))
            st.write("Evidence BGE tokens:", v.get("included_tokens", v.get("exact_tokens", "UNAVAILABLE")))
            st.write("Observed context status:", v.get("status", v.get("M8_status", "UNAVAILABLE")))
    st.dataframe(tables, hide_index=True, width="stretch")
    if record.get("completion"):
        missing = record["completion"].get("m8", {}).get("missing_reasons", {})
        if missing:
            st.warning("Recorded delivery gaps remain unresolved")
            st.write(missing)
    st.caption("UNAVAILABLE — INSUFFICIENT RELEVANCE LABELS for retrieval precision. nDCG: NOT_MEASURED. Unlabeled evidence remains unknown.")
    refs = [data["store"].references[m["artifact_ref"]]["artifact"] for m in record["retrieval_measurements"] + record["m8_measurements"]]
    provenance(data, refs)


def render():
    st.title("Offline Retrieval Evaluation")
    st.write("Experiments → findings → decisions. How we learned to find and deliver evidence.")
    st.caption("Our reusable offline retrieval-evaluation framework · saved measurements only · not a runtime retrieval stage")
    try:
        data = load()
    except (ArtifactError, OSError, ValueError, KeyError, TypeError):
        st.error("UNAVAILABLE — evaluation benchmark or measurement bindings failed verification.")
        return
    store = data["store"]
    extra = {}
    for key, (name, fingerprint) in EXTRAS.items():
        try:
            extra[key] = store.manifest(name, expected=fingerprint)
        except (ArtifactError, OSError, ValueError, KeyError, TypeError):
            extra[key] = None
    if any(value is None for value in extra.values()):
        st.error("UNAVAILABLE — a historical study failed its pinned manifest verification. No results are substituted or recomputed.")
        return
    try:
        store.bind("docs/adr/D051-rrf-ranking-decision-v1.md", "68db87109f16b72931f0ce4d58a2d039c81f6957823d83432e6921aa0764cb50")
    except (ArtifactError, OSError, ValueError):
        st.error("UNAVAILABLE — the accepted ranking decision failed verification.")
        return
    frozen = data["frozen_data"]
    s = data["summary"]
    with st.container(border=True):
        st.subheader("TL;DR — what, why, how and key learnings")
        st.markdown("**What:** Check whether search finds the evidence a question needs and includes it in the context sent to the LLM.")
        st.markdown("**Why:** Finding relevant-looking results does not guarantee that the required evidence reaches the LLM.")
        st.markdown("**How:** Test different search methods and evidence budgets against questions with human-approved supporting evidence.")
        st.markdown("**What we learned:** Combining BM25 keyword search and semantic vector search using RRF (Reciprocal Rank Fusion) offered the preferred "
                    "balance of evidence coverage, speed and simplicity for this local project. Keeping the Top-30 results and allowing up to 128,000 (128K) "
                    "BGE tokens delivered the most complete evidence in our focused budget study. Some evidence gaps remain.")
        st.markdown("- **k=60 in RRF** is the constant in the scoring formula: `1 / (60 + search rank)`. It does **not** mean Top-60.\n"
                    "- **Top-30** means keeping the 30 highest-ranked combined results.")
        st.caption("Human-approved labels are ground truth; configuration choice is not universal optimality. This page does not change production defaults.")
    columns = st.columns(4)
    for col, (label, value) in zip(columns, [("Expanded benchmark questions", s["questions"]), ("Answerable / unsupported", f"{s['answerable']} / {s['unsupported']}"),
        ("Human-approved evidence groups", s["mandatory_groups"]), ("Focused frozen subset", frozen["summary"]["questions"])]):
        with col.container(border=True, height="stretch"):
            st.metric(label, value)
            if label == "Focused frozen subset":
                st.caption(f"questions · {frozen['summary']['groups']} human-approved evidence groups")
    st.info("Finding evidence ≠ delivering evidence ≠ producing a grounded answer.")
    st.subheader("Our learning journey")
    st.caption("Historical baseline → focused experiments → broader validation. Same-day October 27 studies are grouped by the question they answered, "
               "not claimed to have a precise execution order. Each card retains its own scope; the final 34-question scope is not retroactively applied.")
    with st.container(border=True):
        original = frozen["original_m9"]
        first = next(iter(original["summary"].values()))
        st.subheader("01 · Establish how we would test retrieval")
        st.caption(f"Original benchmark: {first['answerable_denominator']} answerable questions and "
                   f"{first['unsupported_denominator']} questions designed to test handling of insufficient evidence.")
        st.markdown("**What we asked:** Does the system find the evidence needed for each question—and does that evidence "
                    "make it into the context supplied to the LLM?")
        st.markdown("**What we tested:** BM25 keyword search, vector semantic search, and their combination using RRF "
                    "**(hybrid)**. We also tested different evidence budgets.")
        st.markdown("**What we measured:** Two separate outcomes: whether the required evidence was found, "
                    "and whether it was included in the final context.")
        st.markdown("**What we learned:** Finding evidence does not guarantee that it reaches the LLM. "
                    "We therefore track search coverage and context delivery separately.")
        st.markdown("**Evaluation rule:** Human-approved labels identify known supporting evidence. Other results "
                    "remain unreviewed; we do not automatically count them as irrelevant.")
        with st.expander("Historical baseline measurements"):
            st.markdown("**How we compared the search methods**")
            st.markdown(f"We tested three search methods using **{first['answerable_denominator'] + first['unsupported_denominator']} questions**: "
                        f"**{first['answerable_denominator']} answerable questions** requiring "
                        f"**{first['required_group_denominator']} human-approved evidence groups**, plus "
                        f"**{first['unsupported_denominator']} questions designed to test handling of insufficient evidence**.")
            st.markdown("Each method kept its **10 highest-ranked results**:\n\n"
                        "1. **BM25:** retrieved up to 50 keyword-search candidates → kept Top-10.\n"
                        "2. **BGE Vector Search:** retrieved up to 50 semantic-search candidates → kept Top-10.\n"
                        "3. **Hybrid (BM25 + BGE Vector Search) + RRF:** combined both Top-50 lists using RRF → kept final Top-10.")
            method_labels = {"bm25": "BM25", "vector": "BGE Vector Search",
                             "hybrid": "Hybrid (BM25 + BGE Vector Search) + RRF"}
            st.dataframe([{
                "Search method": method_labels[mode],
                "Answerable questions": original["summary"][mode]["answerable_denominator"],
                "Insufficient-evidence test questions": original["summary"][mode]["unsupported_denominator"],
                "Required evidence groups": original["summary"][mode]["required_group_denominator"],
                "Known-evidence recall in Top-10": f"{original['summary'][mode]['retrieval']['10']['equivalence_aware_Recall_macro']:.1%}",
                "First supporting result ranking score (MRR)": f"{original['summary'][mode]['MRR_at_10']:.3f}",
            } for mode in method_labels], hide_index=True, width="stretch")
            st.markdown("**Reading the results:** Higher recall means more known supporting evidence was found, "
                        f"averaged across the {first['answerable_denominator']} answerable questions. Higher MRR means the first supporting result appeared earlier.")
            st.caption("Historical recall uses the original overlap scoring method; it is not simply the percentage of all required groups found.")
            st.markdown("**Precision:** Not measured because retrieved results were not exhaustively labeled relevant or irrelevant; "
                        "unreviewed results remain unknown. These retrieval scores do not establish answer correctness.")
        provenance(data, ["data/evals/m9/runs/m9-v3/RESULTS.json"])
    with st.container(border=True):
        union = frozen["selection_comparison"]["full_union"]
        st.subheader("02 · Agree on the evidence and compare methods fairly")
        st.caption(f"Focused benchmark: {frozen['summary']['questions']} questions and "
                   f"{frozen['summary']['groups']} human-approved evidence groups.")
        st.markdown("**What we asked:** Can we compare ranking methods using the same questions, search results "
                    "and approved evidence requirements?")
        st.markdown("**What we prepared:** We selected 10 difficult questions and 5 realistic user questions. "
                    "We identified supporting evidence, reviewed and corrected the proposed labels, "
                    "then froze them for consistent testing.")
        st.markdown("**How we kept comparisons fair:** For each question, we combined BM25 Top-50 and vector Top-50 "
                    "results, counting repeated Chunk IDs only once. Each ranking method received the same combined candidates.")
        st.markdown(f"**What we found:** Across the {frozen['summary']['questions']} questions, these pools contained "
                    f"{union['distinct_global_chunk_ids']:,} unique chunks. Some chunks appeared for multiple questions, "
                    f"producing {union['total_candidates']:,} question–chunk connections. Supporting evidence for all "
                    f"{union['complete_groups']} required groups existed somewhere in these pools.")
        st.markdown("**What we learned:** Finding the evidence in the starting pool does not guarantee it survives "
                    "into the final Top-10 or Top-30. We must measure what each ranking method keeps.")
        with st.expander("Technical details — evidence requirements"):
            st.markdown("**OR alternatives:** Either approved evidence alternative is sufficient.\n\n"
                        "**Joint-AND requirements:** Several pieces of evidence must be present together; "
                        "finding only one is insufficient.")
            st.caption("These are existing human-approved requirements, not new labels or automatically inferred relevance judgments.")
        provenance(data, ["data/evals/ranking/dataset-v1/FREEZE_MANIFEST.json", "data/evals/ranking/phase2-v1/PHASE2_MANIFEST.json"])
    with st.container(border=True):
        rows, timings = ranker_rows(data)
        overall = {r["Ranker"]: r for r in rows if r["Cohort"] == "all_fifteen"}
        st.subheader("03 · Test whether a model-based reranker improves evidence selection")
        st.caption(f"Same {frozen['summary']['questions']} questions and search candidates · Owner-accepted decision D051")
        st.markdown("**What we asked:** Would a model that reads the question and candidate text select better evidence than RRF?")
        st.markdown("**What we tested:**\n\n"
                    "- **RRF:** Combined BM25 and BGE search rankings using a simple formula.\n"
                    "- **MiniLM neural reranker:** Read the question alongside candidate text and scored how well they matched.")
        st.markdown("Some candidate texts were too long for MiniLM to read in one pass. The experiment divided them "
                    "into smaller, overlapping text windows that fit the model’s input limit, scored those windows, "
                    "and used each candidate’s highest window score to rank it. This temporary handling did not "
                    "change our saved retrieval chunks or complete parent Evidence Units.")
        st.markdown("Both methods received the same combined BM25 + BGE search candidates. "
                    "RRF ranked them using their search positions; MiniLM ranked them by reading the question "
                    "and candidate text. These were alternative ranking methods—not RRF followed by MiniLM.")
        st.markdown(f"**What we found:** Within the final Top-10 results, **RRF retained all required evidence for "
                    f"{overall['RRF(k=60)']['Complete questions @10']} of {frozen['summary']['questions']} questions; MiniLM did so for "
                    f"{overall['MiniLM + approved windows']['Complete questions @10']} of {frozen['summary']['questions']}**. "
                    "MiniLM improved this measure, but its gains were not consistent across question categories "
                    "and selection sizes, and it required substantially more CPU time.")
        st.markdown("**What we decided:** Keep RRF for this local POC because it offered the preferred balance of "
                    "evidence coverage, speed and simplicity. Preserve MiniLM as an evaluated alternative for future investigation.")
        st.markdown("**Important distinction:** MiniLM was an additional ranking step after search—not a replacement "
                    "for BGE embeddings. This experiment measured evidence selection, not generated-answer correctness.")
        with st.expander("Ranker quality and local performance"):
            st.dataframe([{**row, "Complete questions @10": str(row["Complete questions @10"])}
                          for row in rows], hide_index=True, width="stretch")
            st.caption("Complete questions @10: Number of questions whose top 10 ranked results contain all required "
                       "human-approved evidence groups. For example, 8 of 15 means eight questions had complete "
                       "required evidence in the Top-10. This measures evidence discovery, not answer correctness or context delivery.")
            st.markdown("**Local reranking latency**")
            st.dataframe([{"Ranker": "MiniLM (cross_encoder)" if method == "cross_encoder" else "RRF", "Warm median reranking ms": row["p50_seconds"] * 1000, "Warm p95 reranking ms": row["p95_seconds"] * 1000,
                           "Timed samples": row["samples"]} for method, row in timings.items()], hide_index=True, width="stretch")
            st.markdown(f"- **Warm median:** Typical reranking time after the model was loaded—MiniLM about "
                        f"**{timings['cross_encoder']['p50_seconds']:.2f} seconds**, RRF about "
                        f"**{timings['rrf']['p50_seconds'] * 1000:.2f} milliseconds**.\n"
                        "- **Warm p95:** 95% of measured runs finished within this time.\n"
                        f"- **Timed samples:** **{timings['cross_encoder']['samples']} MiniLM measurements** and "
                        f"**{timings['rrf']['samples']} RRF measurements**.")
            st.caption("These timings exclude search, model loading, source validation, evidence reconstruction and generation. "
                       "MiniLM ran locally on CPU; these are not paid API charges. Tiny RRF timers are noisy. "
                       "Macro recall differs from micro group coverage.")
        provenance(data, ["data/evals/ranking/phase3-experiment-v1/EXPERIMENT_MANIFEST.json", "data/evals/ranking/phase3-experiment-v1/RETRIEVAL_METRICS.json", "data/evals/ranking/phase3-experiment-v1/PERFORMANCE_SUMMARY.json", "docs/adr/D051-rrf-ranking-decision-v1.md"])
    with st.container(border=True):
        st.subheader("04 · Understand how keyword and semantic search complement each other")
        st.caption("Focused benchmark · Diagnostic study; no new score threshold adopted")
        st.markdown("**What we asked:** If BM25 and BGE find the same chunk, is it more useful? "
                    "And can their scores tell us which evidence to keep?")
        st.markdown("**What we examined:**\n\n"
                    "- **Search agreement:** Did both searches find the chunk, or only one?\n"
                    "- **Search scores:** Could BM25 scores or vector distances reliably identify useful evidence?\n"
                    "- **Evidence relationships:** Did the chunk contain the required evidence itself, "
                    "or lead us to a complete parent Evidence Unit containing it?")
        st.markdown("**What we learned:**\n\n"
                    "1. **Both searches agreeing is a useful signal, not proof of relevance.**\n"
                    "2. **Important evidence sometimes appeared in only one search.** Requiring agreement could discard evidence we needed.\n"
                    "3. **BM25 scores and vector distances use different scales.** We cannot directly compare their numbers "
                    "or invent a single cutoff for good evidence.")
        st.markdown("**What we decided:** Preserve discoveries from either search. We did not adopt an agreement "
                    "requirement or a new score threshold. This study helped explain why the searches complement "
                    "each other; it did not establish retrieval precision.")
        st.caption("Union means results found by either search; intersection means results found by both. "
                   "See card 06 → Saved selection comparisons for the existing union and intersection-first measurements.")
        if extra["signals"] is None:
            st.warning("UNAVAILABLE — source-signal diagnostic bindings could not be verified; this chapter is historical context only.")
        provenance(data, [EXTRAS["signals"][0]])
    with st.container(border=True):
        chapter(5, "Test whether more search results help when evidence space is limited",
                "Focused benchmark · Four candidate selections · 4K–32K BGE evidence-token budgets",
                "Does keeping more search results help more required evidence reach the LLM when space is limited?",
                "RRF Top-10, Top-20, Top-50 and the full combined search pool, using evidence budgets from 4K to 32K BGE tokens. "
                "Search finds small chunks, but context assembly includes complete parent Evidence Units with required context, citations and qualifications.",
                "At 32K, the full combined pool did not improve the measured outcome over Top-10. "
                "More candidates still had to compete for the same limited evidence space.",
                "Finding more evidence is different from delivering it. A complete Evidence Unit may exceed the entire budget, "
                "or fit individually but not fit after earlier units have used some of the budget. Units are kept whole, not truncated.")
        st.info("32K was the largest budget tested in this experiment—not a finding that 32K was optimal. "
                "The intent was to test whether more candidates alone solved evidence delivery under constrained budgets. "
                "Card 07 covers the broader budget study up to 128K, which supported selecting RRF Top-30 with a 128K BGE-token evidence budget.")
        if extra["atomic"]:
            comparison = store.json("data/evals/evidence-selection/experiment-v1/COMPARISON.json")["aggregate"]["all_15"]
            with st.expander("Four-arm small-budget measurements"):
                st.markdown(f"**Evidence delivery across {frozen['summary']['questions']} focused benchmark questions**")
                arm_labels = {"A": "RRF Top-10", "B": "RRF Top-20", "C": "RRF Top-50",
                              "D": "Full combined pool — parent-aware selection"}
                st.caption("Historical experiment labels: A = RRF Top-10; B = RRF Top-20; C = RRF Top-50; "
                           "D = full combined pool with parent-aware selection. These are test configurations, not question cohorts.")
                st.dataframe([{"Candidate selection": arm_labels[name.split("-")[0]],
                               "Evidence budget (BGE tokens)": int(name.split("-")[1]),
                               "Delivered groups": r["groups_included"], "Required groups": r["group_denominator"],
                               "Complete questions": r["complete_questions"]} for name, r in sorted(
                                   comparison.items(), key=lambda item: (int(item[0].split("-")[1]), item[0].split("-")[0]))],
                             hide_index=True, width="stretch")
                st.markdown("**How to read this table:** It shows how much required evidence reached the assembled context "
                            "at each budget. “Complete questions” means questions receiving **all required evidence—not answers generated**. "
                            f"For example, 1 means **1 of {frozen['summary']['questions']} questions** had complete evidence coverage.")
                st.markdown("**Full combined pool (D):** Considered all combined BM25 + BGE candidates, rather than stopping "
                            "at Top-10, Top-20 or Top-50. It counted each parent Evidence Unit once, followed its best chunk’s rank, "
                            "and included whole units that fit the budget. All four methods used complete parents.")
                top10_at32 = comparison["A-32000"]
                st.markdown("**Key finding:** More candidates sometimes helped at smaller budgets. At **32K, all four methods "
                            f"delivered {top10_at32['groups_included']} of {top10_at32['group_denominator']} evidence groups and complete "
                            f"evidence for {top10_at32['complete_questions']} of {top10_at32['question_count']} questions**. "
                            "Considering the full pool did not establish a better default.")
                st.markdown("**No LLM answers were generated.** Missing required evidence indicates a delivery gap, "
                            "not proof that a useful or partial answer is impossible.")
        else:
            st.warning("UNAVAILABLE — small-budget study failed verification.")
        provenance(data, [EXTRAS["atomic"][0], "data/evals/evidence-selection/experiment-v1/COMPARISON.json"])
    with st.container(border=True):
        selection = frozen["selection_comparison"]
        st.subheader("06 · Test two ways to retain more supporting evidence")
        st.caption(f"Same {frozen['summary']['questions']} questions and {frozen['summary']['groups']} human-approved evidence groups.")
        st.markdown("**What:** We tested two ways to select candidates from the saved BM25 and BGE results.")
        st.markdown("**Why:** A short ranked list can leave out required evidence. We wanted to retain more of that "
                    "evidence without keeping the entire combined pool.")
        st.markdown("**RRF selection-depth comparison:** RRF Top-30 retained "
                    f"**{selection['rrf_top30']['complete_groups']} of {frozen['summary']['groups']} required evidence groups**, "
                    f"versus **{selection['rrf_top10']['complete_groups']} at Top-10** and "
                    f"**{selection['rrf_top20']['complete_groups']} at Top-20**. This supported testing Top-30 further. "
                    "These counts measure evidence present in the selected chunks, not delivery within a context budget. "
                    "Card 07 tests actual delivery and supports the combined RRF Top-30 + 128K configuration.")
        st.markdown("**How — Experiment 1: Common results plus unique discoveries**")
        st.markdown("Keep all chunks found by **both searches**, then add the highest-ranked chunks found only by BM25 or only by BGE.")
        st.markdown(f"- Adding **10 from each search’s unique results** retained "
                    f"**{selection['intersection_stage1']['complete_groups']} of {frozen['summary']['groups']} evidence groups**.\n"
                    f"- Expanding to **20 from each** retained **all {selection['intersection_stage2']['complete_groups']} groups**.")
        st.markdown("**RRF was not used to build these selections.**")
        st.markdown("**How — Experiment 2: Supplement an RRF selection**")
        st.markdown("Start with the saved **RRF Top-10**, then add up to **10 additional BM25 candidates and "
                    "10 additional BGE candidates** outside that selection, removing duplicates. This retained "
                    f"**{selection['stage1']['complete_groups']} of {frozen['summary']['groups']} groups**. "
                    "We also tested a larger version starting with RRF Top-20.")
        st.markdown("**What we learned:** Important evidence can come from either search alone. Both approaches "
                    "preserved more required evidence than RRF Top-10, but also kept more candidates—so these were not equal-size comparisons.")
        st.markdown("**What we decided:** Keep these as experimental alternatives. Better candidate coverage alone "
                    "does not establish that complete evidence will fit the context budget or improve answers. "
                    "Neither approach replaced the accepted retrieval policy.")
        with st.expander("Saved selection comparisons"):
            st.markdown(f"**Candidate selection across {frozen['summary']['questions']} focused benchmark questions**")
            method_labels = {
                "Full native union": "All combined BM25 + BGE candidates",
                "Intersection-first Stage 1": "Common chunks + 10 unique results per search",
                "Intersection-first Stage 2": "Common chunks + 20 unique results per search",
                "RRF supplementation Stage 1": "RRF Top-10 + additional results from each search",
                "RRF supplementation Stage 2": "RRF Top-20 + additional results from each search",
            }
            column_labels = {
                "Strategy": "Candidate selection method",
                "Required group denominator": "Required evidence groups",
                "Direct witness groups": "Evidence groups covered by selected chunks",
                "Complete questions": "Questions with all required evidence",
                "Candidate memberships": "Total question–chunk connections",
                "Average candidates per question": "Average chunks selected per question",
            }
            st.dataframe([{column_labels[key]: method_labels.get(value, value) if key == "Strategy" else value
                           for key, value in row.items() if key != "Question denominator"}
                          for row in selection_rows(data)], hide_index=True, width="stretch")
            example = selection["intersection_stage1"]
            st.markdown("**Example:** “Common chunks + 10 unique results per search” selected about "
                        f"**{example['average_candidates']:.0f} chunks per question**. Those selections covered "
                        f"**{example['complete_groups']} of {frozen['summary']['groups']} required evidence groups**, giving "
                        f"**{example['complete_questions']} of {frozen['summary']['questions']} questions** all their required evidence. "
                        "This measures evidence retained in selected chunks—not context delivery or answer correctness.")
            with st.expander("Technical details — original experiment names"):
                st.dataframe([{"Display name": label, "Original experiment name": original_name}
                              for original_name, label in method_labels.items()], hide_index=True, width="stretch")
                st.caption("Intersection-first Stage 1 and RRF supplementation Stage 1 are different policies. "
                           "Supplementation adds up to 10 candidates per search outside RRF Top-10, or up to 20 outside "
                           "RRF Top-20, then removes duplicates without backfilling.")
        if extra["intersection"] is None:
            st.warning("UNAVAILABLE — intersection study receipt unavailable; canonical comparison remains separately verified.")
        provenance(data, [EXTRAS["intersection"][0], "data/evals/rrf-supplementation/experiment-v1/EXPERIMENT_MANIFEST.json"])
    with st.container(border=True):
        budgets = budget_rows(data)
        chosen = next(r for r in budgets if r["Strategy"] == "RRF Top-30" and r["Evidence budget (BGE tokens)"] == 128000)
        st.subheader("07 · Test how much evidence fits into context")
        st.caption(f"{frozen['summary']['questions']} focused benchmark questions · "
                   f"{frozen['summary']['groups']} required evidence groups · Eight evidence budgets")
        st.markdown("**What we asked:** Which candidate selection and evidence budget deliver the most complete supporting evidence?")
        st.markdown("**What we tested:** RRF Top-10, RRF Top-30, and RRF Top-10 supplemented with additional BM25/BGE "
                    "candidates. Each was tested across eight budgets from **4K to 128K BGE tokens**.")
        st.markdown("**How context was assembled:** Selected chunks led to complete parent Evidence Units. Units were "
                    "included whole, together with required context, citations and qualifications, when they fit the "
                    "evidence budget. They were never truncated.")
        st.markdown(f"**What we found:** **RRF Top-30 + 128K delivered {chosen['Delivered groups']} of "
                    f"{chosen['Required group denominator']} required evidence groups**, giving "
                    f"**{chosen['Complete questions']} of {chosen['Question denominator']} questions all their required evidence**—"
                    "the highest complete-question coverage in this study.")
        st.markdown("**What we decided:** Carry **RRF Top-30 + 128K** forward as the selected experimental configuration. "
                    "This measured evidence delivery, not generated-answer correctness.")
        st.markdown("**Remaining limitation:** More budget cannot recover evidence missing from the selected candidates.")
        st.info("How this connects to context assembly: The 128K BGE-token budget covers only the evidence package—"
                "complete parent Evidence Units together with their required context, citations and qualifications.")
        st.markdown("**Next step — Pre-Generation:** Combine that package with prompt instructions, the question and "
                    "response-schema requirements. Measure the complete request using the generator’s tokenizer and "
                    "check the model’s context limit, reserved output space and estimated cost.")
        st.caption("The total is not simply 128K plus prompt tokens: BGE and the generator use different tokenizers. "
                   "The complete request must be counted again for the selected model.")
        with st.expander("Budget effects — delivered evidence, not answer accuracy"):
            import pandas as pd
            frame = pd.DataFrame(budgets)
            st.line_chart(frame.pivot(index="Evidence budget (BGE tokens)", columns="Strategy", values="Delivered groups"), x_label="BGE evidence budget", y_label=f"Delivered human-approved groups (of {chosen['Required group denominator']})")
            st.markdown(f"**Evidence-budget comparison across {frozen['summary']['questions']} focused benchmark questions**")
            st.markdown("**How to read this table:** Compare the same selection method across budgets to see whether "
                        "more space delivers more required evidence. Compare methods at the same budget to see which "
                        "delivers more. Prioritize **Complete questions** (all required evidence delivered), then "
                        "**Delivered groups** (individual requirements covered). These are evidence-delivery results, not generated answers.")
            budget_table = pd.DataFrame([{key: value for key, value in row.items() if key != "Question denominator"}
                                         for row in budgets])
            highlighted = budget_table.style.apply(
                lambda row: ["background-color: #e8f2ec; color: #183d29; font-weight: 600"
                             if row["Strategy"] == "RRF Top-30" and row["Evidence budget (BGE tokens)"] == 128000
                             else "" for _ in row], axis=1)
            st.dataframe(highlighted, hide_index=True, width="stretch")
            st.markdown(f"**Main takeaway:** RRF Top-30 at 128K delivered **{chosen['Delivered groups']} of "
                        f"{chosen['Required group denominator']} required evidence groups**, giving "
                        f"**{chosen['Complete questions']} of {chosen['Question denominator']} questions** all their required evidence. "
                        "That was the highest complete-question coverage in this study; gaps remained.")
            st.caption("All rows share the focused subset denominator. Historical reused and newly measured rows remain labeled. Supplementation used a private processing-order adapter. "
                       "Higher budget does not guarantee monotonic inclusion of each individual unit. BGE budget is not a model context window or provider token count.")
        provenance(data, ["data/evals/m8-delivery/experiment-v1/EXPERIMENT_MANIFEST.json", "data/evals/m8-delivery/experiment-v1/RESULTS.json"])
    with st.container(border=True):
        publication = data["completion_publications"][-1] if data["completion_publications"] else None
        if publication:
            complete = publication["summary"]
            st.subheader("08 · Check evidence coverage across the full benchmark")
            st.caption(f"Expanded benchmark · {complete['questions']} questions · Original and focused experiments preserved")
            st.markdown("**What we asked:** Does our selected RRF Top-30 + 128K evidence-budget configuration have "
                        "retrieval and evidence-delivery measurements for every question in the expanded benchmark?")
            st.markdown("**What we did:** Checked question IDs and original wording across the historical datasets "
                        "so no question was missed or counted twice. Reused compatible saved results and ran only "
                        "the missing retrieval and evidence-assembly measurements.")
            st.markdown(f"**What we measured:** **{complete['questions']} questions**—"
                        f"**{complete['answerable_denominator']} answerable** and "
                        f"**{complete['questions'] - complete['answerable_denominator']} insufficient-evidence test questions**. "
                        f"The answerable questions require **{complete['required_group_denominator']} human-approved evidence groups**.")
            st.markdown("**What we found:**\n\n"
                        f"- **Evidence discovered:** Supporting Evidence Units were located for **{complete['parent_groups_located']} "
                        f"of {complete['required_group_denominator']} groups**.\n"
                        f"- **Evidence delivered:** **{complete['groups_delivered']} of {complete['required_group_denominator']} groups** "
                        "reached the assembled context.\n"
                        f"- **Questions with all required evidence:** **{complete['complete_delivery_questions']} of "
                        f"{complete['answerable_denominator']} answerable questions** received every required group.")
            st.markdown("**What we learned:** Finding supporting evidence does not guarantee it reaches context. "
                        "The expanded measurements show the remaining discovery and delivery gaps; the table below identifies affected questions.")
            st.markdown("**What we decided:** Use this expanded benchmark to track future comparisons, while preserving "
                        "the original experiments and their own question sets and scoring methods. These are evidence-coverage "
                        "results—not proof that generated answers are correct or complete.")
            st.caption(f"Saved retrieval inputs: {complete['M7_reused']} reused / {complete['M7_new']} newly measured. "
                       f"Evidence assemblies: {complete['M8_reused']} reused / {complete['M8_new']} newly measured. "
                       "Insufficient-evidence test questions have no positive evidence-group denominator. "
                       "Strict direct-witness and historical overlap scores are kept separate.")
            with st.expander("Expanded cohort measurements and remaining gaps"):
                cohort_names = {"A": "Original Difficult", "B": "NLP — Realistic Queries",
                                "C": "Original Remaining", "D": "Unsupported / Abstention"}
                def coverage(value, total):
                    return "Not applicable" if value is None else f"{value} of {total}"
                st.markdown("**Evidence coverage by question cohort**")
                st.dataframe([{
                    "Question cohort": cohort_names[row["cohort_id"]],
                    "Answerable questions": row["answerable_questions"],
                    "Total questions": row["questions"],
                    "Required evidence groups": row["required_groups"],
                    "Evidence groups located": coverage(row["parent_groups_located"], row["required_groups"]),
                    "Evidence groups delivered": coverage(row["groups_delivered"], row["required_groups"]),
                    "Questions with all required evidence delivered": coverage(row["complete_delivery_questions"], row["answerable_questions"]),
                } for row in publication["cohorts"]], hide_index=True, width="stretch")
                st.caption("Located means supporting Evidence Units were found; delivered means their required evidence "
                           "reached the assembled context. Questions with all required evidence delivered is measured "
                           "against answerable questions, not all questions.")
                st.info("Why Unsupported / Abstention has 0 answerable questions: its three questions were designed "
                        "to test handling of insufficient evidence in the approved source collection. They have no "
                        "positive evidence-group requirements, so coverage is Not applicable—not zero or a failed "
                        "retrieval score. Search can still return documents; that alone does not establish answerability "
                        "or prove a later abstention was correct.")
                st.markdown("**Questions missing required evidence in context**")
                reason_labels = {
                    "BUDGET_DISPLACEMENT_BY_EARLIER_PARENTS": "Earlier Evidence Units used the available budget; this required evidence did not fit.",
                    "RRF30_CUTOFF_EXCLUDES_DISCOVERED_APPROVED_PARENT": "Required supporting Evidence Unit was outside the selected Top-30 candidates.",
                }
                st.dataframe([{"Question": r["question_id"],
                               "Missing human-approved evidence groups": ", ".join(r["target"]["m8"]["missing_group_ids"]),
                               "Why evidence was missing": " ".join(reason_labels.get(reason, "Other recorded cause; see technical details.")
                                                                     for reason in r["target"]["m8"]["missing_reasons"])}
                              for r in data["records"].values()
                              if r.get("target") and r["group_ids"] and not r["target"]["m8"]["complete_question"]], hide_index=True, width="stretch")
                st.caption("These are evidence discovery/delivery gaps—not judgments that generated answers were incorrect.")
                with st.expander("Technical details — original cohort measurements and gap codes"):
                    st.dataframe(publication["cohorts"], hide_index=True, width="stretch")
                    st.dataframe([{"Question": r["question_id"], "Recorded reasons": str(r["target"]["m8"]["missing_reasons"])}
                                  for r in data["records"].values()
                                  if r.get("target") and r["group_ids"] and not r["target"]["m8"]["complete_question"]], hide_index=True, width="stretch")
                    st.caption("Included parents counts complete Evidence Units, not approved evidence groups. "
                               "Direct-hit scores use strict OR/joint-AND scoring for cohorts A/B and historical overlap "
                               "scoring for C; they must not be pooled. None indicates an unavailable or inapplicable measurement.")
            provenance(data, [data["store"].references[publication["manifest_ref"]]["artifact"], data["store"].references[publication["results_ref"]]["artifact"], "data/evals/expanded-benchmark/v1/MANIFEST.json"])
        else:
            st.warning("UNAVAILABLE — no compatible sealed expanded-completion publication. No 34-question success inferred.")
    with st.container(border=True):
        st.subheader("Our offline evaluation framework today")
        st.write("This is our standard place to compare future retrieval and context-assembly changes against approved benchmarks.")
        st.write("Versioned questions + approved labels → controlled inputs/configurations → sealed experiment results → separate discovery and delivery scores → failure attribution → owner decision")
        st.caption("This UI reuses the existing 8514 readers and experiment contracts. It is observability, not a new runner. Future evaluations require separate authorization and versioned outputs. "
                   "8514 stays available until the corresponding 8516 capabilities are developed and verified; no sunset is performed here.")
        st.caption("Answer grounding/completeness and owner acceptance belong to Post-Generation Evaluation & Human Review, not this retrieval scorecard.")
    with st.expander("Question-level historical comparisons"):
        drilldown(data)
    if data["rejected"]:
        st.warning(f"{len(data['rejected'])} incompatible or unsealed records were excluded by the existing reader.")
