# M2 — C01 structure-aware chunking pilot

Acceptance update — October 23, 2026: both M2 C01 configurations are owner accepted and preserved. M3 is now owner accepted under D029, with 384 total BGE tokens as its provisional default and four specific selective exceptions up to 512. The original M2-only implementation boundary below is historical. It establishes no embedding or retrieval-quality winner. See [the accepted catalog](RETRIEVAL_CHUNK_CATALOG.md) and [M4 handoff](M3_TO_M4_HANDOFF.md).

The project owner accepted M0/M1 and authorized M2 only. This additive pilot takes complete verified C01 units through the [M0 contract](CHUNK_PREPARATION_CONTRACT.md); it does not change QA, native loaders, normalized records, the unified layer or dashboard. Results require owner review before M3. Existing M0/M1 delivery reports retain their historical pending-review labels; the new owner decision is recorded in the single working milestone tracker and an additive acceptance receipt.

## Components and dependency boundary

- `rag_hub.m2_tokenizer.PinnedBgeTokenizer`: verify pinned local tokenizer/config assets and count without truncation or padding.
- `rag_hub.structure_chunking.StructureAwarePilot`: derive exact display slices and preserve context, qualifications and source bindings.
- `tools/chunking/run_c01.py`: run both configurations, account for source coverage, and write private versioned evidence.
- `tools/chunking/tests/test_structure_chunking.py`: actual-gateway integration and explicitly owned synthetic engineering controls.

`tools/chunking/pyproject.toml` and its lockfile isolate new dependencies. The accepted root and dashboard dependency files/environments are unchanged. Direct pins: `tokenizers==0.22.2`, `langchain-text-splitters==1.1.2`; the lock and tokenizer specification also pin `langchain-core==1.7.0`. Native ingestion dependencies match the existing runtime: PyMuPDF 1.28.2, Pydantic 2.14.1 and markdown-it-py 4.2.0. Transitive packages are locked; no embedding weights, PyTorch, Transformers or Sentence Transformers runtime is needed.

## Tokenizer and effective input budget

The official `BAAI/bge-small-en-v1.5` tokenizer/configuration assets are pinned to repository revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, with individual SHA-256 values in `config/bge-tokenizer-v1.json`. The tokenizer JSON SHA-256 is `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`. Files remain private under `data/tooling/tokenizers/`; downloads were limited to seven tokenizer/configuration/model-card files, totaling 1,038,973 bytes. No model weights were acquired.

