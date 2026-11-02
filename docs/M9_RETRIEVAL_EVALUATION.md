**Measured delivery — October 26, 2026:** M9 is technically verified, pending project-owner acceptance. Explicit result selector `config/retrieval-evaluation-results-m9-v1.json`, SHA-256 `f3420b4645ac8b37819a37750d1d9a33e74b7d1e828f7711eef14e573d868ece`; manifest SHA-256 `8a2dba7fc4def81eef74e76b168a5de4473a7ee9cae3bf64cec10dce339e0fad`. All87 cases /348 budget observations completed and independently checked. BM25 MRR@10=0.731; hybrid=0.707; vector=0.581. BM25/hybrid equivalence-aware Recall@10=82.1%, vector=69.2%. Complete required evidence at32K:16/26,15/26,11/26 respectively. Chunk-size and compact-evidence experiments remain unimplemented.

# M9 retrieval, evidence and token-budget evaluation

M0–M8 are owner accepted. The owner approved all 29 benchmark-v1 questions and proposed labels without revisions, against manifest SHA-256 `17f1c6594ff7e435b3f0da636165c4daf105f9a768f13bac80742eb33640065d`. One consolidated receipt is preserved at `data/evals/m9/approvals/benchmark-v1.json`; no individual signatures or independent reviewer attestations are created. Original proposal/status fields remain unchanged for audit history. The receipt establishes current ground-truth acceptance.

M9 technical results require separate project-owner acceptance. M10 generation remains unauthorized. This evaluation measures retrieval and evidence availability; it does not certify publisher claims, generated answers or production readiness.

## Frozen method

Private benchmark files remain in `data/evals/m9/benchmark-v1/`. The [review checkpoint](M9_BENCHMARK_REVIEW.md) describes source bindings and label scope. The executable final recipe is `config/retrieval-evaluation-m9-v3.json` with SHA-256 `222e23d0987966eb3b7c748fa036b2d9fec435e06716ec7739f2d0ab917e9962`.

All three modes use exactly the approved questions, current 992 authorized Chunk IDs, top-K 10, candidate depth 50, RRF constant 60 and no filters. The runner calls unchanged M7 and M8 APIs in their existing locked environments. It does not change source admission, index contents, document embeddings, query instructions or global defaults.

Every actual scenario passes through `EvidenceService.assemble`, which verifies native parent/source/file bindings before and after assembly. Repeated search checks cover every query/mode. Additional complete-package replay covers Q01 and Q21 in every mode/budget. Reference-only expected-parent controls are independently assembled/replayed for diagnostic fit estimates. Preliminary sequential/concurrent timing probes are preserved separately and excluded from the final comparison; final execution uses one verified M8 snapshot. No query, label, retrieval setting, metric definition or M8 policy was tuned in those timing changes.

## Metrics and their limits

- Answerable denominators: 26 questions; unsupported controls Q27–Q29 remain separate.
- Raw known-positive chunk Recall@K uses every approved positive Chunk ID, with macro and micro denominators.
- Equivalence-aware chunk recall collapses only explicitly approved single-chunk alternatives: Q06's eight representations and Q20's two representations. It does not invent new positive labels or call unjudged chunks irrelevant.
- MRR@10 uses one-based first known-positive rank, or zero when absent. Unsupported controls have no ordinary recall/MRR value.
- Parent/group coverage recognizes any approved alternative parent in each required group. Q02/Q04/Q13/Q26 require all two/three/two/two groups; Q17's two chunks share one parent.
- A different child from the correct parent can permit complete evidence reconstruction even when the directly labeled chunk is missing. Direct chunk relevance and parent access are reported separately.
- Evidence inclusion is measured through unchanged M8 at 4,000/8,000/16,000/32,000 BGE tokens. A verified package is not proof of semantic answer sufficiency. Complete parents are included or omitted, never truncated.

Reference-only fit controls use known-positive parents outside retrieval scoring. Their measured wrapper/rank context differs from actual search, and they exclude competing irrelevant parents. A fit estimate is not a recall result or a promise about actual top-10 inclusion.

Token reports distinguish exact final evidence tokens, conservative complete-block reserves and omitted complete-block counts. Independently serialized source, context, citation, qualification and metadata costs are non-additive. Restricted projections can contain inseparable warning text. Efficiency per 1,000 tokens is an evidence-group proxy, not answer quality. BGE counts do not select an M10 model/window; system/query/output overhead and that model's tokenizer remain future obligations.

