# M0–M3 qualified source-search successor

The owner authorized this bounded M3 extension on October 23, 2026. The final qualified/C14 successor is OWNER_ACCEPTED / CLOSED under D029 on October 23, 2026; it remains explicitly selected. The original M0/M1 [preparation contract](CHUNK_PREPARATION_CONTRACT.md), M2 configurations, 954-chunk predecessor, default catalog and ingestion dashboard remain unchanged.

Decision **RAG-M3-Q01**: support source content already admitted by the Unified Verified-Consumption Layer within its published qualifications, including attributed defective or unverified examples. Downstream chunking preserves source content and scope; it does not certify publisher claims or create QA eligibility. Rationale: a qualified example can be useful without being executable or independently reproduced. Alternatives rejected: indexing whole QA envelopes, exposing unrestricted defective code, guessing boundaries, silently increasing every input budget, or changing native QA. Status: owner-accepted engineering direction and results, with the final release pinned by D029.

## Contracts and ownership

`QualifiedPreparation` adds `qualified-search-preparation-1.0` around the unchanged `chunk-input-1.0`. `prepare(unit_id)` and `validate(prepared)` always resolve through the live authoritative gateway. Source quotations, context, QA, qualifications and provenance remain separate.

| Representation | Permitted role |
|---|---|
| `record` | Entire original ChunkInput, unchanged, including protected native renderings and publications. Not embedding text. |
| `search_sources` | Existing explicit source fields, or exact source quotations explicitly enumerated in the verified protected projection. Search-only, always parent-bound. |
| `headings` | Literal required source headings. Nested HTML heading identity comes only from normalized type metadata already bound by the accepted gateway; heading text comes from verified context. |
| `parent_only_projection_segments` | Explicit required-context quotations and attributed score output. Not independent search entries. |
| Native QA observations / qualifications | Preserved in the complete parent. Not embedded as publisher knowledge. |

Protected source quotations retain native Section IDs, source hashes, byte/codepoint spans and published roles. Only the published source quotations are used; raw canonical Sections, omitted metric claims and excluded financial output are never fallback content. Defective publisher code is neither repaired nor certified. Context-only score output and provider installation/selection context remain in the full parent. All four protected parents have primary source search representations; this does not mean every contextual character receives a separate chunk.

`QualifiedChunker.chunk(prepared, source_pointer)` validates preparation before and after splitting. `RetrievalChunk` 1.0 is reused. New configuration identities fingerprint the extension, tokenizer, source fields and authorized scope. Chunk IDs remain publication/configuration/source-interval qualified. The qualified-only predecessor preserved its original 954 rows and IDs. The final accepted C14 publication necessarily remints PDF handle-bound identities while retaining every historical file; 564 HTML/Markdown rows remain exact in the selected release.

## Structural and token rules

384 total BGE tokens remains the default, including literal required headings and CLS/SEP. A selective 512-token ceiling applies only when an indivisible source-supported representation fits. No truncation or omitted heading is allowed.

- Markdown: complete explicit primary quotation segments fit within 384. QA labels/warnings are not source-text embeddings. Required context remains parent-only.
- C06 prompt: the explicit printed `Example:` source-member boundary gives two exact ranges, 192 and 474 tokens. The second preserves the entire quotation, response and final rules. No prompt execution.
- C16: whole 507/485-token examples use selective 512. Larger examples use a conservative lexical map of complete top-level statements. Balanced functions, expressions, objects and templates are indivisible. Regex/slash operators, unsupported interpolation and ambiguous/incomplete syntax fail closed. This narrow splitter is not a TypeScript compiler, new ingestion parser, or executable-code certification. Exposed source declaration maps were frozen before implementation and are machine-prepared, not independently human-adjudicated ground truth.
- C14: the accepted source-bound QA successor separates the 47-entry bibliography from Appendices A/B/C. Bibliography remains attribution-only; appendix narratives are ILLUSTRATIVE with literal source headings and visual limitations. Fourteen additional chunks use the published boundaries; the one 385-token reference uses a selective 512 limit. Canonical extraction/classification history remains immutable.

Older rows retain their original prefixes and metadata to preserve exact replay. Nested C16 headings are included for all new C16 rows; prior prefix evidence is not retroactively rescored. Existing full-parent context remains required for old and new rows.

## Verified reader and later-milestone obligations

Use `QualifiedChunkCatalog`, not a raw JSON reader or raw normalized fallback:

```python
from pathlib import Path
from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

root = Path.cwd()
corpus = load_c14_verified_corpus(root)
catalog = QualifiedChunkCatalog(
    root, corpus, selector="config/retrieval-chunks-m3-c14-scope-v2.json"
)
row = catalog.list_chunks(document_id="C04", limit=1)["items"][0]
view = catalog.open_chunk(row["chunk_id"])
catalog.validate_view(view)
parent = view["verified_parent"]  # Mandatory full native evidence, context and warnings.
```

For successor rows, `search_representation.text` contains only exact source quotation text with required source-heading prefix. Its role is `SEARCH_ONLY_NOT_INDEPENDENT_EVIDENCE`. `source_slice` is an inspection/search slice, not evidence authorization. `open_chunk` rehydrates and validates the entire authoritative parent before returning a view. `validate_view` reconstructs and compares that complete view, rejecting removed warnings, source edits, stripped parents/context, forged publication identities or altered search obligations. The gateway rejects a search representation presented as a verified unit.

M4 must embed only the explicitly bound search input and enforce the per-configuration total budget without truncation. Future ranking/evidence reconstruction must resolve IDs through this reader and use the full authorized consumer projection, including qualifications, provider boundaries, source-defect and metric restrictions, PDF expiration warnings and citations. UI/generation must display mandatory limitations. Catalog fields do not grant independent evidence permission. These are M3 interface obligations and tests, not claims that embeddings, search or answer generation have been implemented or evaluated.

The existing Streamlit dashboard remains on its unchanged catalogs; this delivery does not silently adopt the candidate or change dashboard selection behavior.

## Historical qualified build and accepted final reproduction

The following is the preserved earlier qualified-only build. The accepted final full-corpus rebuild and witness consolidation are documented in [C14 reconciliation](C14_QA_SCOPE_RECONCILIATION.md); use [M4 handoff](M3_TO_M4_HANDOFF.md) for the accepted selectors. Existing local corpus/tokenizer assets are required:

```sh
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false \
  UV_CACHE_DIR=/private/tmp/rag-uv-cache \
  uv run --project tools/chunking --locked python tools/chunking/build_qualified_catalog.py \
  --output data/chunking/m3-qualified-v2
```

The earlier immutable selector is `config/retrieval-chunks-m3-qualified-v2.json`; the accepted final selector is `config/retrieval-chunks-m3-c14-scope-v2.json`. A different replay directory changes manifest path bindings; payloads, configurations, component and upstream hashes must remain identical. Existing outputs are write-once and never overwritten. New builds require a new version if implementation or evidence changes.

Earlier qualified-only reports and the then-deferred C14 issue remain historical under the private milestone workstream `workspace/rag-implementation/v1/m3-qualified-recovery-v1/`. The single M0–M11 tracker is updated there in place. Default selectors, upstream QA, sources, unified public contracts and historical artifacts are unchanged. M4 remains unapproved.
