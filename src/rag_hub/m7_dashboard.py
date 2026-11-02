"""Small candidate-search panel; existing Chunk Inspector owns evidence display."""

from pathlib import Path

SELECTOR = "config/hybrid-retrieval-m7-v1.json"
SELECTOR_SHA256 = "87110b099e59aca1460bfd5dc847e073964c392ccf42b559ecf88483cddb37f9"


def get_service(root, selector_sha256):
    import sys

    # Installed Streamlit entrypoints add the app directory, not the repository.
    # Admit only this installed source tree, never a caller-selected import root.
    project = Path(__file__).resolve().parents[2]
    if Path(root).resolve(strict=True) != project:
        raise ValueError("m7_dashboard_requires_its_installed_project_root")
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    from tools.retrieval.service import RetrievalService

    return RetrievalService(Path(root), selector=SELECTOR, selector_sha256=selector_sha256)


def render(root, *, selector, document_ids):
    import streamlit as st

    from rag_hub.m5_dashboard import open_parent

    with st.expander("M7 · Local retrieval — Vector / BM25 / Hybrid", expanded=False):
        st.caption("SEARCH CANDIDATES ONLY · no answers or evidence approval. Open a result in "
                   "the verified Chunk Inspector to inspect its complete qualified parent.")
        if selector != "config/retrieval-chunks-m3-durable-v1.json":
            st.info("Select the durable operational release for M7. Historical inspection is unchanged.")
            return
        cached = st.cache_resource(show_spinner=False)(get_service)
        st.caption("Pinned BGE query instruction · native L2 distance · unchanged BM25 scores · "
                   "rank fusion (RRF), not score averaging. No relevance winner established.")
        with st.form("m7-retrieval"):
            query = st.text_input("Retrieval query", key="m7_query")
            a, b, c = st.columns(3)
            mode = a.selectbox("Retrieval mode", ["hybrid", "vector", "bm25"], key="m7_mode")
            top_k = b.number_input("Final top-K", min_value=1, max_value=992, value=10, step=1,
                                   key="m7_top_k")
            depth = c.number_input("Candidate depth per retriever", min_value=1, max_value=992,
                                   value=50, step=1, key="m7_depth")
            a, b, c, d = st.columns(4)
            did = a.selectbox("Retrieval document", ["All", *document_ids], key="m7_document")
            fmt = b.selectbox("Retrieval format", ["All", "html", "markdown", "pdf"], key="m7_format")
            classification = c.selectbox("Retrieval classification", ["All", "STANDARD_REFERENCE", "ILLUSTRATIVE_REFERENCE"],
                                          key="m7_classification")
            rrf_k = d.number_input("RRF constant", min_value=1, max_value=10000, value=60, step=1,
                                   key="m7_rrf_k")
            submitted = st.form_submit_button("Search authorized chunks")
        if st.button("Reset M7 workers", key="m7_reset"):
            try:
                cached(str(root), SELECTOR_SHA256).close()
            except (ValueError, TypeError, KeyError, OSError):
                st.info("Restore the selected artifacts before reconstructing M7 workers.")
            cached.clear()
            st.session_state.pop("m7_result", None)
            st.rerun()
        if submitted:
            st.session_state.pop("m7_result", None)
            service = None
            filters = {k: v for k, v in (("document_id", did), ("format", fmt),
                       ("reference_classification", classification)) if v != "All"}
            try:
                with st.spinner("Verifying release and retrieving local candidates…"):
                    service = cached(str(root), SELECTOR_SHA256)
                    result = service.search(query, mode=mode, top_k=int(top_k),
                        candidate_depth=int(depth), rrf_k=int(rrf_k), filters=filters)
                # IDs/diagnostics only. Authorization is never cached as a detached payload.
                st.session_state["m7_result"] = result
            except (ValueError, TypeError, KeyError, OSError) as exc:
                if service is not None:
                    service.close()
                cached.clear()
                st.error("Retrieval failed closed. No single-mode fallback or evidence is returned.")
                st.text(str(exc))
        result = st.session_state.get("m7_result")
        if result:
            try:
                cached(str(root), SELECTOR_SHA256).check()
            except (ValueError, TypeError, KeyError, OSError):
                st.session_state.pop("m7_result", None)
                st.error("Retrieval snapshot changed. Reset workers after restoring accepted artifacts.")
                return
            st.caption(f"{len(result['candidates'])} candidates · {result['retrieval_mode']} · "
                       f"{result['diagnostics']['seconds']:.2f}s · complete-parent rehydration required")
            st.text("Retrieval release: " + result["release_identity"])
            st.dataframe([{k: r[k] for k in ("rank", "document_id", "reference_classification",
                "contributing_retrievers", "rrf_score", "vector_rank", "vector_distance",
                "bm25_rank", "bm25_score", "chunk_id")} for r in result["candidates"]],
                hide_index=True, width="stretch")
            if not result["candidates"]:
                st.info("No candidates for this query/filter. This is not an evidence-sufficiency decision.")
            for hit in result["candidates"]:
                st.button(f"Open verified parent · #{hit['rank']} · {hit['document_id']}",
                    key="m7_parent_" + hit["chunk_id"], on_click=open_parent,
                    args=(st.session_state, hit["chunk_id"]))
            with st.expander("Retrieval configuration & release bindings"):
                st.json({"selection": result["selection"], "parameters": result["parameters"],
                         "index_release_bindings": result["index_release_bindings"]}, expanded=False)

            from rag_hub.m8_dashboard import render as render_evidence

            render_evidence(root, result)
