"""Preparation views. Source text uses native authorized display helpers."""

from collections import Counter
from pathlib import Path

import streamlit as st

from apps.knowledge_preparation.backbone import technical_backbone
from apps.knowledge_preparation.data import PDFWalkthrough
from apps.knowledge_preparation.process import STAGE_BY_PAGE, STAGES
from rag_hub.dashboard_data import locator_label
from rag_hub.dashboard_ui import payload, qualifications, safe_source_link

ROOT = Path(__file__).resolve().parents[2]

FOCUS = {
    "Sources": "Original document, acquisition, permissions and provenance.",
    "Parse": "Extracted text blocks, structural elements and source locations.",
    "Normalize": "Canonical Sections, document structure and source mappings.",
    "QA & Verified Evidence": "Approved evidence, withheld content and the context needed to use it responsibly.",
    "Parsing & Evidence": "How parsed blocks become organized Sections and approved evidence units.",
    "Chunks & Lineage": "Searchable chunks and their connections to complete evidence and original sources.",
    "Embeddings & Indexes": "How saved chunks are represented for vector and keyword search.",
    "Validation & Publications": "Integrity checks, source-use restrictions and published artifact versions.",
}


@st.cache_resource(show_spinner=False, max_entries=1)
def load():
    return PDFWalkthrough(ROOT, formats=("pdf", "markdown", "html"))


def document_changed():
    """Keep source context independent of a page-specific widget identity."""
    st.session_state["kp_selected_document"] = st.session_state["kp_document"]


def chunk_changed():
    st.session_state["kp_selected_chunk"] = st.session_state["kp_chunk"]


def select_evidence_unit(walk, uid):
    ids = [u["unit_id"] for u in walk.units]
    labels = {u["unit_id"]: f"Evidence {n:02d} · {locator_label(u['citation_locators'])}"
              for n, u in enumerate(walk.units, 1)}
    return st.selectbox("Follow evidence unit", ids, key="kp_unit", format_func=labels.__getitem__,
                        index=ids.index(uid), persist_state="session")


def selected_chunk(walk, uid):
    rows = [r for r in walk.chunks.values() if r["unit_id"] == uid]
    if not rows:
        st.info("No retrieval chunks recorded for this evidence unit.")
        return None
    ids = [r["chunk_id"] for r in rows]
    current = st.session_state.get("kp_selected_chunk", st.session_state.get("kp_chunk"))
    if current not in ids:
        current = ids[0]
    st.session_state["kp_selected_chunk"] = current
    if st.session_state.get("kp_chunk") not in ids:
        st.session_state.pop("kp_chunk", None)
    return st.selectbox("Related retrieval chunk", ids, key="kp_chunk",
                        index=ids.index(current), on_change=chunk_changed,
                        format_func=lambda cid: f"Chunk {ids.index(cid) + 1:02d} · "
                        f"{walk.chunks[cid]['token_count']} BGE tokens", persist_state="session")


def evidence(walk, uid, *, value=None):
    value = value or walk.unit(uid)
    walk.data.validate_unit(value)
    consumer = value["consumer"]
    context = consumer["llm_context"]
    st.caption("The complete evidence unit is checked against its saved source. "
               "Document text is reference material, not instructions to follow.")
    # Keep native warnings/restrictions ahead of source content. Never expose a bare slice.
    qualifications(context, consumer)
    st.subheader("Verified source content")
    payload(context["source_content"])
    st.subheader("Required context")
    if context["required_context"]:
        payload(context["required_context"])
    else:
        st.caption("No additional context recorded for this unit.")
    with st.expander("Technical details — citations and source bindings"):
        st.json({"unit_id": uid, "citations": value["citation_locators"],
                 "publication": value["publication_identity"],
                 "source_fidelity": consumer.get("source_fidelity"),
                 "known_limitations": consumer.get("known_limitations"),
                 "allowed_usage": consumer.get("allowed_usage"),
                 "forbidden_usage": consumer.get("forbidden_usage")})


