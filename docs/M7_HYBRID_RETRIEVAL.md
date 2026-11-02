> **Owner decision — October 25, 2026:** M7 is now OWNER_ACCEPTED / CLOSED for engineering integrity. M8 reconstruction is separately authorized, implemented and under verification; see [M8](M8_VERIFIED_EVIDENCE.md). Earlier delivery-time status below is historical; no relevance or hybrid-superiority claim is implied.

# M7 local candidate retrieval

M6 is owner accepted for lexical indexing integrity. M7 implements vector, BM25 and hybrid candidate retrieval against the same 992 authorized Chunk IDs and 553 verified parents. M7 results await project-owner acceptance. Relevance, hybrid superiority and answer quality have not been evaluated; M9 owns comparative evaluation. M8 evidence packaging and generation are not implemented.

## Explicit release and execution

Use `config/hybrid-retrieval-m7-v1.json` with its separately reviewed SHA-256 from the M7 exit report. Its immutable manifest binds the accepted QA, Unified, M3, M4, M5, M6 and operational selections, all six existing locks, implementation files and original Chroma physical witnesses. Historical selectors and defaults are unchanged. No new dependency or environment is installed.

From the repository root:

```sh
uv run --locked --offline --no-sync python -m tools.retrieval.service --root . \
  --selector config/hybrid-retrieval-m7-v1.json \
  --selector-sha256 87110b099e59aca1460bfd5dc847e073964c392ccf42b559ecf88483cddb37f9 \
  --query 'How does retrieval augmented generation work?' \
  --mode hybrid --top-k 10 --candidate-depth 50 --rrf-k 60
```

The SHA above identifies this explicit M7 engineering candidate; do not replace it with a hash computed from an arbitrary modified selector. The API has the same explicit arguments:

```python
from pathlib import Path
from tools.retrieval.service import RetrievalService

service = RetrievalService(Path.cwd(), selector="config/hybrid-retrieval-m7-v1.json",
                           selector_sha256=reviewed_selector_sha256)
try:
    result = service.search("reciprocal rank fusion", mode="hybrid", top_k=10,
                            candidate_depth=50, rrf_k=60,
                            filters={"document_id": "C10"})
finally:
    service.close()
```

Keep a service instance alive to reuse the loaded workers. Calls are serialized with a lock. Explicitly close it when finished; process exit also closes workers. Three offline JSON-lines workers execute in the unchanged embedding, indexing and lexical environments. They do not merge dependency locks or load models in the dashboard interpreter. A failed worker invalidates the service; reconstruct it explicitly. There is no automatic retry using a different retrieval mode.

## Query-only BGE contract

The pinned local model card recommends `Represent this sentence for searching relevant passages: ` for short retrieval queries. M7 prepends that exact instruction to the query after stripping outer whitespace; internal text is otherwise preserved. This is a provisional query policy, not a measured winner. Accepted document encoding retains its empty instruction.

The existing `LocalBGE` adapter checks model weights, revision, tokenizer parity, pinned packages, CPU float32, eager attention, CLS pooling, normalization and deterministic settings. Actual loaded model class hashes must match accepted M4 runtime evidence. M7 uses its unchanged tokenization/encoding functions with a 512-token ceiling including instruction and special tokens. Overlong queries fail; they are never silently truncated. Empty or punctuation-only queries return zero candidates without inference.

The encoder's internal bridge binds the query, instructed text, token IDs, model configuration and 384-dimensional finite normalized float32 vector. The public service accepts query text only; it does not accept caller-supplied vectors. Document vectors are never re-encoded.

## Native retrieval and fusion

Vector search uses the saved M5 Chroma collection through native `collection.query`. A verified temporary local copy isolates native database bookkeeping; the original accepted index is not opened by Chroma. All 992 vectors and exact metadata are checked before querying the copy, and original physical witnesses remain checked. The small eligible corpus is requested in full for deterministic distance/Chunk-ID boundary ties, then reduced to candidate depth. Native L2 distances are diagnostics, not probabilities.