The pinned tokenizer configuration, model position configuration and Sentence Transformers configuration all specify a **512-token ceiling**. The actual tokenizer adds **two special tokens**, `[CLS]` and `[SEP]`. See the [official tokenizer configuration](https://huggingface.co/BAAI/bge-small-en-v1.5/blob/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/tokenizer_config.json), [model configuration](https://huggingface.co/BAAI/bge-small-en-v1.5/blob/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/config.json) and [sentence configuration](https://huggingface.co/BAAI/bge-small-en-v1.5/blob/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/sentence_bert_config.json). This qualifies configured token limits, not embedding quality or a model execution benchmark.

The **256 and 384 limits apply to the entire prospective embedding input**, including an explicit source-backed heading prefix, delimiters and special tokens. The initial body allowance is `limit − actual heading tokens − 2`; every emitted complete string is then counted again exactly. No query instruction is prepended to document passages, following the [publisher's document/query distinction](https://huggingface.co/BAAI/bge-small-en-v1.5). No QA commentary, publication JSON or arbitrary envelope metadata enters embedding text.

Only literal `SOURCE_CONTENT` required headings with explicit source bindings enter the optional heading prefix. They remain required context and never become standalone evidence. Other context and all qualifications remain separately bound. The two configurations use zero source overlap, isolating chunk-size effects and allowing exact lossless coverage accounting. Overlap tuning remains future work.

The JSON tokenizer is corroborated against a BERT tokenizer constructed from the separately pinned vocabulary and official configuration, including all 61 C01 source fields and protected-value controls. This is configuration parity using the same tokenizer backend, not an independent model-quality result. Encoding more than 512 tokens is deliberately allowed for measurement; no truncation occurs. Output admission to a pilot chunk requires the configured budget check.

## Boundary behavior

1. Keep an already fitting source unit intact where possible.
2. Retain native table, formula, code and caption elements atomically. Oversized elements become explicit unresolved intervals rather than arbitrary prose splits.
3. For longer section text, prefer existing native source-member boundaries. Their recorded status remains original block boundaries; M2 does not relabel them as independently certified paragraphs.
4. Preserve a leading source member with following prose when naive packing would isolate it; no new heading classification is inferred. For oversized prose atoms, use LangChain recursive sentence/whitespace splitting with the pinned tokenizer as its length function, preserved separators, no whitespace stripping and no overlap. See [LangChain's documented splitter controls](https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter). No character-level fallback splits technical identifiers. Every proposed partition must concatenate byte-for-byte to the original approved display string.
5. Treat bibliography separately: require a declared bibliography, exact hash-verified source-member mappings, consecutive numbered markers and marker alignment with member starts. Pack complete entries within the total budget. Never split an oversized entry into generic prose; retain it as unresolved.

The 68 C01 reference-entry boundaries were recorded before chunker development in the private `BIBLIOGRAPHY_EXPECTATIONS.json`, including display offsets and source spans. They are deterministic source-marker verification, not new independent human approval. Earlier human reference reviews remain separately scoped historical evidence.

## Lineage and qualifications

Each pilot piece retains its publication-qualified Unit ID, preparation/evidence binding, source-field JSON pointer and hash, exact display interval/text/hash, Section roles, citations, publication identity and native qualifications. Tables/formulas retain the whole original authorized projection in the parent preparation. Only the selected exact source slice and the explicit heading prefix form the prospective embedding text.

Two lineage precisions are explicit:

- **Hash-verified display-to-original slices:** exact partial raw offsets are derived only when the native member text hash and approved display assembly match; existing synthetic newline joiners are accounted separately.
- **Authorized display projection with parent citations:** exact display offsets plus original parent source citations; no invented partial raw offset. Whole table/formula projections and some other native views naturally use this representation. Split views with only parent-level raw precision are listed for review.

`proposal_id` values are deterministic pilot fingerprints. They are not M3 RetrievalChunk IDs, index records or a catalog API. A pilot piece never authorizes standalone evidence: future consumers must revalidate and reconstruct the original complete verified unit with its mandatory context and restrictions. `StructureAwarePilot.validate(result)` recomputes through the live gateway; rehashing a forged result does not grant authority.

No native QA observation is rewritten. Separate chunking diagnostics identify tokenizer unknowns and locator precision. Unknown tokens do not replace original source text or silently change source eligibility. PDF expiration stays informational; fresh preparation carries current warnings without modifying M1 artifacts or extending authorization.

## Durable output and replay

The selected final candidate is `m2-structure-aware-1.1`, stored under private `data/chunking/m2-c01-v3/`. Earlier `m2-c01-v1` and `m2-c01-v2` directories are preserved development candidates and are not the review baseline. The final directory contains:

- `prepared-inputs.jsonl`: fresh gateway preparation, including current warning state.
- `config-256/unit-results.jsonl` and `config-384/unit-results.jsonl`: results for all 61 units per configuration, including explicit unresolved intervals.
- `C01_BGE_TOKEN_PROFILE.json`: actual BGE unit-length statistics.
- `C01_CHUNKING_COMPARISON.json`: counts, distributions, coverage, boundary decisions and lineage precision.
- `REVIEW_CASES.json`: non-authoritative diagnostic review cases.
- `C01_CHUNKING_REVIEW.html`: self-contained inspection preview with both configurations.
- `manifest.json`: component, output, tokenizer and original loaded-snapshot fingerprints.

From the repository root, with the existing private frozen corpus and acquired pinned tokenizer assets present:

```sh
uv sync --project tools/chunking --locked
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false \
  uv run --project tools/chunking --locked python tools/chunking/run_c01.py
```

Output writes are append-only: identical replay is accepted; differing output at an existing path fails. Use `--output data/chunking/m2-c01-replay-v3` for a separate replay. Runtime/resource measurements go to standard output; deterministic manifests contain no run timestamp. The runner blocks socket connections during execution and records that no embedding-model runtime was loaded. It never downloads assets automatically.

Missing private corpus/tokenizer assets are genuine prerequisites, not evidence that a clean checkout is ready to run. The existing source corpus is not redistributed. BGE assets and the LangChain/tokenizer software carry their separately recorded upstream licenses; a software/model license does not establish rights to publish the corpus.

## Decision record and stop boundary

ID: RAG-M2-01. Authorization date: October 22, 2026; implementation verification continued October 23. Status: M2 implementation authorized; results pending owner review. Decision: retain the accepted gateway and preparation contract; run a C01-only structure-aware, lossless 256/384-total-token comparison using pinned tokenizer/configuration assets and an isolated LangChain runtime. Rationale: measure real token budgets without changing frozen ingestion or treating QA/context as independent source content. Alternatives: modify frozen dependencies; decode/rewrite tokenizer output; generic prose-split bibliography; truncate oversized elements. Those alternatives violate the preservation and coverage requirements. Zero overlap and heading-only prefixing are disclosed pilot choices, not proven retrieval-quality optima.

The single working tracker remains `workspace/rag-implementation/v1/MILESTONE_TRACKER.json`. No M3 chunk catalog, dashboard extension, corpus expansion, embeddings, vector/lexical indexing, retrieval, generation or Git operations are included. Owner acceptance and separate authorization are required before proceeding.
