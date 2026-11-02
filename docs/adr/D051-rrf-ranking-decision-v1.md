# D051 — Retain RRF for the Week 2 POC

- **Version:** 1.0.
- **Date:** October 26, 2026 (America/Los_Angeles).
- **Status:** OWNER_ACCEPTED / CLOSED.
- **Authority:** Explicit project-owner “Phase 3 Owner Decision and Closure” instruction. This records the instruction; it is not an independent identity attestation or digital signature.
- **Decision:** Retain RRF(k=60) as the default ranking method for the Week 2 RAG Intelligence Hub POC. Do not adopt MiniLM into active retrieval. Existing BM25-only and vector-only modes remain available; no runtime configuration is changed by this decision.
- **Predecessor:** [D050 — Hybrid candidate discovery and relevance reranking](../decisions.md#d050--hybrid-candidate-discovery-and-relevance-reranking).

## Context and alternatives

The accepted M7 service provides BM25, vector and hybrid RRF candidate retrieval. M8 separately reconstructs complete authorized parents and applies atomic budgets. A bounded experiment compared retaining existing RRF with adopting a pinned local MiniLM cross-encoder, including its approved full-coverage windowing policy. Retaining both as experimental alternatives was also considered. Candidate ranking grants no source or evidence authorization.

The chosen approach retains RRF in the active path and preserves MiniLM as an experimental artifact. MiniLM's modest top-10 gains do not justify its measured latency and additional implementation complexity for this local POC.

## Methodology and measured results

Fifteen frozen, owner-reviewed questions comprised ten original M9 questions and five natural-language questions. Both methods ranked identical sealed BM25 top-50/vector top-50 unions: 1,294 original question–candidate memberships, 534 distinct Chunk IDs, and 22 required evidence groups. Retrieval was not rerun. Unjudged passages were not treated as irrelevant.

RRF used original one-based ranks and k=60. The cross-encoder was `cross-encoder/ms-marco-MiniLM-L6-v2`, revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, in the unchanged CPU float32 runtime. Policy `ce-fullcoverage-two-window-1.0` retained 1,291 complete fitting inputs and six overlapping windows for three overflowing pairs, giving 1,297 scoring inputs. Maximum finite window score mapped each result back to its original Chunk ID; exact score ties used ascending Chunk ID.

Recall below is macro, equivalence-aware completed-evidence-group witness recall, preserving OR alternatives and joint AND witnesses. MRR@10 measures the earliest completed group witness; complete-question coverage separately requires every group. These are bounded known-positive metrics, not exhaustive relevance judgments.

| Metric, all 15 questions | RRF(k=60) | MiniLM + windows |
|---|---:|---:|
| Recall@5 | 64.4% | 52.2% |
| Recall@10 | 64.4% | 70.0% |
| Recall@20 | 80.0% | 76.7% |
| MRR@10 | 0.544 | 0.569 |
| Complete questions @10 | 8/15 | 10/15 |
| Complete questions @20 | 11/15 | 11/15 |
| Warm full-pool median reranking latency | 0.212 ms | 2,544 ms |
| Warm full-pool p95 reranking latency | 0.241 ms | 2,716 ms |

The approved 20/50/full-pool timing scenarios used five repetitions and one untimed warmup per question/method/scenario: 450 timed samples in total. Full pools contained 74–94 candidates, with 75 timed query samples per method. Three separate process-cold loads verified the checkpoint. Warm times exclude discovery, model loading and source verification; they are not end-to-end query latency. Very short RRF timings are subject to timer noise. Original-ten and natural-five results remain separately available in the sealed report.

## Trade-offs and unresolved findings

- MiniLM improves complete top-10 evidence discovery for M9-Q04, R02 and R04, but loses R05's complete top-10 result.
- M9-Q05's first completed witness ranks 31/23 for RRF/MiniLM; R03 ranks 49/47. Both remain outside the top 20.
- M9-Q23 regresses from rank 17 with RRF to 36 with MiniLM.
- M9-Q13 retains incomplete required-group coverage, including at top 20 for both methods.
- Oversized M8 parent-evidence envelopes remain unresolved. Q21 ranks first with both methods; ranking does not establish that its complete parent fits an evidence budget. No M8 assembly or budget improvement was measured here.
- Full token coverage across windows does not provide whole-passage attention. Maximum-score aggregation gives windowed candidates additional scoring opportunities.
- Fifteen selected, exposed questions, one model, one runtime and one windowing policy do not establish statistical or universal superiority, answer faithfulness, cross-platform repeatability or production readiness.

## Preservation, verification and reconsideration

The accepted experiment manifest is `data/evals/ranking/phase3-experiment-v1/EXPERIMENT_MANIFEST.json`, SHA-256:

`d4147705c4c648e29ef8a806a5e77345925b0d2d4827d94edd79bdee5dc057d9`

The additive decision receipt is `data/evals/ranking/approvals/phase3-owner-closure-v1.json`. Private closure verification is recorded under `workspace/rag-implementation/v1/ranking-phase3-owner-closure-v1/`. The experiment's delivery-time pending status remains immutable; this later owner receipt establishes acceptance. Its 130 final passing tests are historical verification, not tests rerun for this documentation task.

Preserve acquired MiniLM assets, the windowing adapter, frozen labels and pools, rankings, timing records and all accepted M0–M9 artifacts. The active M7 selector and manifest retain their original hashes and RRF constant 60. No production code or configuration change is required or authorized.

Reconsider cross-encoder reranking only through a separately authorized, versioned experiment if a broader reviewed benchmark or changed use case demonstrates worthwhile gains, if measured hardware/runtime cost becomes acceptable, or if failures justify evaluating another explicitly pinned model/input policy. Preserve the RRF control and use identical candidate pools. Any label, runtime, dependency, model or M7/M8 adoption change requires its own approval and regression evidence.

The ranking comparison workstream is closed. M8 refinement, compact evidence, further experiments, M10/M11 and Git actions remain unauthorized. Stop for separate owner instruction.