BM25 delegates to the unchanged M6 public API. Its preprocessing, global IDF, native scores and exact-ID tie-breaking remain intact. A lexical match is required; scores can be nonpositive. Literal ChromaDB, GraphRAG, 0.25 and C++ are absent from the authorized prepared input strings and token inventory. Their independent tokenization preserves each term. Zero matches are not caused by losing these tokens, and do not establish absence from every raw or held source region. No index expansion was added to manufacture hits.

Hybrid fusion uses one-based ranks: `sum(1 / (rrf_k + rank))`. The initial constant is 60, without an optimality claim. IDs shared across lists appear once, with both original ranks and metrics. Single-retriever candidates retain their one contribution. Native scores and distances are never averaged or normalized into the RRF score. Final ties use ascending exact Chunk ID. Duplicate IDs within a native list, invalid rankings and unknown metadata fail closed.

Parameters: final top-K 1–992; candidate depth top-K–992; integer RRF constant 1–10,000. Booleans and fractional values are rejected. Exact filters are `document_id`, `format` and `reference_classification`, using recorded values. Filtering never alters classification or independently approves contextual membership. Vector and hybrid modes may return nearest candidates for queries with no exact lexical match; this does not establish relevant or sufficient evidence.

## Candidate contract and evidence boundary

Results contain release/selector identities, query hash, explicit parameters and ranked candidates. Each candidate has its exact Chunk ID, document/format/classification, contributing retrievers, native vector rank/distance, native BM25 rank/score, optional RRF score and mandatory complete-parent rehydration flag. Source text, snippets, qualified projections and independent evidence approvals are absent.

Use only the existing verified Chunk Inspector or the accepted `EmbeddingArtifacts.open_bound_chunk` gateway for authorized parent inspection. Preserve complete-unit restrictions, required source context, citations, C04 protected projections, C10 QA observations, C06 attribution, C14 scopes and PDF expiration warnings. Candidate metadata is not sufficient authorization. M7 does not reconstruct an M8 evidence package or infer new Section relationships.

Missing, changed or mixed-release source/index/model/code files fail closed. Cached workers and UI results retain a live filesystem lease. The original Chroma store, lexical records, model assets and source publications are not repair targets for this service.

## Streamlit

```sh
uv run --locked --offline --project apps/ingestion_dashboard streamlit run apps/ingestion_dashboard/app.py
```

Choose the durable operational release. Open **M7 · Local retrieval — Vector / BM25 / Hybrid**, enter a query and select mode, top-K, depth and optional filters. Results display contributions and native diagnostics. **Open verified parent** navigates to the existing Chunk Inspector; no second evidence viewer or answer generator exists. Historical inspection modes retain their original behavior. **Reset M7 workers** releases loaded components and requires explicit reconstruction.

## Verification, resources and rollback

Fresh functional/adversarial controls and actual timings are recorded in the private M7 workstream. Tests include an independent saved-vector distance oracle, an independent RRF arithmetic oracle, unchanged M6 parity, fresh-process ranking, invalid vectors, stale selectors, corrupt index files, invalid filters and no silent hybrid fallback. Streamlit AppTest is reported separately from manual browser verification.

Warm execution reuses the pinned BGE model and native index copy. Integrity hashing remains part of every query's latency. Reported local RSS and short-run timings are observations, not production capacity or cross-platform guarantees. Queries are not persistently logged by the service; explicit verification reports contain only the chosen engineering queries and candidate metadata. No external API or model download occurs.

Rollback: leave the M7 selector unused and close its workers. M0–M6 artifacts and historical dashboard modes remain independently usable. Do not delete accepted data, reset Git, regenerate embeddings or modify publications. The eight deferred Post-M11 findings and separate source-checkpoint/recovery follow-ups remain visible in the existing canonical tracker.
