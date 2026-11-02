"""Native Streamlit inspection UI; no parsing, QA decisions or publication writes."""

from time import perf_counter
from urllib.parse import urlparse

import streamlit as st

from rag_hub.dashboard_data import educational_example
from rag_hub.operational_selection import (
    HISTORICAL,
    MODES,
    construct_dashboard,
    resolve_selection,
    runtime_description,
    switch_release,
)

VIEWS = ["Pipeline Overview", "Document Explorer", "Section & Unit Inspector", "Chunk Inspector"]


@st.cache_resource(show_spinner=False, max_entries=1)
def _load_dashboard(root, identity, selector):
    selected = resolve_selection(root, selector)
    if identity != selected.key:
        raise ValueError("dashboard_cache_identity_changed")
    data = construct_dashboard(root, selected)
    data._operational_selection = selected
    return data


def load_dashboard(root: str, cache_generation=None, *, selector=HISTORICAL):
    # Resolve trusted identities before cache access; no latest/implicit fallback.
    selected = resolve_selection(root, selector)
    data = _load_dashboard(root, selected.key, selector)
    data._operational_selection.check()
    data.check()
    return data


load_dashboard.clear = _load_dashboard.clear


def navigate(view, *, document=None, section=None, unit=None):
    st.session_state["view"] = view
    if document:
        st.session_state["document"] = document
    if section:
        st.session_state["selected_section"] = section
        st.session_state["inspector_mode"] = "Section"
    if unit:
        st.session_state["selected_unit"] = unit
        st.session_state["inspector_mode"] = "Unit"


def open_section(sid, key):
    st.button(sid, key=key, on_click=navigate,
              args=(VIEWS[2],), kwargs={"section": sid}, width="stretch")


def open_unit(uid, key):
    st.button(uid, key=key, on_click=navigate,
              args=(VIEWS[2],), kwargs={"unit": uid}, width="stretch")


def json_detail(label, value):
    with st.expander(label):
        st.json(value, expanded=False)


def text(value):
    """Source strings are data: no HTML, remote images, Markdown or execution."""
    st.text(str(value))


def safe_source_link(url):
    if isinstance(url, str) and urlparse(url).scheme in {"https", "http"}:
        st.link_button("Open publisher source ↗", url)


def disposition(status):
    {"ADMITTED": st.success, "HOLD": st.warning, "EXCLUDED": st.info}[status](status)


def counts(metrics):
    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, f"{value:,}" if isinstance(value, int) else value)


def admission_bar(admitted, excluded, held, *, show_caption=True):
    # Fixed UI-owned color constants; source text never enters this HTML.
    total = admitted + excluded + held
    if not total:
        return
    widths = [100 * n / total for n in [admitted, excluded, held]]
    segments = "".join(
        f'<div style="width:{width:.6f}%;background:{color};height:14px"></div>'
        for width, color in zip(widths, ["#277B69", "#B7C4CF", "#D4A34A"]))
    st.markdown(f'<div style="display:flex;border-radius:6px;overflow:hidden">{segments}</div>',
                unsafe_allow_html=True)
    if show_caption:
        st.caption(f"ADMITTED {admitted:,} · EXCLUDED {excluded:,} · HOLD {held:,}")


def format_breakdown(data):
    for row in data.format_breakdown():
        label, percentage = st.columns([3, 1])
        label.markdown(f"#### {row['label']}")
        percentage.markdown(f"**{row['admitted_percent']:.1f}% admitted**")
        admission_bar(row["ADMITTED"], row["EXCLUDED"], row["HOLD"], show_caption=False)
        details = [f"{row['documents']} {'document' if row['documents'] == 1 else 'documents'}",
                   f"{row['sections']:,} Sections", f"{row['ADMITTED']:,} admitted"]
        if row["STANDARD"] + row["ILLUSTRATIVE"] == row["ADMITTED"]:
            details += [f"{row['STANDARD']:,} standard", f"{row['ILLUSTRATIVE']:,} illustrative"]
        details += [f"{row['units']} verified units", f"{row['EXCLUDED']} intentional exclusions"]
        if row["HOLD"]:
            details.append(f"{row['HOLD']} HOLD")
        st.caption(" · ".join(details))


