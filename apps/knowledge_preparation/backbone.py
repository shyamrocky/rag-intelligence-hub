"""Presentation-only engineering notes over the existing verified preparation snapshot."""

import streamlit as st

# Implementation descriptions, not a second source of artifact measurements.
LAYERS = {
    "Sources": [
        ("Frozen snapshots + source registry", "Keep the original local source, acquisition record and source-use permissions.",
         "Source identity and acquisition metadata", "SHA-256 fingerprints and publication bindings"),
    ],
    "Parse": [
        ("PyMuPDF + recorded PDF adapter", "Extract text/layout blocks and retain page locations; extraction does not authorize evidence.",
         "Parsed block records and parser provenance", "Bound parser artifacts and original PDF identity"),
    ],
    "Normalize": [
        ("Python normalization + Pydantic Section contracts", "Organize extracted blocks into canonical Sections with stable identities and source mappings.",
         "Canonical Section records", "Schema, source fingerprints and recorded block-to-Section links"),
    ],
    "QA & Verified Evidence": [
        ("Native format-specific QA + unified evidence contracts", "Read approved scope, HOLD/exclusion decisions and published parent memberships; retain context and qualifications.",
         "Authorized evidence units and recorded QA decisions", "Native source validation and publication-bound memberships; not factual certification"),
    ],
    "Chunks & Lineage": [
        ("Structure-aware Python chunking + pinned BGE tokenizer", "Prepare searchable children while preserving parent, Section and source relationships.",
         "Chunk catalog, token counts and lineage", "Bound input spans, tokenizer configuration and parent/source identities"),
    ],
    "Embeddings & Indexes": [
        ("Sentence Transformers + BGE", "Represent each prepared chunk as a dense semantic vector.",
         "Saved embedding records and vectors", "Model/input fingerprints, chunk identity and saved vector bindings"),
        ("Persistent ChromaDB", "Store vectors for dense similarity search.",
         "Vector-index publication and export records", "Hash-bound saved export coverage; this view does not open the database"),
        ("rank_bm25 · BM25Okapi", "Index chunk text separately for lexical keyword matching; BM25 does not consume BGE vectors.",
         "BM25 index publication and text records", "Chunk text fingerprints, configuration and saved export coverage"),
    ],
    "Validation & Publications": [
        ("BoundFiles + native evidence/catalog validators", "Check saved source, evidence, chunk and derivative identities; fail closed when bindings change.",
         "Integrity outcomes and versioned local manifests", "SHA-256 hashes, schema/contract checks and lineage/coverage reconciliation"),
    ],
}


def technical_backbone(title, library):
    stages = ("Parse", "Normalize", "QA & Verified Evidence") if title == "Parsing & Evidence" else (title,)
    with st.expander("Technical backbone", expanded=False):
        st.caption("How this stage was built. This dashboard inspects saved artifacts; opening this "
                   "section does not execute parsing, QA, embedding, indexing or retrieval.")
        rows = [
            {"Stage": stage, "Technology": tech, "What it does": purpose,
             "Saved output": output, "Verification": verification}
            for stage in stages for tech, purpose, output, verification in LAYERS[stage]
        ]
        if "Parse" in stages and any(d["format"] == "markdown" for d in library.documents):
            rows.append({"Stage": "Parse", "Technology": "markdown-it-py + bounded MDX parser",
                         "What it does": "Preserve Markdown lines, fenced code and supported tab/provider boundaries; never execute code or MDX.",
                         "Saved output": "Markdown block records and source spans",
                         "Verification": "Bound snapshot identity and recorded block/parser metadata"})
        if "Parse" in stages and any(d["format"] == "html" for d in library.documents):
            rows.append({"Stage": "Parse", "Technology": "Python HTMLParser + semantic HTML adapter",
                         "What it does": "Read frozen HTML structure and preserve DOM/source locations; no browser, JavaScript or remote assets are executed.",
                         "Saved output": "HTML block records, classifications and DOM mappings",
                         "Verification": "Bound parser records and original source identity"})
        st.dataframe(rows, hide_index=True, width="stretch")
        if "Parse" in stages:
            st.markdown("**Recorded parser provenance — connected sources**")
            st.dataframe([
                {"Source": did, "Adapter": profile["parser"]["recorded_adapter"],
                 "Adapter version": profile["parser"]["adapter_version"]}
                for did, profile in sorted(library.profiles.items())
            ], hide_index=True, width="stretch")
            st.caption("These are saved adapter versions. Where recorded, parser dependencies and "
                       "observed block-parser versions remain in Technical provenance — parser below.")
        if title == "Chunks & Lineage":
            catalog = library.catalog
            configs = catalog.manifest["configurations"]
            default = configs[catalog.manifest["default_configuration_id"]]["total_tokens"]
            maximum = max(c["total_tokens"] for c in configs.values())
            st.caption(f"Saved policy: {default} BGE-token default; approved limits up to {maximum}. "
                       "Overlap and larger-chunk exceptions are detailed below. Token counts include "
                       "headings/special tokens; they are not generator usage.")
        if title == "Embeddings & Indexes":
            model = library.model
            st.caption(f"Saved model: {model['model']} · {model['dimensions']} dimensions · "
                       f"{model['pooling']} pooling · {model['normalization']} normalization.")
            st.info("This prepares two search paths: dense BGE/ChromaDB and lexical BM25. "
                    "Hybrid retrieval later combines their ranked results using RRF; preparation "
                    "does not fuse rankings or create a hybrid embedding.")
        if title == "Validation & Publications":
            st.caption("Publication means a versioned local artifact, not an online release. "
                       "Integrity checks do not certify factual correctness, current index database "
                       "health or retrieval/answer quality.")
