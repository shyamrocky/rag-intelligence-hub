# M3 retrieval chunk catalog and lineage

**OWNER_ACCEPTED / CLOSED — October 23, 2026 (D029).** Both accepted M2 configurations remain unchanged. The final explicit M3 catalog has **992 chunks representing all 553 verified units across 16 documents**, with zero unresolved admitted-source chunking intervals. Authorized source-display emission is 99.98%; parent-only context and the 358 source QA HOLD Sections retain their restrictions. This is not whole-source fidelity or retrieval-quality performance.

Accepted selector: `config/retrieval-chunks-m3-c14-scope-v2.json`. Manifest SHA-256: `f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c`. Use the explicit unified selection in [the M4 handoff](M3_TO_M4_HANDOFF.md). The original default corpus/dashboard/catalog selectors are unchanged.

The default is **384 total BGE tokens**, including source-backed headings and special tokens. Four indivisible qualified inputs use selective 512 limits: C14 bibliography 385, C06 prompt 474, and C16 examples 485/507 actual tokens. Maximum actual input is 507. No truncation, removed source headings or unapproved generic budget increase is allowed.

## Ownership and interfaces

`rag_hub.retrieval_chunks.RetrievalChunk` is the additive, versioned derived schema, also exported as [JSON Schema](schemas/retrieval-chunk-1.0.schema.json). `rag_hub.chunk_catalog.ChunkCatalog` reads a fingerprinted explicit selector and reuses `ChunkPreparation` and the accepted unified gateway. It never runs QA, reparses documents, reconstructs unauthorized source text or grants eligibility.

The catalog stores **references**, exact display intervals/hashes, source-span precision, publication-qualified parent bindings and diagnostics. It does not flatten source text, QA observations and restrictions into one field. Mandatory context, qualifications, citations, publication identity and current expiration warnings resolve from the original complete verified parent. Context-only Sections remain context-only. Membership in a parent does not imply that every child contains every parent Section's text.

The earlier scaffold `schemas.Chunk` assumes a detached text payload and an `index_status` field; it cannot express these publication-qualified, complete-parent obligations. It remains unchanged. M3 reuses the accepted preparation, source-mapping and tokenization components and adds the narrower derived `RetrievalChunk` rather than migrating ingestion schemas or creating another eligibility status.

IDs are `rc:retrieval-chunk-1.0:<sha256>` over the canonical complete row excluding the ID itself. The row binds the publication-qualified Unit ID, configuration ID, exact display slice, source hash, lineage and diagnostics. The configuration binds tokenizer revision/assets, actual total budget and implementation fingerprints. Changes create new IDs. Clock-derived expiration warnings are resolved live rather than changing immutable chunk identity.

The reader verifies selector/manifest/file/component hashes and the upstream binding set, rejects duplicate/orphan identities and conflicting parent bindings, and holds filesystem leases. `open_chunk` re-resolves the exact source field and interval through the live gateway, checks hashes and lineage, and returns an **inspection slice plus the unchanged complete verified parent**. It is not the future M8 retrieval-evidence reconstruction service. `validate_view` rejects modified, stale, warning-stripped or context-stripped views.

```python
from pathlib import Path
from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

root = Path.cwd()
corpus = load_c14_verified_corpus(root)
catalog = QualifiedChunkCatalog(
    root, corpus, selector="config/retrieval-chunks-m3-c14-scope-v2.json"
)
rows = catalog.list_chunks(document_id="C01", offset=0, limit=25)
cid = rows["items"][0]["chunk_id"]
view = catalog.open_chunk(cid)
catalog.validate_view(view)
catalog.get_unit_chunks(view["chunk"]["unit_id"])
catalog.get_chunk_sections(cid)
catalog.get_section_chunks(catalog.get_chunk_sections(cid)[0]["section_id"])
```

For HOLD/excluded Sections, reverse lookup returns no authorized chunk relationships. Their inspection metadata remains available from the original unified catalog. Many-to-many relationships are preserved without duplicating canonical Section counts.

## Precision and coverage

Where existing native source-member hashes and display assembly match, the M2 mapping supplies exact original slices. Otherwise the exact **approved display** interval and parent citations remain authoritative; no finer raw offsets are guessed. Synthetic display newlines are explicitly accounted. C01 affiliation-star WordPiece unknowns retain the original source characters and diagnostics.

Coverage is a partition of each approved indexable source field into chunks or explicitly unresolved intervals. Shared parent memberships and repeated context are reported separately; summing per-unit display lengths is not unique whole-source character coverage. Protected warning-bearing projections are not stripped or converted to independently indexable text.

The Streamlit **Chunk Inspector** is an additive view in the existing application. It uses the same cached live verified corpus and a leased read-only catalog. Widget interactions do not execute the chunker. Source strings render as literal text; raw/audit-only fallback is prohibited. Existing ingestion views retain their APIs and QA status semantics.

## Full-corpus extension boundary

`CorpusChunker` delegates C01 unchanged to M2. For the other sources it reuses M2's heading/source-span helpers and lossless LangChain sentence/whitespace policy. Native paragraph/prose classifications may split; code, tables, formulas, captions, figure-text and lists remain atomic. Oversized atomic elements become explicit unresolved intervals. Bibliography boundaries require source witnesses: numbered markers for the original C01 path, and the published 47-entry hanging-indent/geometry map for C14. C14's bibliography remains attribution-only; Appendices A/B/C have separate substantive ILLUSTRATIVE scopes and required source headings. No graph interpretation is inferred. Missing witnesses cause abstention. Context headings and unknown structures are not forced into independent chunks.

The four native warning-bearing Markdown parents have approved primary source quotation search representations through `QualifiedPreparation`; mandatory context, score-output quotations, source-defect warnings and provider boundaries remain in the complete parent. Raw evidence and excluded claims are not indexed. All prior M3 chunking exceptions are resolved within the accepted source scope, including C06 prompt, C16 TypeScript and C14. This never changes native QA eligibility or creates Section HOLD decisions. See [qualified source policy](QUALIFIED_CHUNKING_POLICY.md).

Construction validates Section metadata in checked public pages, then verifies published parent memberships. This avoids repeating a full filesystem lease check for every edge. Evidence access and subsequent queries still check the original live leases. A first full-corpus development inspector timed out with per-edge Section lookups; its outputs/logs are retained as development evidence. The selected successor uses the paginated construction path.

## Decision and stop boundary

ID: RAG-M3-01. Date: 2026-10-23. Status: OWNER_ACCEPTED / CLOSED under D029; original implementation decision retained. Decision: add a derived, version-qualified catalog and read-only inspector over the accepted gateway, using 384 provisionally and preserving both M2 pilots. Rationale: support navigable lineage without another admission authority. Alternatives: embed whole envelopes, use raw normalized Sections, detach qualifications, or infer finer offsets; rejected because they lose source/QA distinctions or authorization boundaries.

See [original verification](M3_CATALOG_VERIFICATION.md) for the historical initial catalog; final accepted selection and replay obligations are in [C14 reconciliation](C14_QA_SCOPE_RECONCILIATION.md) and [M4 handoff](M3_TO_M4_HANDOFF.md). M4 embeddings, vector/lexical indexes, retrieval and generation require separate authorization.