def payload(value):
    """Render only gateway-authorized source/context fields, retaining structure.

    Tables and other native variants remain structured, rather than guessing how
    unknown row/column representations map to a new table schema.
    """
    if isinstance(value, list):
        for index, item in enumerate(value):
            if len(value) > 1:
                st.caption(f"Element {index + 1}")
            payload(item)
    elif isinstance(value, dict):
        if "restricted_projection" in value:
            projection = value["restricted_projection"]
            if not isinstance(projection.get("consumable_text"), str):
                raise ValueError("missing_warning_bearing_native_projection")
            for warning in projection.get("warnings", []):
                st.warning(str(warning))
            text(projection["consumable_text"])
            return
        for key, item in value.items():
            if key in {"citations", "source_span", "source_sha256", "source_id", "source_title",
                       "source_url", "section_id", "structure", "kind", "content_type"}:
                continue
            if item is None or item == [] or item == {}:
                continue
            if key in {"text", "rendered_text", "display_text", "latex"}:
                text(item)
            elif key in {"table", "structure"}:
                st.caption(key.replace("_", " ").title())
                headers = item.get("headers", []) if isinstance(item, dict) else []
                rows = item.get("rows", []) if isinstance(item, dict) else []
                if (headers and len(set(headers)) == len(headers) and rows
                        and all(isinstance(r, list) and len(r) == len(headers) for r in rows)):
                    st.dataframe({h: [r[i] for r in rows] for i, h in enumerate(headers)},
                                 hide_index=True, width="stretch")
                    st.caption("Exact published row/header associations; no inferred cells.")
                else:
                    st.json(item, expanded=True)
            elif isinstance(item, (dict, list)):
                st.caption(key.replace("_", " ").title())
                payload(item)
            else:
                text(f"{key.replace('_', ' ')}: {item}")
    elif value is not None:
        text(value)


def qualifications(context, consumer):
    expiry = consumer.get("publication_expiration")
    if expiry:
        st.caption(f"Publication status: {expiry.get('status', 'Not recorded')}")
        if expiry.get("warning"):
            st.warning(expiry["warning"])
        json_detail("Publication expiration metadata", expiry)
    observations = context.get("qa_observations", [])
    if observations:
        st.subheader("QA observations")
        st.caption("Our ingestion/QA findings — not statements attributed to the publisher.")
        for observation in observations:
            note = (observation.get("explanation") or observation.get("description")
                    or observation.get("issue_id") or "Recorded QA observation")
            st.warning(note) if observation.get("severity") == "WARNING" else st.info(note)
    st.subheader("Qualifications & permitted use")
    q = context["qualification"]
    for limitation in q.get("limitations", []):
        st.info(str(limitation))
    scope = q.get("documentation_scope", {})
    for limitation in scope.get("limitations", []):
        st.warning(str(limitation))
    left, right = st.columns(2)
    with left:
        st.caption("Allowed usage")
        for usage in q.get("allowed_usage", []):
            text(usage)
    with right:
        st.caption("Forbidden usage")
        for usage in q.get("forbidden_usage", []):
            text(usage)
    json_detail("Complete native qualifications", q)


def render_verified_unit(data, uid):
    from rag_hub.chunk_dashboard import open_inventory

    value = data.verified_unit(uid)
    st.button("Inspect this unit's chunk lineage", key="unit-chunk-lineage",
              on_click=open_inventory, kwargs={"unit_id": uid})
    data.validate_unit(value)  # fail before emitting evidence UI
    st.caption("VERIFIED_CONSUMER_EVIDENCE · complete publication-bound unit · not a chunk")
    text(uid)
    st.subheader(data.document(value["document_id"])["source"]["title"])
    counts([("Document", value["document_id"]), ("Format", value["format"].upper()),
            ("Classification", value["reference_classification"])])
    consumer = value["consumer"]
    context = consumer["llm_context"]
    # Mandatory restrictions appear before source content and are never a toggle.
    qualifications(context, consumer)
    st.subheader("Source content")
    st.caption("Faithful attributed source material; source claims are not independently certified.")
    payload(context["source_content"])
    st.subheader("Required context")
    if context["required_context"]:
        payload(context["required_context"])
    else:
        st.caption("No additional consumer context recorded for this unit.")
    json_detail("Citations and source locations", value["citation_locators"])
    json_detail("QA publication identity", value["publication_identity"])
    json_detail("Recorded source fidelity and related evidence", {
        "source_fidelity": consumer.get("source_fidelity"),
        "related_evidence": consumer.get("related_evidence", []),
        "format_context": consumer.get("context"), "provider_tab": consumer.get("provider_tab"),
    })
    st.subheader("Related Sections")
    relationships(data, uid, key="unit-inspector")