def overview(walk, _uid):
    with st.container(key="kp-overview"):
        st.title("Knowledge Preparation")
        st.write("From source documents to searchable knowledge.")
        format_counts = Counter(d["format"] for d in walk.documents)
        labels = {"pdf": "PDF", "markdown": "Markdown", "html": "HTML"}
        source_counts = " · ".join(
            f"{count} {labels[fmt]} source{'s' if count != 1 else ''}"
            for fmt in ("pdf", "markdown", "html") if (count := format_counts[fmt])
        )
        st.caption(f"Read-only overview · {len(walk.documents)} Verified sources connected: {source_counts}")
        with st.container(key="preparation-pipeline"):
            st.subheader("Preparation pipeline")
            st.caption("Start with the process. Select a stage to inspect its saved artifacts.")
            with st.container(key="kp-pipeline-stages"):
                for number, (column, stage) in enumerate(zip(st.columns(7, gap="small"), STAGES), 1):
                    with column, st.container(key=f"kp-stage-{number:02d}"):
                        st.caption(f"{number:02d}")
                        st.page_link(st.session_state["kp_pages"][stage["page"]], label=stage["title"])
                        st.caption(f"Input: {stage['input']}")
                        st.caption(f"↓ Output: {stage['output']}")
            st.divider()
            dense, lexical = st.columns(2)
            dense.markdown("**Dense search:** chunks → embeddings → vector index")
            lexical.markdown("**Lexical search:** chunks → BM25 index")
            st.caption("Blocks → canonical Sections → QA-authorized evidence units → retrieval chunks. "
                       "These are different objects, not interchangeable names.")
            st.caption("QA and unit formation are closely connected. Validation and publication occur "
                       "throughout the process, not only at the final stage. Links inspect saved artifacts.")
            with st.expander("How the process maps to implementation milestones"):
                st.dataframe([{"Process stage": s["title"], "What happens": s["detail"],
                               "Implementation boundary": s["milestone"]} for s in STAGES],
                             hide_index=True, width="stretch")
                st.caption("The 61 C01 verified units were inputs to M0. M0 defines a contract; "
                           "it does not parse documents, grant QA eligibility or split chunks.")
        with st.container(key="kp-source-scope"):
            st.subheader("Choose your scope")
            documents = walk.documents
            formats = sorted({d["format"].upper() for d in documents})
            left, right = st.columns([1, 3])
            fmt = left.selectbox("Format", ["All formats", *formats], key="kp_scope_format",
                                 persist_state="session")
            matching = [d for d in documents if fmt == "All formats" or d["format"].upper() == fmt]
            choices = ["All matching sources", *[d["document_id"] for d in matching]]
            if st.session_state.get("kp_scope_source") not in choices:
                st.session_state["kp_scope_source"] = choices[0]
            names = {d["document_id"]: d["source"]["title"] for d in matching}
            selected = right.selectbox("Source", choices, key="kp_scope_source", persist_state="session",
                                       format_func=lambda value: value if value == choices[0]
                                       else f"{value} · {names[value]}")
            if selected != choices[0]:
                st.session_state["kp_selected_document"] = selected
            scoped = matching if selected == choices[0] else [d for d in matching if d["document_id"] == selected]
            if len(scoped) == 1:
                st.session_state["kp_selected_document"] = scoped[0]["document_id"]
            scope_name = ("All connected sources" if fmt == "All formats" else f"{fmt} · All sources") \
                if selected == choices[0] else f"{selected} · {names[selected]}"
            st.caption(f"Showing: {scope_name} · {len(scoped)} source(s)")
            st.caption("Totals combine only connected verified publications. Filter by format or choose a "
                       "document for its breakdown. Only published, verified sources are included.")
        selected_ids = {d["document_id"] for d in scoped}
        units = [u for u in walk.units if u["document_id"] in selected_ids]
        chunks_in_scope = {cid: r for cid, r in walk.chunks.items() if r["document_id"] in selected_ids}
        indexed = set(walk.indexes["Vector index"]["records"]) & set(chunks_in_scope)
        bge_vectors = set(walk.embeddings) & set(chunks_in_scope)
        bm25_records = set(walk.indexes["BM25 index"]["records"]) & set(chunks_in_scope)
        covered = indexed & bge_vectors & bm25_records
        parsed = [walk.parsed[d["document_id"]] for d in scoped]
        block_count = f"{sum(p['total'] for p in parsed):,}" if all(
            p["total"] is not None for p in parsed) else "unavailable"
        section_count = sum(d["counts"]["sections"] for d in scoped)
        admitted_count = sum(d["counts"].get("ADMITTED", 0) for d in scoped)
        st.caption("Counts describe different objects and published relationships, not a one-to-one conversion.")
        with st.container(key="preparation-metrics"):
            for number, (column, (label, value)) in enumerate(zip(st.columns(4), [
                    ("Sources", len(scoped)), ("Evidence units", len(units)),
                    ("Retrieval chunks", len(chunks_in_scope)),
                    ("Search index coverage", f"{len(covered)}/{len(chunks_in_scope)}")])):
                with column, st.container(key=f"kp-metric-{number}"):
                    st.metric(label, value)
                    if number == 0:
                        st.caption(f"{block_count} parsed blocks → {section_count:,} canonical Sections "
                                   f"→ {admitted_count:,} admitted Sections")
                    if number == 3:
                        st.caption(f"BGE: {len(bge_vectors):,} saved vectors · "
                                   f"BM25: {len(bm25_records):,} indexed text records")
        with st.container(key="kp-source-breakdown"):
            st.subheader("Source breakdown")
            st.caption(scope_name)
            if len(scoped) == 1:
                st.write(scoped[0]["source"]["title"])
                source = walk.for_document(scoped[0]["document_id"]).source_metadata
                st.caption(f"{source.get('publisher', 'Publisher not recorded')} · "
                           f"{scoped[0]['format'].upper()} · {source.get('rights_status', 'Rights not recorded')}")
            counts = {key: sum(d["counts"].get(key, 0) for d in scoped)
                      for key in ["sections", "ADMITTED", "HOLD", "EXCLUDED"]}
            if len(scoped) > 1:
                st.caption(f"Combined structure across {len(scoped)} sources")
            st.dataframe([
                {"Disposition": "All canonical sections", "Sections": counts["sections"],
                 "What it means": "Recorded document structure; not all sections become evidence."},
                {"Disposition": "Admitted", "Sections": counts["ADMITTED"],
                 "What it means": "Approved for use under the source's qualifications and context rules."},
                {"Disposition": "HOLD", "Sections": counts["HOLD"],
                 "What it means": "Withheld pending verification or resolution; unavailable as evidence."},
                {"Disposition": "Excluded", "Sections": counts["EXCLUDED"],
                 "What it means": "Intentionally left outside eligible evidence under the recorded QA policy."},
            ], hide_index=True, width="stretch")
            st.caption("Sections and evidence units are different objects. Multiple sections can form one "
                       "unit; supporting headings/context are not independent evidence.")
            st.page_link(st.session_state["kp_pages"]["QA & Verified Evidence"], label="Inspect structure & evidence →")
        with st.container(key="kp-source-inventory"):
            st.subheader("Sources in this scope")
            st.divider()
            for document in scoped:
                with st.container(border=True):
                    title, action = st.columns([4, 1], vertical_alignment="center")
                    title.write(f"{document['document_id']} · {document['source']['title']}")
                    title.caption(f"{document['format'].upper()} · "
                                  f"{document['counts']['sections']} sections · "
                                  "Saved publication bindings verified; source-use qualifications apply")
                    with action:
                        if st.button("Inspect source →", key=f"kp-inspect-{document['document_id']}"):
                            st.session_state["kp_selected_document"] = document["document_id"]
                            st.switch_page(st.session_state["kp_pages"]["Sources"])


