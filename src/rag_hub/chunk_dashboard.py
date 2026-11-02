"""Additive read-only M3 inspector; no chunk generation on widget interactions."""

import json

import streamlit as st

from rag_hub.chunk_catalog import DEFAULT_SELECTOR
from rag_hub.operational_selection import (
    DURABLE,
    EmbeddingMetadata,
    construct_catalog,
    resolve_selection,
)


@st.cache_resource(show_spinner=False, max_entries=1)
def _load_chunk_catalog(root, identity, selector, _data):
    selected = resolve_selection(root, selector)
    if selected.key != identity:
        raise ValueError("chunk_cache_identity_changed")
    return construct_catalog(root, _data, selected)


def load_chunk_catalog(root, selector, _data):
    selected = resolve_selection(root, selector)
    selected.check()
    _data.check()
    if _data.binding_fingerprints != selected.manifest["upstream_files"]:
        raise ValueError("incompatible_operational_corpus_and_catalog")
    value = _load_chunk_catalog(root, selected.key, selector, _data)
    value.check()
    return value


load_chunk_catalog.clear = _load_chunk_catalog.clear


@st.cache_resource(show_spinner=False, max_entries=1)
def _embedding_metadata(root, identity, _catalog):
    selected = resolve_selection(root, DURABLE)
    if identity != selected.key:
        raise ValueError("embedding_cache_identity_changed")
    return EmbeddingMetadata(root, _catalog)


def clear_caches():
    load_chunk_catalog.clear()
    _embedding_metadata.clear()


def open_inventory(unit_id=None, section_id=None):
    st.session_state["view"] = "Chunk Inspector"
    st.session_state["chunk_unit_filter"] = unit_id or ""
    st.session_state["chunk_section_filter"] = section_id or ""


def render(data, *, selector=DEFAULT_SELECTOR):
    from rag_hub.dashboard_ui import (
        json_detail,
        open_section,
        open_unit,
        payload,
        qualifications,
        text,
    )

    st.title("Retrieval Chunk Inspector")
    st.caption("Derived lineage catalog · chunks are not independent evidence authorizations. "
               "384 BGE tokens is provisional; no retrieval-quality winner has been measured.")
    selected_release = resolve_selection(data.root, selector)
    st.caption(f"Release: {selected_release.spec['release']} · {selected_release.spec['name']}")
    st.caption(f"Catalog selector: {selector}")
    st.caption(f"Manifest SHA-256: {selected_release.spec['manifest_sha']}")
    catalog = load_chunk_catalog(str(data.root), selector, _data=data)
    catalog.check()
    summary = catalog.manifest["summary"]
    documents = catalog.manifest["documents"]
    a, b, c = st.columns(3)
    a.metric("Catalog chunks", summary["chunks"])
    b.metric("Accounted verified units", summary["units"])
    c.metric("Documents", len(documents))
    if selector == DURABLE:
        metadata = _embedding_metadata(str(data.root), selected_release.key, _catalog=catalog)
        metadata.check()
        value = metadata.export()
        st.info(f"Compatible M4 artifact: {value['embeddings']} embeddings · {value['model']} · "
                f"{value['dimensions']} dimensions. No model or numerical arrays loaded.")
        st.caption(f"Embedding manifest SHA-256: {value['manifest_sha256']}")
        st.caption(value['qualification'])
    else:
        st.caption("Embedding metadata is not selected for this historical inspection mode.")
    did = st.selectbox("Chunk document", ["All", *documents], key="chunk_document")
    unit = st.text_input("Filter by exact verified Unit ID", key="chunk_unit_filter")
    sid = st.text_input("Filter by exact canonical Section ID", key="chunk_section_filter")
    page = st.number_input("Chunk page", min_value=1, value=1, step=1, key="chunk_page")
    rows = catalog.list_chunks(None if did == "All" else did, unit_id=unit or None,
                               section_id=sid or None, offset=(page - 1) * 25, limit=25)
    st.caption(f"{rows['total']} matching chunks · parent membership filters do not imply exact "
               "raw-span allocation to every linked Section.")
    st.dataframe([{"Chunk ID": r["chunk_id"], "Unit ID": r["unit_id"],
                   "Document": r["document_id"], "Type": r["source"]["content_type"],
                   "Tokens": r["token_count"], "Precision": r["lineage"]["precision"]}
                  for r in rows["items"]], hide_index=True, width="stretch")
    with st.expander("Non-indexable/blocked unit accounting"):
        st.dataframe([{"Unit ID": o["unit_id"], "Status": o["status"],
                       "Chunks": len(o["chunk_ids"]),
                       "Reasons": json.dumps(o["non_indexable"] + o["unresolved"])}
                      for o in catalog.outcomes() if o["status"] != "CHUNKED"], hide_index=True)
    entered = st.text_input("Exact version-qualified Chunk ID", key="chunk_entered")
    selected = st.selectbox("Or open a chunk on this page",
                           ["", *[r["chunk_id"] for r in rows["items"]]], key="chunk_selected")
    cid = entered.strip() or selected
    if not cid:
        return
    view = catalog.open_chunk(cid)
    catalog.validate_view(view)
    row, parent = view["chunk"], view["verified_parent"]
    context = parent["consumer"]["llm_context"]
    qualifications(context, parent["consumer"])
    st.subheader("Authorized source display slice")
    st.info("Inspection slice only. Evidence use requires the complete verified parent below, "
            "with its mandatory context and qualifications. This is not independent factual validation.")
    text(view["source_slice"])
    if view["heading_context"]:
        json_detail("Source-backed heading context — not standalone evidence", view["heading_context"])
    st.subheader("Complete authorized parent")
    payload(context["source_content"])
    st.subheader("Required context")
    payload(context["required_context"])
    json_detail("QA observations — our findings, not publisher statements", context["qa_observations"])
    json_detail("Exact display and original source lineage", row["source"] | row["lineage"])
    json_detail("Chunk diagnostics", {k: row[k] for k in (
        "boundary_decision", "reference_numbers", "review_notes", "unknown_token_offsets")})
    json_detail("Citation and authoritative parent publication", {
        "citations": parent["citation_locators"], "publication": parent["publication_identity"]})
    open_unit(row["unit_id"], "chunk-open-parent")
    edges = catalog.get_chunk_sections(cid)
    st.dataframe(edges, hide_index=True, width="stretch")
    for i, edge in enumerate(edges):
        open_section(edge["section_id"], f"chunk-open-section-{i}")
    json_detail("All sibling chunks in this parent", catalog.get_unit_chunks(row["unit_id"]))