def relationships(data, uid, key):
    rows = data.relationships(uid)
    st.caption("INSPECTION_ONLY · exact membership index; no inferred neighboring Sections")
    st.dataframe(rows, hide_index=True, width="stretch")
    # A Section may have more than one role. Keep every edge above; one button per ID.
    for sid in dict.fromkeys(r["section_id"] for r in rows):
        open_section(sid, f"{key}-section-{sid}")


def assembly(data):
    st.subheader("How Sections Become Verified Units")
    st.caption("Recovery & Assembly connects Parsing to QA. This view explains existing work; "
               "it does not execute assembly or grant approval.")
    st.write("Extraction records text, elements and source positions. Format-specific recovery "
             "proposes source-supported relationships. QA validates fidelity, membership, context "
             "and provenance. A QA publication authorizes complete units. The unified adapter "
             "reads published relationships; it does not discover or approve them.")
    st.caption("PyMuPDF, Docling, MinerU and format-specific adapters are possible extraction "
               "paths; only source-specific recorded use is reported in Parsing evidence.")
    mode = st.radio("Relationship view", ["Educational example", "Explore actual corpus relationships"],
                    horizontal=True, key="relationship_mode")
    if mode == "Educational example":
        example = educational_example()
        st.info(example["label"])
        left, arrow, right = st.columns([3, 1, 2])
        with left:
            for section in example["sections"]:
                with st.container(border=True):
                    st.write(f"{section['section_id']} · {section['type']}")
                    st.caption(section["role"])
        arrow.markdown("### →")
        with right, st.container(border=True):
            st.write("U001 · Verified Unit (illustrative)")
            st.caption("Only after source validation and publication authorization.")
        return
    docs = data.documents()
    did = st.selectbox("Relationship document", [r["Document"] for r in docs], key="relationship_doc")
    units = data.units(did)
    uid = st.selectbox("Verified Unit ID", [r["unit_id"] for r in units], key="relationship_unit")
    if not uid:
        st.info("No verified units for this document.")
        return
    st.caption(f"Actual corpus relationships · {did}")
    open_unit(uid, "assembly-open-unit")
    edges = data.relationships(uid)
    left, arrow, right = st.columns([3, 1, 2])
    with left:
        for index, edge in enumerate(edges):
            with st.container(border=True):
                open_section(edge["section_id"], f"assembly-{index}")
                st.caption(f"{edge['native_structural_type']} · {edge['role']} "
                           f"(native: {edge['native_role']}) · {edge['locator']}")
                if edge["context_only_in_unit"]:
                    st.info("Context membership here; not an independent evidence passage.")
                if edge["scope_limited_projection"]:
                    st.warning("Scope-limited source projection; raw Section is not authorized.")
    arrow.markdown("### →")
    value = data.verified_unit(uid)
    with right, st.container(border=True):
        st.write("Verified consumer unit")
        text(value["document_id"])
        st.caption(f"{len(edges)} role-bearing links · {len({e['section_id'] for e in edges})} "
                   "unique canonical Sections")
        st.caption("Authorized by the QA publication below.")
        st.json(value["publication_identity"], expanded=False)
    qualifications(value["consumer"]["llm_context"], value["consumer"])
    json_detail("Recorded relationship evidence — no new discovery", data.assembly_evidence(value))
    st.caption("Relationship proposal, QA validation and publication authorization are separate steps.")