This is a small, source-authored, exposed benchmark with bounded known-positive qrels. Document-anchored/exact-term questions may favor lexical matching. Per-category samples can be singletons; no statistical generalization or universal retrieval/model winner is established.

## Private outputs and supported commands

The completed full comparison is stored under `data/evals/m9/runs/m9-v3/`; source/publisher evidence packages are not stored as unrestricted search payloads. Per-case files contain actual candidate references, metric values, parent IDs, budget outcomes and obligation hashes. Only the original verified gateway authorizes evidence.

To execute an explicitly authorized fresh logical replay, use a new private output directory:

```sh
uv run --locked --offline --no-sync --project tools/embeddings python -m tools.evaluation.runner \
  --config-sha256 222e23d0987966eb3b7c748fa036b2d9fec435e06716ec7739f2d0ab917e9962 \
  --output data/evals/m9/runs/m9-replay-001
```

This performs query encoding and evidence verification; it does not rebuild indexes or document vectors. Full evaluation is deliberately more expensive than one search. Existing complete outputs must not be overwritten. Interrupted compatible runs can reuse hash-bound measurement journals, which are never evidence authorizations. Logical ranking/metric equivalence is the reproducibility criterion; elapsed timings are not byte-reproducible.

The independent verifier rederives known-positive ranks, parent-group coverage, reconstruction membership and all budget accounting using actual public catalog metadata:

```sh
uv run --locked --offline --no-sync --project tools/embeddings python -m tools.evaluation.verify_results
```

Its additional Q21 cost probe is diagnostic, outside the four scored budgets. It retains complete native evidence and checks measured block costs against actual omission records. It never implements a compact projection.

## Streamlit inspection

Launch the existing application:

```sh
uv run --locked --offline --project apps/ingestion_dashboard streamlit run apps/ingestion_dashboard/app.py
```

Select **Durable full corpus — current operational candidate**, open **M9 · Retrieval evaluation**, then enable **View M9 measured evaluation**. The view uses a fingerprinted, explicit result selector, validates complete measured coverage and recomputes aggregates. It displays no fabricated metrics or raw-source fallback when integrity fails. Existing historical modes and M7/M8 inspectors remain unchanged.

Select a question and budget to inspect outcomes, source-equivalent groups, actual candidate ranks and diagnostic reference fit. **Copy this question to existing M7 search** only populates the existing form; it does not execute another evaluation or query automatically. Candidate buttons reopen the existing live verified-parent Chunk Inspector. Static metrics and saved candidate metadata never authorize source content.

## Remaining boundaries

The historical C01 256/384 pilot is not two compatible current retrieval pipelines. Its [existing experimental proposal](../workspace/rag-implementation/v1/m9-benchmark-review-v1/CHUNK_SIZE_EXPERIMENT_PROPOSAL.md) remains PENDING separate authorization. No alternative chunks/vectors/indexes/readers were produced.

Compact evidence is feasibility analysis only. Any removal of redundant serialization, separation of audit metadata from model input, citation-reference reuse or narrower projection needs a separately approved versioned contract and independent preservation/adversarial tests. Complete source/context/warnings and citation precision cannot be silently dropped to fit a budget. A narrower source scope may also require upstream QA authorization.

All eight Post-M11 debt findings remain deferred in the existing canonical register. Source-control and independent-current-recovery follow-ups remain separate. No Git operation, backup transfer, default change or M10 implementation is authorized by these results.

## Approved direction D042

- **Date:** October 26, 2026.
- **Decision:** Accept all benchmark-v1 questions/labels by one consolidated owner receipt and execute fixed M9 retrieval/evidence/budget comparisons plus a bounded results dashboard. Stop for M9 result acceptance.
- **Rationale:** Evaluate discovery, usable complete evidence and token cost independently, using existing source-authority gateways.
- **Alternatives:** Tune labels/settings after seeing results, score unjudged content as proven irrelevant, substitute oracle parents into retrieval, compact evidence, or build an unapproved alternative pipeline. None is authorized.
- **Status:** Owner-approved execution scope. Result acceptance remains pending; M10/M11 remain unauthorized.
