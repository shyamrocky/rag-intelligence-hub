# M8 verified evidence reconstruction

M7 is owner accepted for retrieval engineering integrity. M8 is an opt-in, read-only composition service awaiting project-owner acceptance. It reopens exact M7 candidates through the accepted `EmbeddingArtifacts.open_bound_chunk` → M3 → Unified → native publication gateways. It creates no admission, source correction, publication decision or new index. Relevance, answer support and comparative retrieval quality remain M9 questions.

## Select and assemble

Use the explicitly reviewed selector and SHA in the M8 exit report. The configuration manifest is an immutable implementation/budget contract, **not** a QA publication. It binds the accepted M7 release, which binds QA, Unified, M3–M6, operational selections, six locks and original native index witnesses. Historical defaults remain unchanged.

Run Python from the repository root using the existing embedding environment, which provides NumPy for the accepted artifact reader:

```sh
uv run --locked --offline --no-sync --project tools/embeddings python
```

```python
from pathlib import Path
from tools.retrieval.service import RetrievalService
from tools.evidence.service import EvidenceService, EvidenceIntegrityError

root = Path.cwd()
retrieval = RetrievalService(
    root, selector="config/hybrid-retrieval-m7-v1.json",
    selector_sha256="87110b099e59aca1460bfd5dc847e073964c392ccf42b559ecf88483cddb37f9",
)
evidence = EvidenceService(
    root, selector="config/evidence-reconstruction-m8-v1.json",
    selector_sha256="e0ac189c8b5ffd331f28ae87f81d56c22868e12c45d7b73e6a5e7f1a65c6bef2",
)
try:
    candidates = retrieval.search("reciprocal rank fusion", mode="hybrid", top_k=5)
    package = evidence.assemble(candidates, token_budget=16000)
    # Revalidate just before supported downstream use. Do not treat exported JSON
    # as a bearer authorization or reuse it after source/QA/clock bindings change.
    evidence.validate(package, candidates)
    if package["status"] == "VERIFIED_EVIDENCE":
        llm_input = package["llm_evidence"]  # Counted whole-parent blocks, no generation here.
    else:
        omissions = package["diagnostics"]["omitted"]
finally:
    retrieval.close()
```

`EvidenceIntegrityError` is a failure, not an empty retrieval result. Invalid candidate/configuration or altered source, model, index, citation and publication bindings fail the entire request. No partial success or fallback occurs on integrity failure. A valid request instead returns `VERIFIED_EVIDENCE`, `NO_RETRIEVAL_CANDIDATES` or `INSUFFICIENT_EVIDENCE_FOR_BUDGET`. These statuses describe verified availability, not semantic sufficiency for an answer.

## Contract and source separation

Schema: `m8-evidence-package-1.0`. The API accepts an M7 result and integer budget 1–1,000,000; it never accepts caller-supplied source text, parents, projections or evidence packages as candidate inputs.

| Field | Purpose / consumption boundary |
|---|---|
| `schema`, `release_identity`, `selection` | Explicit M8 implementation identity; not source admission |
| `retrieval` | M7 identity, mode, query SHA, original result hash; rank provenance is validated transport, not signed origin/relevance proof |
| `status`, `verification`, `counts` | Successful live verification versus ordinary no-candidate/budget outcomes |
| `parents[].evidence.verified_parent` | Exact complete authorized Unified consumer bundle; no raw native/audit fallback |
| `...consumer.llm_context.source_content` | Publisher/source content, including authorized warning-bearing restricted projections |
| `...consumer.llm_context.required_context` | Mandatory context and supporting headings; never independently promoted |
| `...consumer.llm_context.qa_observations` | Ingestion findings, explicitly distinct from publisher statements |
| `...consumer.llm_context.qualification` | Mandatory complete-unit, allowed/forbidden-use restrictions |
| `...consumer` additional fields | Native source fidelity, related evidence, format context and live expiration fields, unchanged |
| `...citation_locators`, `publication_identity`, `memberships` | Exact native citations, source bindings and many-to-many roles |
| `parents[].evidence.contributing_candidates` | Every matching Chunk ID, rank, mode and native/RRF diagnostic retained |
| `parents[].evidence.citation_precision` | Recorded chunk source/lineage and unchanged native parent locators; no finer coordinates inferred |
| `parents[].token_count` | Count of that complete canonical JSON block including special tokens |
| `llm_evidence` | The sole budgeted downstream content representation: concatenated complete JSON evidence blocks |
| `budget`, `diagnostics` | Counting configuration, deduplication and omissions; audit/control metadata outside the LLM content budget |