def sources(walk, _uid):
    source = walk.source_metadata
    st.subheader(source["title"])
    safe_source_link(source["canonical_url"])
    with st.container(border=True):
        st.subheader("Document")
        st.dataframe([{"Field": label, "Value": str(source.get(key) or "Not recorded")}
                      for label, key in [("Document", "doc_id"), ("Publisher", "publisher"),
                                         ("Version", "source_version"), ("Format", "source_format"),
                                         ("Language", "language"), ("File size (bytes)", "byte_size")]],
                     hide_index=True, width="stretch")
    with st.container(border=True):
        st.subheader("Acquisition & Permissions")
        st.dataframe([{"Field": label, "Value": str(source.get(key) or "Not recorded")}
                      for label, key in [("Rights", "rights_status"), ("Captured at", "captured_at")]],
                     hide_index=True, width="stretch")
        if source.get("acquisition_basis"):
            st.info(source["acquisition_basis"])
        else:
            st.caption("Acquisition basis is not recorded in the bound source metadata available here.")
    st.caption("The immutable source snapshot is hash-checked by the native reader. No new source is downloaded.")
    with st.expander("Technical provenance — frozen source"):
        st.json({"source_sha256": walk.document["snapshot"]["sha256"],
                 "version": source["source_version"], "publication": walk.document["publication_identity"]})


def change_record_page(key, delta):
    st.session_state[key] += delta


def reset_section_page():
    st.session_state["kp_section_page"] = 1