def overview(data):
    s = data.summary()
    st.title("Ingestion pipeline")
    st.write("Explore the frozen corpus, its quality decisions and verified consumer relationships.")
    counts([("Sources", s["documents"]), ("Sections", s["sections"]),
            ("Admitted", s["admitted"]), ("Verified units", s["units"])])
    stages = [
        ("Acquisition", "16 frozen source snapshots", VIEWS[1]),
        ("Classification", "11 HTML · 1 Markdown · 4 PDF", VIEWS[1]),
        ("Parsing", f"{s['sections']:,} canonical Sections", VIEWS[1]),
        ("Recovery & Assembly", "Published Section ↔ Unit links", VIEWS[0]),
        ("QA Validation", f"{s['admitted']:,} admitted · {s['HOLD']} HOLD", VIEWS[1]),
        ("QA Publication", "3 accepted format publications", VIEWS[1]),
        ("Unified Layer", f"{s['units']} units · {s['membership_edges']:,} links", VIEWS[2]),
    ]
    for index, (column, (name, fact, view)) in enumerate(zip(st.columns(7), stages)):
        with column, st.container(border=True):
            st.button(name, key=f"stage-{index}", on_click=navigate, args=(view,), width="stretch")
            st.caption(fact)
            if index < 6:
                st.caption("→")
    st.caption("Frozen evidence, not a live stage execution monitor. Normalization is included in "
               "the parsing/recovery presentation; underlying stage ownership remains unchanged.")
    admission_bar(s["admitted"], s["excluded"], s["HOLD"])
    format_breakdown(data)
    st.caption("Accepted publications · source-bound provenance · mandatory qualifications retained. "
               f"{s['units']} verified consumer units are not retrieval chunks.")
    with st.expander("Format breakdown and documented PDF HOLD categories"):
        st.dataframe([{"Format": f.upper(), **v} for f, v in s["formats"].items()],
                     hide_index=True, width="stretch")
        st.dataframe([{"Documented issue family": k, "HOLD Sections": v}
                      for k, v in data.hold_categories().items()], hide_index=True, width="stretch")
        st.caption("Inherited QA outcomes; the dashboard does not detect or reclassify failures.")
    assembly(data)