The complete verified parent is retained without flattening its envelope into publisher prose. QA commentary and qualifications are labeled fields, never source claims. Related context remains bound inside each parent; shared text across *different* parents is not removed. Exact Unit ID is the sole deduplication key. All original contributions survive parent deduplication. Detached candidate text and duplicate/cross-release IDs are rejected.

The M7 result has no cryptographic origin signature. M8 verifies its schema, release chain, allowed IDs/metadata, native ranks and RRF arithmetic; it does not claim authenticated retrieval execution or relevance. Even a self-consistent caller ranking over legitimate IDs still needs full live source authorization. Candidate diagnostics never authorize evidence.

## Atomic evidence budget

Policy: `m8-atomic-bge-json-1.0`. The existing `PinnedBgeTokenizer` runs in the unchanged `tools/chunking` environment, with no inference, network or dependencies added. It uses the frozen BGE tokenizer spec, counts complete canonical UTF-8 JSON blocks with special tokens, disables padding/truncation and binds text hashes to counts. Counting can exceed BGE's 512-token **embedding** limit; M8 performs token counting only, not embedding or generation.

Parents are considered in best final candidate-rank order. Each complete block includes authorized content, context, warnings, qualifications, citations, publication identity, membership roles and all contributing candidate/span references. Per-block special-token overhead is conservatively reserved. Oversized parents are skipped intact; later fitting parents can still be included. The final concatenated `llm_evidence` is counted again exactly and must fit the requested budget. No internal source sentence, context, citation or qualification is removed to save tokens.

Omissions report `PARENT_EXCEEDS_TOTAL_BUDGET` or `BUDGET_EXHAUSTED`, exact full-block count, remaining reserved budget and contributing IDs. If none fits, no partial parent is exposed. Token counts do not establish an M10 LLM context window or guarantee parity with another tokenizer. M10 must select its own compatible budgeting policy and reserve system/query/generation overhead separately; this task implements neither M10 nor a universal prompt limit.

## Qualifications and citation precision

- C04: only the existing protected `restricted_projection` is consumable; code defects and unverified score semantics retain complete-unit restrictions and warnings. No raw `source_evidence` fallback.
- C06: source benchmark attribution, contextual requirements and incomplete mathematical/visual qualifications remain native and inseparable.
- C10: table and RRF context retain source boundaries; scoring ambiguity remains a `QA_OBSERVATION`, not a publisher statement.
- C14: bibliography attribution and three qualified appendices remain separate native scopes and Unit IDs.
- PDFs: publication expiration is an informational warning, carried live into the package. Altered integrity remains blocking. Recorded parent/display-projection citation precision is retained; no boxes or glyph coordinates are invented.

`validate(package, original_m7_result)` reconstructs and compares every field, including counted text, token counts, parent provenance and live warnings. `serialize(...)` calls that validation. Supported consumers must use this path immediately before consumption; arbitrary saved/edited JSON is never an authorization token. Do not persist complete packages in public logs, Git or unrestricted caches. Private engineering fixtures are distinct from source admissions or independently reviewed ground truth.

## Streamlit and rollback

Launch:

```sh
uv run --locked --offline --project apps/ingestion_dashboard streamlit run apps/ingestion_dashboard/app.py
```

Select the durable operational release, run M7 search, then enable **View verified evidence package** and choose a BGE budget. The view reuses existing source/qualification rendering helpers and complete-parent navigation. It shows selected parents, deduplication, citations/precision and explicit omissions. It does not cache detached packages in session state. The leased read-only corpus/service can be reused; every requested evidence view reopens native parents and checks current bindings.

Rollback: leave M8 unselected/unchecked; the accepted M7 candidate APIs, native publications and historical inspection modes remain usable. No source/QA/model/index rollback or regeneration is needed. Source-control and independent-current-recovery follow-ups and all eight deferred Post-M11 findings remain separately tracked. M9–M11 require separate owner authorization.

The complete recorded consumer envelope can cost substantially more than source prose alone. A measured C14 bibliography parent is 84,064 BGE tokens before the additional contributing-chunk lineage block. That envelope retains extensive native citations and source metadata. Small budgets intentionally omit such a parent whole. The default UI budget of 16,000 is a convenience for inspection, not a guarantee that every parent fits or an approved M10 context size. No compacted citation/provenance consumer contract is introduced by M8.
