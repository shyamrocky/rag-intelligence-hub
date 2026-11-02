# M9 acceptance and BM25 32K diagnostic findings

October 26, 2026. M9 is **OWNER_ACCEPTED / CLOSED** under D049. The bounded diagnostic is technically verified, pending owner review; no remediation is authorized.

The accepted result selector remains config/retrieval-evaluation-results-m9-v1.json, SHA-256 f3420b4645ac8b37819a37750d1d9a33e74b7d1e828f7711eef14e573d868ece. Manifest SHA-256 is 8a2dba7fc4def81eef74e76b168a5de4473a7ee9cae3bf64cec10dce339e0fad. The consolidated owner receipt is stored privately at data/evals/m9/approvals/m9-results-v1.json; it is a record of explicit instruction, not a digital identity attestation.

## What failed

Of 26 answerable BM25 questions, 16 have all required evidence groups included at 32K. The remaining ten are Q04, Q05, Q09, Q10, Q11, Q13, Q16, Q21, Q23 and Q25.

| Cause | Cases | Count |
|---|---|---:|
| Required group missing from BM25 top 10 | Q04/Q05/Q13/Q16/Q23 | 5 |
| Retrieved required parent exceeds entire budget | Q09/Q10/Q11/Q21/Q25 | 5 |
| Competition from earlier parents | Q04, overlapping with retrieval miss | 1 |
| Unresolved primary saved-record outcome | None | 0 |

Q04's retrieved required parents could fit together, but earlier parents occupy the budget. Its third required group is missing, and all three reference-only reserves total 33,417. Budget competition is therefore only part of that failure.

Saved hybrid metadata shows BM25 ranks 15/17/12 for missing Q04/Q05/Q16 groups. The final top-10 cutoff is established for those three; increasing candidate depth is not the demonstrated remedy. Deeper Q13/Q23 ranks and underlying lexical mechanisms remain unknown.

Q21's correct parent is rank 1 and costs 91,483 actual BM25 block tokens. Q09/Q10/Q11/Q25 required blocks cost 33,346/66,827/39,284/34,159. No C16 parent is required by these ten labels. Oversized unjudged C16 blocks illustrate serialization overhead but do not reserve selected token budget.

## Interpretation and next decision

First consider a separately authorized **compact verified-evidence design assessment**, preserving complete source/context/citations/qualifications and native audit records. Separately investigate top-K/fallback sensitivity for missing groups. No retrieval algorithm, budget, default, M8 assembly rule or evidence scope changed.

Reference-only estimates, exact saved actual block counts and calculated fixed-order reserve thresholds are distinct. Newly measured final package costs at different budgets are NOT MEASURED. No larger budget is claimed to improve answer quality. Known-positive labels are not exhaustive; unjudged candidates are not automatically irrelevant.

Private source-bound reports are at data/evals/m9/diagnostics/bm25-32k-v1/: FINAL_READ_ONLY_REPORT.md, TEN_CASE_DIAGNOSTIC_MATRIX.json/.md, TOKEN_COST_ANALYSIS.md, ROOT_CAUSE_FINDINGS.md and PRE_GENERATION_GATE_IMPLICATIONS.md. They are inspection artifacts, not evidence authorization. Reproduction helper and focused tests are in workspace/rag-implementation/v1/m9-bm25-diagnostic-v1/.

Fresh verification: 17 saved-record tests passed, including alternative-parent semantics, deduplication, malformed-data rejection and non-monotonic greedy reserve calculations. No M7 search, query/model execution, M8 assembly or full historical regression ran. Original 371 sealed M9 artifacts, protected upstream files, Git HEAD/index and canonical debt remain unchanged; acceptance and governance records are additive/current updates.

The runtime pre-generation gate cannot consult benchmark labels or guarantee semantic sufficiency. Compact evidence and pre/post-generation gates remain proposed. Optional chunk-size comparison, eight Post-M11 findings and separate source-control/recovery follow-ups remain pending. M10/M11 require explicit authorization.