def record_pagination(total, key):
    """UI-only pagination; source locations remain distinct from table pages."""
    pages = max(1, (total + 24) // 25)
    page = min(max(st.session_state.get(key, 1), 1), pages)
    st.session_state[key] = page
    previous, guidance, following = st.columns([1, 3, 1], vertical_alignment="center")
    previous.button("Previous", key=f"{key}_previous", disabled=page == 1,
                    on_click=change_record_page, args=(key, -1))
    start = (page - 1) * 25
    guidance.caption(f"Records {min(start + 1, total)}–{min(page * 25, total)} of {total} "
                     f"· Page {page} of {pages}")
    following.button("Next", key=f"{key}_next", disabled=page == pages,
                     on_click=change_record_page, args=(key, 1))
    if not total:
        st.info("No records match the selected scope.")
    return start


def related_items(walk, items, *, kind, start=0):
    """Small metadata-only drill-down, restricted to the currently displayed rows."""
    if not items:
        return
    field = "Block ID" if kind == "block" else "Section ID"
    ids = [item[field] for item in items]
    key = f"kp_related_{kind}"
    if st.session_state.get(key) not in ids:
        st.session_state[key] = ids[0]
    labels = {item[field]: f"{'Block' if kind == 'block' else 'Section row'} {start + n:03d} · "
              f"{item.get('Type', '')} · {item.get('Source location', item.get('Source locator', ''))}"
              for n, item in enumerate(items, 1)}
    with st.container(border=True):
        st.subheader("Related items")
        selected = st.selectbox(f"Select {kind} on this page", ids, key=key,
                                format_func=labels.__getitem__)
        result = walk.related_items(**{f"{kind}_id": selected})
        if result["mapping_status"] == "UNAVAILABLE":
            st.info("Block-to-Section mapping unavailable. No relationship is inferred from matching IDs.")
        if not result["rows"]:
            st.info(result["message"])
        unit_labels = {unit["unit_id"]: f"Evidence {n:02d}" for n, unit in enumerate(walk.units, 1)}
        block_labels = {row["Block ID"]: f"Block {n:03d}"
                        for n, row in enumerate(walk.parsed["rows"], 1)}
        display = []
        for row in result["rows"]:
            branches = []
            for uid in row["unit_ids"]:
                siblings = [cid for cid, chunk in walk.chunks.items() if chunk["unit_id"] == uid]
                children = [f"{n:02d}" for n, cid in enumerate(siblings, 1) if cid in row["chunk_ids"]]
                branches.append(f"{unit_labels[uid]} → Chunks {', '.join(children)}" if children
                                else f"{unit_labels[uid]} → No saved chunks")
            display.append({"Section": f"Section {row['section_number']:03d}" if row["section_number"]
                            else "Section (mapping unavailable)",
                            "Source blocks": ", ".join(block_labels.get(bid, "Block (mapping unavailable)")
                                                       for bid in row["block_ids"]) or "Mapping unavailable",
                            "Status": row["status"], "Evidence → Chunks": "; ".join(branches) or "None",
                            "Recorded reason / relationship": row["reason"]})
        if display:
            st.dataframe(display, hide_index=True, width="stretch")
        st.caption("Chunk numbers are within each evidence unit. These are saved parent relationships; "
                   "they do not establish that every linked Section appears in every chunk.")
        with st.expander("Technical details — related item IDs"):
            st.json({"selected": selected, **result})


def parse_blocks(walk, _uid):
    parser = walk.profile["parser"]
    parsed = walk.parsed
    st.subheader("Extracted blocks, before evidence admission")
    st.write(f"Recorded parser: {parser['recorded_adapter']} · {parser['adapter_version']}")
    st.caption("Parsing extracts text and structural elements with source locations. "
               "A parsed block is not an evidence unit, a retrieval chunk or a QA approval.")
    if parsed["status"] == "UNAVAILABLE":
        st.info("Recorded block metadata is unavailable. No extraction is rerun.")
        return
    with st.container(border=True):
        st.subheader("Extraction summary")
        a, b = st.columns(2)
        a.metric("Parsed blocks", parsed["total"])
        b.metric("Canonical Sections downstream", walk.document["counts"]["sections"])
        st.caption("Block and Section counts can differ because normalization organizes source structure. "
                   "No one-to-one mapping is inferred from these totals.")
        st.dataframe([{"Extracted type": kind, "Blocks": count} for kind, count in parsed["types"].items()],
                     hide_index=True, width="stretch")
    with st.expander("Inspect parsed blocks", expanded=False):
        with st.container(border=True):
            st.subheader("Parsed blocks")
            st.caption("Each row describes one saved block. This table shows up to 25 records at a time; "
                       "the record-page number is not a PDF page number; it is also not a source line or DOM position.")
            start = record_pagination(len(parsed["rows"]), "kp_block_page")
            st.dataframe(parsed["rows"][start:start + 25], hide_index=True, width="stretch")
        related_items(walk, parsed["rows"][start:start + 25], kind="block", start=start)
        st.caption("Metadata only: raw parsed text, including unverified content, is not displayed. "
                   "Authorized text is available through QA & Verified Evidence.")

    with st.expander("Technical provenance — parser"):
        st.json(parser)
        st.json({"artifact": parsed["path"], "sha256": parsed["sha256"], "status": parsed["status"]})


def normalized_sections(walk, _uid):
    st.subheader("Canonical Sections, before chunk preparation")
    st.caption("Normalization gives extracted material consistent Section identities, structural types "
               "and source mappings. It does not independently authorize evidence use.")
    st.metric("Canonical Sections", walk.document["counts"]["sections"])
    st.dataframe([{"Recorded Section type": k, "Sections": v}
                  for k, v in walk.profile["structural_types"].items()], hide_index=True)
    st.caption("Disposition below comes from the later QA publication; it is shown for traceability, "
               "not as a decision made by normalization.")
    with st.expander("Inspect canonical Sections", expanded=False):
        status = st.selectbox("Section disposition", ["All", "ADMITTED", "HOLD", "EXCLUDED"],
                              key="kp_section_status", on_change=reset_section_page,
                              persist_state="session")
        rows = walk.data.sections(walk.document["document_id"], status=None if status == "All" else status,
                                  offset=0, limit=25)
        start = record_pagination(rows["total"], "kp_section_page")
        if start:
            rows = walk.data.sections(walk.document["document_id"], status=None if status == "All" else status,
                                      offset=start, limit=25)
        st.caption(f"{rows['total']} matching sections · metadata only")
        st.dataframe(rows["items"], hide_index=True, width="stretch")
        related_items(walk, rows["items"], kind="section", start=start)

    with st.expander("Technical details — normalization and source mappings"):
        st.caption("Structural types come from the bound normalized Section records. The public catalog "
                   "preserves canonical IDs, source locations and published membership relationships.")
        st.json({"type_counts": walk.profile["structural_types"],
                 "locator_coverage": walk.profile["locator_coverage"]})


def qa_evidence(walk, uid):
    st.subheader("From source structure to authorized evidence")
    st.write("QA establishes which source scope is eligible, what remains on HOLD or excluded, "
             "and which context, citations and qualifications must accompany the evidence.")
    st.caption("QA and evidence-unit formation follow the native format-specific contracts. "
               "This does not certify that every publisher claim is factually true.")
    counts = walk.document["counts"]
    for column, (label, value) in zip(st.columns(4), [("Admitted Sections", counts["ADMITTED"]),
            ("HOLD Sections", counts.get("HOLD", 0)), ("Excluded Sections", counts.get("EXCLUDED", 0)),
            ("Verified evidence units", len(walk.units))]):
        column.metric(label, value)
    st.info("Admitted: usable within its approved scope. HOLD: withheld pending verification. "
            "Excluded: intentionally outside eligible evidence. A raw Section is not automatically "
            "an independent consumption unit.")
    if walk.document["format"] == "markdown":
        st.info("Markdown/MDX units retain their published provider, tab, code and source-use "
                "qualifications. Admission can be limited to a specific scope; it does not mean "
                "that a code example was executed or independently verified to work.")
    if walk.document["format"] == "html":
        st.info("HTML evidence uses the current published QA scope and retained source qualifications. "
                "DOM structure, captions and code remain reference data; scripts and remote assets "
                "are not executed or loaded by this view.")
    with st.expander("Inspect evidence unit", expanded=False):
        ids = [u["unit_id"] for u in walk.units]
        labels = {u["unit_id"]: f"Evidence {n:02d} · {locator_label(u['citation_locators'])}"
                  for n, u in enumerate(walk.units, 1)}
        uid = st.selectbox("Choose evidence unit", ids, key="kp_unit", format_func=labels.__getitem__,
                           index=ids.index(uid), persist_state="session")
        st.subheader("How Sections form the selected evidence unit")
        st.dataframe(walk.data.relationships(uid), hide_index=True, width="stretch")
        st.caption("The table shows which Sections supply the main evidence, headings and background "
                   "needed to understand this unit. A Section can contribute to more than one unit; "
                   "a heading or background passage is not stand-alone evidence.")
        st.caption("Later, approved evidence is prepared for search as smaller chunks, while keeping "
                   "its connection to the complete source and any required context or qualifications.")
        evidence(walk, uid)


def parsing(walk, uid):
    # Historical combined route retained; direct overview links now open the exact stage.
    parsed, normalized, qa = st.tabs(["Parse", "Normalize", "QA & Verified Evidence"])
    with parsed:
        parse_blocks(walk, uid)
    with normalized:
        normalized_sections(walk, uid)
    with qa:
        qa_evidence(walk, uid)


def document_preparation_summary(walk, title):
    """Selected-document handoff using the existing verified inventories."""
    with st.container(border=True, key="kp-document-summary"):
        st.subheader("Document preparation summary")
        st.caption(f"{walk.document['document_id']} · Selected document totals")
        st.markdown(f"**{len(walk.units):,} evidence units** → **{len(walk.chunks):,} chunks** → "
                    f"**{len(walk.embeddings):,} saved embeddings** → "
                    f"**{len(walk.indexes['Vector index']['records']):,} vector-index records** + "
                    f"**{len(walk.indexes['BM25 index']['records']):,} BM25 records**")
        st.caption("Counts reflect verified saved exports. BM25 indexes chunk text separately; "
                   "current index database health is not checked here.")
        target = "Embeddings & Indexes" if title == "Chunks & Lineage" else "Chunks & Lineage"
        label = "View Embeddings & Indexes →" if title == "Chunks & Lineage" else "← Back to Chunks & Lineage"
        st.page_link(st.session_state["kp_pages"][target], label=label)


def chunking_policy(library):
    """Full-corpus metadata from the existing validated catalog, not PDF-only totals."""
    catalog = library.catalog
    configs = catalog.manifest["configurations"]
    default = configs[catalog.manifest["default_configuration_id"]]["total_tokens"]
    maximum = max(config["total_tokens"] for config in configs.values())
    overlaps = {config.get("overlap", config.get("chunk_overlap")) for config in configs.values()}
    overlap = next(iter(overlaps)) if len(overlaps) == 1 else "Varies by saved configuration"
    st.markdown(f"**Default limit:** {default} BGE tokens · **Approved exceptions:** up to {maximum} "
                f"· **Overlap:** {overlap if overlap is not None else 'Unavailable'}")
    st.caption("Limits include headings and special tokens. Larger limits apply only to approved "
               "content that needs to remain intact; overlap does not increase for those exceptions.")
    st.info("**Why this limit?** We compared 256 and 384 tokens on our first PDF (C01). "
            "The 384-token limit kept more evidence units intact and produced fewer chunks, "
            "so we chose it as a practical default. BGE's configured maximum is 512 tokens; "
            "approved exceptions use that extra room to keep specific content intact. "
            "This was an engineering choice, not proof that 384 gives the best search results.")
    larger, offset = [], 0
    while True:
        page = catalog.list_chunks(offset=offset, limit=1000)
        larger.extend(row for row in page["items"] if row["token_count"] > default)
        offset += len(page["items"])
        if offset >= page["total"]:
            break
        if not page["items"]:
            raise ValueError("incomplete_chunk_policy_inventory")
    documents = {d["document_id"]: d for d in library.data.corpus.catalog.list_documents()}
    st.markdown(f"Across the **full corpus**, there are **{len(larger)} chunks above the usual "
                f"{default}-token limit**:")
    source_label = "PDF" if {d["format"] for d in library.documents} == {"pdf"} else "source"
    st.caption(f"All published formats · {page['total']:,} saved chunks · This table covers the full "
               f"corpus and is independent of the {source_label} selected below.")
    rows = []
    for did in sorted({row["document_id"] for row in larger}):
        chunks = [row for row in larger if row["document_id"] == did]
        rows.append({"Document": f"{did} · {documents[did]['source']['title']}",
                     "Larger chunks": len(chunks),
                     "Actual BGE tokens": ", ".join(str(n) for n in sorted(
                         [row["token_count"] for row in chunks], reverse=True)),
                     "Approved limit": ", ".join(str(n) for n in sorted({
                         configs[row["configuration_id"]]["total_tokens"] for row in chunks}))})
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")


def chunks(walk, uid):
    st.caption("Already verified evidence → common preparation contract → retrieval chunks and lineage")
    with st.expander("Technical details — How evidence becomes searchable chunks"):
        st.dataframe([
            {"Step": "Input contract", "Responsibility": "Define ChunkInput and preservation/validation rules; no parsing, QA or splitting."},
            {"Step": "Evidence preparation", "Responsibility": "Represent/profile already verified units through the live gateway; no splitting yet."},
            {"Step": "Structure-aware chunking", "Responsibility": "Create model-token-budgeted retrieval representations from eligible source content."},
            {"Step": "Chunk catalog & lineage", "Responsibility": "Publish chunk identities and parent/Section/source lineage."},
        ], hide_index=True, width="stretch")
        st.caption("This dashboard reads existing saved artifacts; opening it does not rerun a processing step.")
    st.markdown("**Structure-aware chunking with parent–child lineage** makes evidence searchable while "
                "preserving its structure and source relationships. Smaller chunks respect document "
                "boundaries and support retrieval; each links back to its complete parent evidence unit, "
                "where context, citations and qualifications remain available for interpretation and citation.")
    with st.expander("Inspect individual records", expanded=False):
        uid = select_evidence_unit(walk, uid)
        cid = selected_chunk(walk, uid)
        if not cid:
            return
        view = walk.chunk(cid)
        row = view["chunk"]
        section_links = walk.catalog.get_chunk_sections(cid)
        siblings = [key for key, chunk in walk.chunks.items() if chunk["unit_id"] == uid]
        with st.container(border=True, key="kp-chunk-relationships"):
            st.subheader("Source relationships")
            st.caption("Sections → Evidence unit → Retrieval chunk → Original source")
            sections, parent, child, source = st.columns(4)
            sections.markdown("**Sections**")
            sections.write(f"{len({edge['section_id'] for edge in section_links})} linked to this parent")
            parent.markdown("**Evidence unit**")
            parent.write(f"Evidence {next(n for n, unit in enumerate(walk.units, 1) if unit['unit_id'] == uid):02d}")
            parent.caption("Complete parent and required context")
            child.markdown("**Retrieval chunk**")
            child.write(f"Chunk {siblings.index(cid) + 1:02d} of {len(siblings)} for this parent")
            source.markdown("**Original source**")
            source.write(f"{walk.document['document_id']} · {walk.document['format'].upper()}")
            source.caption(locator_label(view["verified_parent"]["citation_locators"]))
            st.caption("This shows saved connections, not processing order. Linked Sections belong to the "
                       "complete parent, including its headings or supporting context; "
                       "not every Section necessarily appears in the selected chunk.")
        with st.container(key="kp-chunk-metrics"):
            a, b, c = st.columns(3)
            a.metric("BGE tokens", row["token_count"], border=True)
            b.metric("Source characters", row["source"]["end"] - row["source"]["start"], border=True)
            c.metric("Saved embedding", "Present" if cid in walk.embeddings else "Unavailable", border=True)
        st.caption("BGE token counts describe the saved retrieval representation, not generator usage.")
        st.subheader("Complete parent and source obligations")
        evidence(walk, uid, value=view["verified_parent"])
        st.subheader("Selected search slice")
        st.info("Search representation only. It must not be cited without its complete authorized parent.")
        st.text(view["source_slice"])
        st.dataframe(section_links, hide_index=True, width="stretch")
        with st.expander("Technical details — chunk lineage"):
            st.json({"chunk_id": cid, "unit_id": uid, "source": row["source"],
                     "lineage": row["lineage"], "parent_binding": row["parent_binding"],
                     "configuration": row["configuration_id"], "heading_context": view["heading_context"]})



def embeddings(walk, uid):
    st.write("A saved embedding represents a chunk numerically. Indexes use that representation to locate it.")
    with st.container(key="kp-embedding-metrics"):
        a, b, c = st.columns(3)
        a.metric("Document embeddings", len(walk.embeddings), border=True)
        b.metric("Dimensions", walk.model["dimensions"], border=True)
        c.metric("Data type", "float32", border=True)
    st.caption("One saved embedding per retrieval chunk in the selected source. "
               "Dimensions describe vector size, not token count.")
    st.write(walk.model["model"])
    st.caption(f"Pooling: {walk.model['pooling']} · Normalization: {walk.model['normalization']}")
    st.info("Hash-bound saved metadata only. No model is loaded, no vectors are generated and no index "
            "database is opened. This does not establish retrieval quality or current database health.")
    st.dataframe([{"Index": label, "Document export records": len(index["records"]),
                   "Binding status": index["status"]} for label, index in walk.indexes.items()],
                 hide_index=True, width="stretch")
    with st.expander("Inspect individual records", expanded=False):
        st.caption("Choose an evidence unit, then one of its chunks to inspect saved bindings. "
                   "Document totals and model settings above stay the same.")
        uid = select_evidence_unit(walk, uid)
        cid = selected_chunk(walk, uid)
        if cid:
            st.subheader("This chunk across the saved artifacts")
            st.dataframe([{"Stage": label, "Binding": value} for label, value in [
                ("Chunk catalog", "Present"), ("Embedding record", "Present"),
                ("Vector index export", "Present"), ("BM25 index export", "Present")]], hide_index=True)
            with st.expander("Technical details — exact embedding and index bindings"):
                st.json(walk.embeddings[cid])
                st.json({label: index["records"][cid] for label, index in walk.indexes.items()})


def withheld_section_rows(walk):
    """Read published metadata only; retain recorded reasons without inferring QA decisions."""
    rows = []
    did = walk.document["document_id"]
    for status in ("HOLD", "EXCLUDED"):
        offset = 0
        expected = walk.document["counts"].get(status, 0)
        while True:
            page = walk.data.sections(did, status=status, offset=offset, limit=100)
            if page["total"] != expected or any(r["Status"] != status for r in page["items"]):
                raise ValueError("withheld_section_count_mismatch")
            rows.extend(page["items"])
            offset += len(page["items"])
            if offset == expected:
                break
            if not page["items"] or offset > expected:
                raise ValueError("incomplete_withheld_section_inventory")
    if len({r["Section ID"] for r in rows}) != len(rows):
        raise ValueError("duplicate_withheld_section")
    return rows


def recorded_reason(row):
    value = row.get("Issue / reason")
    return value if value and value != "—" else "Reason not recorded."


def reset_withheld_page():
    st.session_state["kp_withheld_page"] = 1


def section_outcomes(walk):
    counts = walk.document["counts"]
    if counts["sections"] != sum(counts.get(s, 0) for s in ("ADMITTED", "HOLD", "EXCLUDED")):
        raise ValueError("section_outcome_count_mismatch")
    rows = withheld_section_rows(walk)
    with st.container(border=True):
        st.subheader("Section outcomes")
        st.markdown(f"**{counts['sections']:,} canonical Sections** → "
                    f"**{counts.get('ADMITTED', 0):,} admitted** · **{counts.get('HOLD', 0):,} HOLD** · "
                    f"**{counts.get('EXCLUDED', 0):,} excluded**")
        st.caption("Admitted Sections are authorized within their approved scope. HOLD Sections remain "
                   "withheld; excluded Sections are outside eligible evidence. These are saved QA "
                   "decisions, not new checks or factual certification.")
        st.markdown("**Why Sections were withheld or excluded**")
        reasons = Counter((r["Status"], recorded_reason(r)) for r in rows)
        if reasons:
            st.dataframe([{"Status": status, "Sections": count, "Recorded QA reason": reason}
                          for (status, reason), count in sorted(reasons.items())],
                         hide_index=True, width="stretch")
        else:
            st.caption("No HOLD or excluded Sections recorded for this source.")
        st.caption("Each Section is counted once under its recorded reason; no missing reason is inferred.")
    with st.expander("Inspect withheld Sections", expanded=False):
        status = st.selectbox("Withheld Section status", ["All", "HOLD", "EXCLUDED"],
                              key="kp_withheld_status", on_change=reset_withheld_page,
                              persist_state="session")
        matching = [r for r in rows if status == "All" or r["Status"] == status]
        start = record_pagination(len(matching), "kp_withheld_page")
        selected = matching[start:start + 25]
        st.dataframe([{"Section": f"Withheld record {start + n:03d}",
                       "Source location": r["Source locator"], "Type": r["Type"],
                       "Status": r["Status"], "Recorded reason": recorded_reason(r)}
                      for n, r in enumerate(selected, 1)], hide_index=True, width="stretch")
        st.caption("Metadata only. Withheld source text is not displayed or admitted by this view.")
        st.page_link(st.session_state["kp_pages"]["QA & Verified Evidence"],
                     label="Open QA & Verified Evidence →")
        with st.expander("Technical details — withheld Section IDs"):
            st.json([{"record": start + n, "section_id": r["Section ID"]}
                     for n, r in enumerate(selected, 1)])


def validation(walk, uid):
    section_outcomes(walk)
    st.success("Selected source, native publication and saved derivative bindings verified.")
    st.caption("This is integrity/lineage verification, not factual correctness or answer-quality certification.")
    st.dataframe([{"Check": label, "Outcome": outcome} for label, outcome in [
        ("Frozen source identity", "HASH_VERIFIED"),
        ("Chunk ↔ parent lineage", "VERIFIED_CATALOG"),
        ("Embedding artifact bytes", "HASH_VERIFIED"),
        ("Vector / BM25 export coverage", "HASH_VERIFIED_SAVED_EXPORT"),
        ("Index database health", "NOT_RUN"), ("Automatic refresh", "NOT_CONFIGURED")]],
        hide_index=True, width="stretch")
    st.subheader("Versioned publication chain")
    st.write("Frozen source → QA-authorized evidence → Retrieval chunks → Saved embeddings & search indexes")
    st.caption("QA publishes authorized evidence before chunk preparation. Chunk catalogs, embeddings and "
               "indexes have their own versioned publications. This final view verifies their composed "
               "bindings; it is not the only place validation or publication happens.")
    st.caption("Vector indexes use saved embeddings; BM25 indexes chunk text separately. "
               "Publication means a saved, versioned local artifact—not publishing online.")
    with st.expander("Inspect evidence validation", expanded=False):
        uid = select_evidence_unit(walk, uid)
        walk.unit(uid)  # Native public validation; no content or receipt is persisted.
        st.success("Selected evidence parent: NATIVE_VALIDATED")
    with st.expander("Technical details — publication receipts"):
        st.json(walk.receipts())


RENDERERS = {"Knowledge Preparation": overview, "Sources": sources,
             "Parsing & Evidence": parsing, "Chunks & Lineage": chunks,
             "Embeddings & Indexes": embeddings, "Validation & Publications": validation,
             "Parse": parse_blocks, "Normalize": normalized_sections,
             "QA & Verified Evidence": qa_evidence}


def stage_context(title):
    stage = STAGE_BY_PAGE.get(title)
    if not stage:
        return
    with st.container(border=True):
        st.caption(f"Current process stage · {stage['title']}")
        a, b = st.columns(2)
        a.markdown("**Input**")
        a.write(stage["input"])
        b.markdown("**Output**")
        b.write(stage["output"])
        st.caption(stage["detail"])


def stage_navigation(title):
    stage = STAGE_BY_PAGE.get(title)
    if not stage:
        return
    position = STAGES.index(stage)
    previous, following = st.columns(2)
    if position:
        target = STAGES[position - 1]
        with previous:
            st.page_link(st.session_state["kp_pages"][target["page"]], label=f"← {target['title']}")
    if position < len(STAGES) - 1:
        target = STAGES[position + 1]
        with following:
            label = f"Next: {target['title']} →" if title in {"Sources", "Parse"} else f"{target['title']} →"
            st.page_link(st.session_state["kp_pages"][target["page"]], label=label)


def render(title):
    try:
        with st.spinner("Verifying saved source and publication bindings…"):
            library = load()
            library.check()
        if title == "Knowledge Preparation":
            overview(library, None)
            library.check()
            return
        st.title(title)
        st.write(f"Focus: {FOCUS[title]}")
        technical_backbone(title, library)
        if title == "Chunks & Lineage":
            chunking_policy(library)
        document_ids = [d["document_id"] for d in library.documents]
        names = {d["document_id"]: d["source"]["title"] for d in library.documents}
        if st.session_state.get("kp_selected_document") not in document_ids:
            st.session_state["kp_selected_document"] = document_ids[0]
        current = st.session_state["kp_selected_document"]
        st.session_state["kp_document"] = current
        source_label = "Selected PDF source" if {d["format"] for d in library.documents} == {"pdf"} else "Selected source"
        did = st.selectbox(source_label, document_ids, key="kp_document",
                           index=None, on_change=document_changed,
                           format_func=lambda value: f"{value} · {names[value]}", persist_state="session")
        walk = library.for_document(did)
        if title in {"Chunks & Lineage", "Embeddings & Indexes"}:
            document_preparation_summary(walk, title)
        detail = did if title == "Sources" else f"{did} · {names[did]}"
        st.caption(f"{detail} · Document detail · Existing verified artifacts")
        st.page_link(st.session_state["kp_pages"]["Knowledge Preparation"], label="← Knowledge Preparation overview")
        # Reset all subordinate selections when the document changes, before rendering widgets.
        if st.session_state.get("kp_active_document") != did:
            for key in ["kp_unit", "kp_chunk", "kp_selected_chunk", "kp_withheld_page", "kp_withheld_status", "kp_section_page", "kp_section_status", "kp_block_page"]:
                st.session_state.pop(key, None)
            st.session_state["kp_active_document"] = did
        ids = [u["unit_id"] for u in walk.units]
        uid = None
        needs_evidence = title not in {"Sources", "Parse", "Normalize"}
        if ids:
            if st.session_state.get("kp_unit") not in ids:
                st.session_state["kp_unit"] = ids[0]
            uid = st.session_state["kp_unit"]
        elif needs_evidence:
            st.info("No authorized evidence units are recorded for this source. Source metadata remains available.")
            return
        stage_context(title)
        RENDERERS[title](walk, uid)
        stage_navigation(title)
        walk.check()
    except (ValueError, OSError, KeyError, TypeError):
        st.error("Preparation walkthrough unavailable: an artifact or live source binding failed validation. "
                 "No unverified source content is substituted. Restart the preview after resolving the binding.")
