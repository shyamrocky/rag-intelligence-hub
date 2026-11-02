# M6 local BM25 candidate index

M6 is implemented for technical verification and separate owner acceptance. It consumes exactly the accepted durable M5 inventory of 992 Chunk IDs, backed by 553 verified parents. M7 hybrid search remains unauthorized. The selected BGE model, five earlier runtime locks, source publications, chunk catalog, vectors and Chroma store are preserved.

## Boundaries and runtime

`tools/lexical/` is a sixth isolated locked environment: Python 3.12.15, rank-bm25 0.2.2 and NumPy 2.2.6. The [upstream library](https://github.com/dorianbrown/rank_bm25) implements Okapi BM25; preprocessing is our versioned policy, not library behavior. Only authorized dependency metadata and its small wheel were acquired. All index operations are local and deny network. No models or source documents are downloaded.

Run commands from the repository root. Existing private corpus, accepted durable QA/Unified/M3/M4/M5 assets and environments are prerequisites. A fresh install of the sixth environment requires `uv sync --locked --project tools/lexical`; offline installation needs the already cached pinned wheel closure. Do not sync or upgrade the five accepted environments.

The explicit opt-in selector is `config/keyword-index-m6-v1.json`. Obtain its reviewed SHA-256 from the M6 exit report; pass it explicitly, rather than trusting an arbitrary replacement file. No default changes or active-publication registry are introduced.

```sh
uv run --locked --offline --no-sync --project tools/lexical python -m tools.lexical.bm25_index inspect --root . --selector config/keyword-index-m6-v1.json --selector-sha256 d9d8125ee77b4c88c0480526de9ed8da7c0b90cde37d235cc0c5da0744d65df0
uv run --locked --offline --no-sync --project tools/lexical python -m tools.lexical.bm25_index search --root . --selector config/keyword-index-m6-v1.json --selector-sha256 d9d8125ee77b4c88c0480526de9ed8da7c0b90cde37d235cc0c5da0744d65df0 --query BM25 --top-k 5
```

The fingerprint above binds this exact technically verified candidate; separate owner acceptance remains pending.

## Authorized text and persistence

The build export calls unchanged `EmbeddingArtifacts.open_bound_chunk` and `embedding_input` in the existing embedding environment. This resolves every complete verified parent before obtaining its approved source slice plus permitted supporting headings. Text, qualification, publication and Chunk IDs must match accepted M4 input hashes and M5 metadata. It never flattens QA observations or qualifications into publisher text. Raw normalized Sections and context-only memberships cannot become new standalone records.

The private export is `data/indexes/m6-bm25-v1/verified-inputs.json`. A content-qualified subdirectory stores canonical `records.json` (tokens and permitted identity metadata) and `manifest.json`. The manifest binds policy, implementation, library code/runtime, lexical records and upstream source/QA/model/catalog identities. Tokens remain restricted search data, not independent evidence. Keep all generated files out of Git.

Reader construction regenerates and compares the exact token inventory against hash-bound approved input evidence. It reopens no model or original Chroma database. Every candidate operation checks its filesystem lease before and after scoring. An explicit hash is required; missing, corrupt, stale or mixed-release assets fail without historical fallback. JSON only, no pickle. Immutable atomic builds reject existing conflicting files and never repair them silently.

## Lexical contract

`config/bm25-preprocessing-v1.json` defines Unicode casefold; whitespace and exterior punctuation boundaries; intact internal underscores, hyphens, dots, slashes and colons; C++/C# suffixes; ASCII-signed numeric values, decimals and percentages. Nonnumeric connector-linked terms additionally yield distinct component aliases, so multiword queries can match hyphenated terminology without deleting the exact term. No stemming, stopword removal or Unicode compatibility rewrite. Query duplicates are retained. The original source string is never modified.

Parameters: BM25Okapi, k1=1.5, b=0.75, epsilon=0.25. Document frequency is computed globally; metadata filtering selects candidates after scoring, without reclassifying or recomputing a different corpus. Match requires an actual lexical token intersection; zero/negative scores may occur for common terms and do not imply no match. Ties use ascending exact Chunk ID. Empty lexical documents remain accounted for. These parameter choices are a reproducible baseline, not an evaluated retrieval winner.

## Candidate API

```python
from pathlib import Path
from tools.lexical.bm25_index import BM25Index

index = BM25Index(Path.cwd(), selector="config/keyword-index-m6-v1.json",
                  selector_sha256=reviewed_sha256)
result = index.search("retrieval-augmented generation", top_k=5,
                      filters={"document_id": "C01"})
```

Only `document_id`, `format` and native `reference_classification` exact filters are supported. Unknown keys/values fail. `top_k` must be an integer 1–992; booleans, fractional, nonpositive and larger values fail. Empty, whitespace, punctuation-only and no-match queries return no candidates. A non-string query fails.

Results contain candidate authority, selected index identity, explicit selector/hash, mandatory parent-rehydration flag and ordered candidates with exact Chunk ID, score, rank, document ID, format and reference classification. They contain no source text, source excerpt, QA commentary or detached authorization. Do not present candidates as evidence.

For content inspection, use the unchanged durable Chunk Inspector or `EmbeddingArtifacts.open_bound_chunk(candidate_chunk_id)` with the accepted explicit durable catalog and embedding selections. Retain its complete parent, context, citations, source/QA distinction, C04/C10/C14 qualifications, C06 attribution and PDF expiration warnings. Search tokens cannot substitute for this call. No new M8 evidence reconstruction is implemented.

## Verification, limits and rollback

Focused tests use real corpus bindings, the actual BM25 library and disposable copies for corruption controls. Fresh-process reopening, exact rebuilds, stable ranking, unauthorized IDs/content, bad filters, altered tokens, rehashed forged indexes and missing files are checked. Existing M5 tests run on a disposable complete validation root, preserving original Chroma physical bytes. H1 focused coordinator/chunking/historical controls and artifact gates are reused through their unchanged public tools; full H1 is unnecessary for additive isolated code and would run out-of-scope model controls. No full-suite execution is claimed.

M9 must evaluate relevance independently. Alias expansion can affect term frequency and ranking; punctuation/Unicode tokenization is intentionally simple. Same-host timings and RSS do not establish production concurrency, portability or quality. The eight deferred findings remain in the canonical Post-M11 backlog. Current source-only checkpoint and independent recovery are still outstanding; the new sixth lock/wheel and private index must join a separately authorized recovery snapshot.

Rollback: leave the M6 selector unselected and use the unchanged accepted M0–M5 stack. Preserve the versioned index for exact replay. Do not reset Git, alter historical selectors, weaken hashes or delete private artifacts. No Git action, backup transfer or M7 execution is authorized by this document.