def document_explorer(data):
    st.title("Document Explorer")
    a, b, c, d = st.columns([1, 2, 2, 1])
    fmt = a.selectbox("Format", ["All", "HTML", "Markdown", "PDF"], key="format_filter")
    query = b.text_input("Search documents", key="doc_search")
    publishers = sorted({d["Publisher"] for d in data.documents()})
    publisher = c.selectbox("Publisher", ["All", *publishers], key="publisher_filter")
    status = d.selectbox("Has Sections", ["All", "ADMITTED", "HOLD", "EXCLUDED"], key="doc_status")
    rows = data.documents(fmt=None if fmt == "All" else fmt.lower(), query=query,
                          publisher=None if publisher == "All" else publisher,
                          status=None if status == "All" else status)
    st.dataframe(rows, hide_index=True, width="stretch", height=300)
    st.caption("Click column headings to sort. Counts refer to unique Sections; units and links differ.")
    if not rows:
        st.info("No documents match these filters.")
        return
    ids = [r["Document"] for r in rows]
    if st.session_state.get("document") not in ids:
        st.session_state["document"] = ids[0]
    did = st.selectbox("Open document", ids, key="document")
    profile = data.document_profile(did)
    doc = profile["document"]
    st.subheader(doc["source"]["title"])
    counts([("Sections", doc["counts"]["sections"]),
            ("Admitted", doc["counts"].get("ADMITTED", 0)),
            ("Excluded", doc["counts"].get("EXCLUDED", 0)),
            ("HOLD", doc["counts"].get("HOLD", 0)), ("Units", len(doc["unit_ids"]))])
    admission_bar(doc["counts"].get("ADMITTED", 0), doc["counts"].get("EXCLUDED", 0),
                  doc["counts"].get("HOLD", 0))
    summary, parsing, qa = st.tabs(["Source & snapshot", "Parsing evidence", "QA overview"])
    with summary:
        safe_source_link(doc["source"].get("canonical_url"))
        text(f"Format: {doc['format']} · Publisher: {doc['source'].get('publisher', 'Not recorded')}")
        text(f"Capture time: {doc['source'].get('captured_at') or 'Not recorded'}")
        text(f"Frozen source SHA-256: {doc['snapshot']['sha256']}")
        json_detail("Frozen snapshot and source identity", {"source": doc["source"],
                                                            "snapshot": doc["snapshot"]})
        json_detail("Accepted publication & selector", {
            "selector": doc["selector_path"], "publication": doc["publication_identity"]})
    with parsing:
        st.caption("INSPECTION_ONLY · recorded provenance, not a new parsing execution")
        for name, value in profile["parser"].items():
            text(f"{name.replace('_', ' ')}: {value}")
        st.dataframe([{"Native structural type": k, "Sections": v}
                      for k, v in profile["structural_types"].items()], hide_index=True)
        json_detail("Source location coverage", profile["locator_coverage"])
        st.caption("Native types are historical extraction observations, not a fresh semantic "
                   "classification. Current QA may qualify a narrower/different presentation.")
    with qa:
        st.dataframe([{"Reference classification": k, "Sections": v}
                      for k, v in profile["classifications"].items()], hide_index=True)
        st.dataframe([{"Issue category": k, "Occurrences": v}
                      for k, v in profile["issue_categories"].items()], hide_index=True)
        st.caption("Issue occurrences can overlap. Warnings on admitted units do not mean HOLD.")
    st.subheader("Section inventory")
    a, b, c = st.columns([1, 2, 1])
    status = a.selectbox("Section status", ["All", "ADMITTED", "HOLD", "EXCLUDED"])
    search = b.text_input("Search Section ID, type or issue")
    size = c.selectbox("Rows per page", [10, 25, 50, 100], index=1)
    # Filters define a new pagination scope; session state retains each scope's page.
    page_key = f"page:{did}:{status}:{search}:{size}"
    page = st.number_input("Page", min_value=1, value=1, step=1, key=page_key)
    result = data.sections(did, status=None if status == "All" else status, query=search,
                           offset=(page - 1) * size, limit=size)
    st.caption(f"{result['total']} matching Sections · metadata only")
    st.dataframe(result["items"], hide_index=True, width="stretch")
    if result["items"]:
        sid = st.selectbox("Select Section to inspect", [r["Section ID"] for r in result["items"]])
        open_section(sid, "document-open-section")
    else:
        st.info("No Sections on this page. Change the filters or return to page 1.")


def section_inspector(data, sid):
    from rag_hub.chunk_dashboard import open_inventory

    s = data.section(sid)
    st.button("Inspect this Section's chunk lineage", key="section-chunk-lineage",
              on_click=open_inventory, kwargs={"section_id": sid})
    st.caption("INSPECTION_ONLY · catalog metadata is not evidence authorization")
    disposition(s["admission_status"])
    text(sid)
    st.subheader(data.document(s["document_id"])["source"]["title"])
    st.write(f"{s['document_id']} · {s['format'].upper()} · {s['native_structural_type']}")
    text(f"Classification: {s.get('reference_classification') or 'Not applicable'}")
    if s.get("native_reference_classification"):
        text(f"Native classification: {s['native_reference_classification']}")
    if s.get("reason"):
        st.info(s["reason"])
    if s["context_only"]:
        st.warning("Context-only in all verified memberships. Open a complete unit; "
                   "this Section is not an independently consumable passage.")
    if s["scope_limited_projection"]:
        st.warning("Scope-limited projection: original raw text is not an unrestricted fallback.")
    json_detail("QA findings and limitations", {"issues": s["issues"],
                                               "unit_qualifications": s["unit_qualifications"]})
    json_detail("Original source locations", s["citation_locators"])
    json_detail("Provenance, decision references & publication", {
        "provenance": s["provenance"], "evidence_refs": s["evidence_refs"],
        "issue_ids": s["issue_ids"], "publication": s["publication_identity"]})
    if not s["unit_ids"]:
        st.info("No verified unit membership. Only inspection metadata and source references "
                "are available; restricted raw source text is not displayed.")
        return
    st.subheader("Linked verified units")
    st.dataframe(s["memberships"], hide_index=True, width="stretch")
    for index, uid in enumerate(s["unit_ids"]):
        open_unit(uid, f"section-linked-unit-{index}")


