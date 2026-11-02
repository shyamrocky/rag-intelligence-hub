"""Optional ephemeral evidence inspection; native verified parents remain authoritative."""

from pathlib import Path

SELECTOR = "config/evidence-reconstruction-m8-v1.json"
SELECTOR_SHA256 = "e0ac189c8b5ffd331f28ae87f81d56c22868e12c45d7b73e6a5e7f1a65c6bef2"


def get_service(root, selector_sha256):
    import sys

    project = Path(__file__).resolve().parents[2]
    if Path(root).resolve(strict=True) != project:
        raise ValueError("m8_dashboard_requires_its_installed_project_root")
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    from tools.evidence.service import EvidenceService

    return EvidenceService(Path(root), selector=SELECTOR, selector_sha256=selector_sha256)


def render(root, result):
    import streamlit as st

    from rag_hub.dashboard_ui import json_detail, payload, qualifications, text

    st.markdown("#### M8 · Complete verified evidence")
    st.caption("Whole authorized parents, not detached search slices. No answers, relevance "
               "certification or new QA approvals. Evidence is reconstructed on each requested view.")
    budget = st.number_input("Evidence budget (pinned BGE tokens)", min_value=1, max_value=1000000,
                             value=16000, step=1000, key="m8_budget")
    enabled = st.checkbox("View verified evidence package", key="m8_view")
    if not enabled:
        return
    cached = st.cache_resource(show_spinner=False, max_entries=1)(get_service)
    try:
        service = cached(str(root), SELECTOR_SHA256)
        with st.spinner("Reopening complete authorized parents and counting mandatory context…"):
            package = service.assemble(result, token_budget=int(budget))
        # No detached package is stored in session state or a reusable authorization cache.
        counts = package["counts"]
        st.caption(f"{counts['candidates']} candidate chunks → {counts['distinct_parents']} distinct parents · "
                   f"{counts['selected_parents']} selected · {counts['omitted_parents']} omitted")
        st.caption(f"Evidence: {package['budget']['exact_llm_evidence_tokens']:,} / {budget:,} BGE tokens. "
                   "This counting policy does not establish a future LLM context window.")
        if package["status"] != "VERIFIED_EVIDENCE":
            st.info(package["status"] + " · no answer-support decision implied")
        if package["diagnostics"]["omitted"]:
            st.warning("Whole parents omitted by budget. No partial parent or stripped qualification returned.")
            st.dataframe(package["diagnostics"]["omitted"], hide_index=True, width="stretch")
        for item in package["parents"]:
            block = item["evidence"]
            parent = block["verified_parent"]
            consumer = parent["consumer"]
            context = consumer["llm_context"]
            with st.expander(f"Verified parent · {block['document_id']} · "
                             f"{len(block['contributing_candidates'])} contributing chunks", expanded=True):
                text(block["unit_id"])
                st.caption(block["reference_classification"] + f" · {item['token_count']:,} block tokens")
                qualifications(context, consumer)
                st.subheader("Authorized source content")
                payload(context["source_content"])
                st.subheader("Mandatory source context")
                payload(context["required_context"])
                json_detail("Citations and recorded precision", {"citations": parent["citation_locators"],
                             "precision": block["citation_precision"]})
                st.dataframe(block["contributing_candidates"], hide_index=True, width="stretch")
                json_detail("Parent Section lineage and authoritative publication", {
                    "memberships": parent["memberships"], "publication": parent["publication_identity"]})
                json_detail("Additional authorized format context", {
                    k: v for k, v in consumer.items() if k != "llm_context"})
        json_detail("Evidence budget, omissions and deduplication", {
            "budget": package["budget"], "diagnostics": package["diagnostics"],
            "release_identity": package["release_identity"], "retrieval": package["retrieval"]})
    except (ValueError, TypeError, KeyError, OSError) as exc:
        cached.clear()
        st.error("Evidence verification failed closed. This is an integrity/input failure, not no results.")
        st.text(str(exc))
