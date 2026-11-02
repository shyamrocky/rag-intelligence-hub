# Isolated RRF versus MiniLM experiment

October 26, 2026. Phase 3 is **OWNER_ACCEPTED / CLOSED** under
[D051 v1.0](adr/D051-rrf-ranking-decision-v1.md). The owner retains RRF(k=60) as the
Week 2 POC default; MiniLM remains experimental. The existing runtime configuration
is unchanged. The sealed experiment report retains its original delivery-time
pending status; the additive owner receipt records subsequent acceptance.

The experiment uses the exact frozen fifteen questions, approved relevance labels
and sealed BM25/vector top-50 unions. It retains all 1,294 original memberships and
scores the approved 1,297 cross-encoder inputs with the pinned MiniLM checkpoint,
unchanged CPU float32 environment and maximum-window-score policy. RRF uses the
existing accepted fusion function with constant 60 and original native ranks.
Neither discovery nor accepted M7/M8 execution was rerun or modified.

Primary metrics are completed-evidence-group witness Recall@5/10/20 and MRR@10,
preserving OR source equivalents and joint AND witnesses. Parent location and native
M9 chunk-target diagnostics are separate. Unjudged passages are not automatically
irrelevant. All full-pool rankings were sealed before automated label scoring.

Across all fifteen questions:

| Ranker | Recall@5 | Recall@10 | Recall@20 | MRR@10 | Complete questions @10 |
|---|---:|---:|---:|---:|---:|
| RRF60 | 64.4% | 64.4% | 80.0% | 0.544 | 8/15 |
| Window-aggregated MiniLM | 52.2% | 70.0% | 76.7% | 0.569 | 10/15 |

Warm full-pool p50/p95 reranking latency was 0.212/0.241 milliseconds for RRF and
2.544/2.716 seconds for MiniLM. There were 75 timed query samples per method and
scenario, using the approved 20/50/full-pool subsets and five repetitions. Three
independent model-load processes passed exact checkpoint checks. All 450 timed
rankings and score fingerprints were stable in the qualified worker. Cold loading,
source verification and discovery are excluded from warm reranking latency.

The owner accepted retaining RRF for this POC: neural gains are mixed and add
material CPU latency. This bounded decision makes no universal superiority claim
and requires no runtime default change. The five natural
questions and original ten are reported separately in the private result packet.

The private versioned report is
`data/evals/ranking/phase3-experiment-v1/EXPERIMENT_REPORT.md`; its manifest binds
rank outputs, metric definitions, raw timings, source reconciliation, code recipes
and verification evidence. The existing canonical milestone tracker records the
exact manifest fingerprint. Private questions, labels and results remain outside
Git. No new publication or QA authority is introduced.

Implementation and synthetic tests:

- [Comparison metrics and subset kernel](../tools/ranking/comparison_v1.py).
- [Comparison tests](../tests/test_ranking_comparison_v1.py).
- [Accepted experimental windowing contract](RANKING_WINDOWING_PREFLIGHT.md).

Verification passed 130 distinct final tests, repository/helper lint and scaffold
smoke. Existing source/QA/model/vector/index identities, frozen pools and labels,
and all 2,000 protected preexisting hashes remained unchanged. Full H1, live
retrieval reruns, M8 budgeting and answer generation were outside this scope.

Window coverage does not reproduce whole-passage attention; max aggregation gives
three candidates an additional scoring opportunity. The fifteen reviewed/exposed
questions do not establish exhaustive relevance, statistical superiority or answer
faithfulness. M8 oversized-parent limitations remain untested and unresolved by
this ranking comparison. Exact numerical repeatability across platforms or new
inference processes was not established.

Do not rerun private recipes into sealed output paths. Any further experiment,
MiniLM adoption, M8 refinement or M10/M11 implementation requires separate
owner authorization. No model downloads, dependency changes or Git operations were
performed.