def inspector(data):
    st.title("Section & Unit Inspector")
    mode = st.radio("Inspect", ["Section", "Unit"], horizontal=True, key="inspector_mode")
    with st.form("id-search"):
        entered = st.text_input(f"Exact {'canonical Section' if mode == 'Section' else 'publication-qualified Unit'} ID", key="inspector_entered")
        submitted = st.form_submit_button("Inspect ID")
    key = "selected_section" if mode == "Section" else "selected_unit"
    if submitted:
        st.session_state[key] = entered.strip()
    target = st.session_state.get(key)
    if not target:
        st.info("Enter an exact ID, or open a document/relationship to choose one.")
        return
    if mode == "Section":
        section_inspector(data, target)
    else:
        render_verified_unit(data, target)


def main(root):
    start = perf_counter()
    st.set_page_config(page_title="RAG Hub · Ingestion", page_icon="📚", layout="wide")
    st.sidebar.title("RAG Intelligence Hub")
    st.sidebar.caption("Ingestion inspection · local & read-only")
    st.sidebar.radio("View", VIEWS, key="view")
    selector = st.sidebar.selectbox("Operational release", list(MODES),
        format_func=lambda key: MODES[key]["name"], key="operational_release")
    if st.sidebar.button("Rebuild verified snapshot", help="Re-run the selected verified loader."):
        from rag_hub.chunk_dashboard import clear_caches

        load_dashboard.clear()
        clear_caches()
        st.rerun()
    try:
        with st.spinner("Loading and verifying the accepted corpus. First load takes about 30 seconds…"):
            selected = resolve_selection(root, selector)
            switch_release(st.session_state, selected.key)
            data = load_dashboard(str(root), selector=selector)
            data.check()
        st.sidebar.caption(f"Selected release: {selected.spec['release']}")
        st.sidebar.caption("Read-only historical inspection" if selected.spec['loader'] != 'durable'
                           else "Current operational candidate · explicit opt-in · no global cutover")
        st.sidebar.caption(f"Catalog manifest: {selected.spec['manifest_sha']}")
        st.sidebar.caption(f"Verified snapshot construction: {data.load_seconds:.1f}s. "
                           "Reused across interactions; filesystem integrity remains checked.")
        with st.sidebar.expander("Runtime & explicit launch"):
            st.json(runtime_description(), expanded=False)
        if selector == "config/retrieval-chunks-c01-v2.json":
            st.sidebar.caption("C01 catalog scope: 61 units / 88 chunks. Other ingestion views retain "
                               "the compatible historical 550-unit corpus.")
        from rag_hub.m5_dashboard import render as render_index

        render_index(root, selector=selector,
                     document_ids=[d["document_id"] for d in data.corpus.catalog.list_documents()])
        from rag_hub.m7_dashboard import render as render_retrieval

        render_retrieval(root, selector=selector,
                         document_ids=[d["document_id"] for d in data.corpus.catalog.list_documents()])
        view = st.session_state["view"]
        if view == VIEWS[0]:
            overview(data)
        elif view == VIEWS[1]:
            document_explorer(data)
        elif view == VIEWS[2]:
            inspector(data)
        else:
            from rag_hub.chunk_dashboard import render

            render(data, selector=selector)
        st.sidebar.caption(f"Current server render: {perf_counter() - start:.2f}s "
                           "(inspection timing, not retrieval latency).")
    except (ValueError, TypeError, KeyError, OSError) as exc:
        message = str(exc)
        if message.startswith(("unknown_", "Unknown ")):
            st.error("ID not found in the accepted catalog/publication. Check the complete ID.")
        else:
            st.error("Verified snapshot unavailable or integrity invalidated. No fallback evidence "
                     "is displayed. Restore the accepted files, then click Rebuild verified snapshot.")
        with st.expander("Technical diagnostic"):
            text(f"{type(exc).__name__}: {message}")
    st.caption("Read-only ingestion, lineage & opt-in M7 candidate retrieval · no QA changes or generation")
