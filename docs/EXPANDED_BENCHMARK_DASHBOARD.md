# Expanded benchmark and dashboard — current experimental entry

October 28, 2026. Reconciliation, read-only dashboard expansion and generation
preparation only. Implementation pending owner review; no live generation, provider
preflight, retrieval rerun, production cutover or M11 is authorized.

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/master_dashboard/expanded.py --server.address 127.0.0.1 --server.port 8512 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8512>. Use the existing dashboard environment; no installation,
SDK, credential or provider connection is needed. Required private artifacts must
already be locally present. Missing or altered required bindings fail closed.

The current entry is a versioned successor to `apps/master_dashboard/app.py`.
That original 15-question application and its sealed implementation remain unchanged
and explicitly runnable for historical replay. The same master navigation and exact
HTML Candidate–Parent Explorer are reused. The explorer retains its original scope;
it is not expanded or rebuilt into another candidate browser.

## Reconciled membership

| Cohort | Questions | Meaning |
|---|---:|---|
| A | 10 | Original Difficult — Stress-test retrieval and generation |
| B | 5 | NLP — Test realistic user queries |
| C | 16 | Original Remaining — Verify apparently easier retrieval cases |
| D | 3 | Abstention — Test correct unsupported-question handling |

The new reference layer contains34 unique questions:31qualified answerable questions
and3unsupported controls. It references40 existing mandatory groups (31from the
original M9 answerable questions,9from the natural-language extension). The existing
15-question/22-group freeze remains unchanged; no group or label was added to it.

The authoritative original set is the approved29-question M9 benchmark:26answerable
questions plus M9-Q27–Q29 unsupported. No separate sealed26-question candidate
publication was located. The preparation records explicitly identify26answerable
proposals within that29-question set; this is a verified subset, not an invented
independent publication. Earlier provisional HTML/PDF golden questions have different
IDs, scope and review status; they are not merged through fuzzy topic similarity.

The ten difficult IDs are taken from the exact frozen mapping and unchanged original
M9 labels. R01–R05 retain their exact texts and approved qualitative/source-native
limits. M9-Q01–Q26 minus those ten form cohortC; unsupported questions are disjoint.
No duplicate IDs, exact-text duplicates or ambiguous canonical memberships were found.
Original proposal fields remain unchanged; effective approval comes from the owner
receipts/frozen wrapper, not from rewriting a historical `PROPOSED` field.

Reference artifacts: `data/evals/expanded-benchmark/v1/`. `MANIFEST.json` binds the
reference inventory, Phase1report, remaining-question outcomes and run plan. Original
files and hashes are retained as inputs. The layer is not a new relevance-label,
QA, admission, technical-debt or publication authority.

## Historical measurements and missing configurations

All34questions have compatible historical retrieval and M8 observations:

- Original29: BM25/vector/hybrid Top10; Recall@1/3/5/10, MRR and parent-group
  coverage; actual M8 assembly at4K/8K/16K/32K BGE budgets.
- Frozen15: saved strict-witness RRF10/20/30 and native/intersection/supplementation
  comparisons; actual M8 experiments through128K. The Stage1processing-order arm
  retains its private-adapter qualification; it is not production-equivalent M8.
- The separately sealed Q02/Q06holdout adds its existing nativeTop50, full saved
  RRF metadata, RRF10/20, intersection stages and full-union comparisons.

Historical M9 direct-positive-group hits use its existing overlap definition. The
later15-question comparisons use strict OR/joint-AND witnesses. These methods are
shown explicitly, not silently pooled into a new score. Parent discovery, direct
witnesses and actual complete-parent delivery remain separate. M9 is an offline
framework, not an extra runtime stage.

Only15questions have the RRF30/128K evidence-delivery measurement. The other19show
`NOT_MEASURED — M8 EXPERIMENT NOT AVAILABLE` for that target configuration while
retaining their actual historical M9 M8 measurements. A passing Top10retrieval
result cannot become an inferred128Kdelivery pass. A valid package or nearest
neighbors for unsupported controls do not establish answer support.

CohortC historical hybrid RRF10is complete at parent-group level for14/16questions,
covering16/18required groups. M9-Q07andM9-Q26are incomplete. M9-Q08has complete
parent-group discovery but only2/3equivalence-aware known-positive chunk-target
recall. The cohort is not uniformly “easy.” Full per-question values remain in the
reconciliation report and dashboard.

Precision remains unavailable because judgments are known-positive, not exhaustive.
Unlabeled candidates are unknown; cited-parent utilization is not precision. BGE
budget units remain distinct from generator tokens. Independent semantic correctness,
faithfulness, completeness and abstention judgment remain pending review.

## Dashboard behavior

The expanded quality page has cohort, generation-status, evaluation-availability
and answerability filters. One question selector controls all three tabs; all
question/detail/measurement tables retain cohort identity. Empty filter combinations
show an availability message instead of selecting a different unauthorized question.

The default journey is the unchanged experimental RRF30/128K configuration. Historical
retrieval/M8 selectors inspect other recorded configurations separately. Generation
attempts retain their own exact model, prompt, package and cost provenance. No
historical configuration becomes a new default or a fresh source-authorization token.

The funded Q05answer, token/cache/reasoning usage, latency, cost and qualification
caveat are reused unchanged. Other33questions are NOT_RUN unless a new compatible
sealed result is discovered. Failed attempts remain distinct. Post-checked counts
include indeterminate deterministic checks, not independently validated answers.
An ABSTAINED declaration is not automatically correct abstention; an ANSWERED
declaration is not proof of evidence support.

Source-free registered artifact receipts are reused for drill-down. Unknown query
references never open arbitrary files. No full parent documents, publisher passages,
prompts, keys or environment files are served. The actual model answer is inert text.
Refresh reads/hashes records only; it never executes an evaluation script, retriever,
model, M8 assembler or provider call.

## Future generation / validation artifact compatibility

New completed results can use the existing `quality-generation-experiment-1.0`
manifest with `status=COMPLETED_SEALED`, exact canonical `question_id`, bound `files`
and the additional `expanded_benchmark_manifest_sha256`. Retain the unchanged
`dataset_freeze_manifest_sha256` as an upstream source-chain binding required by
the existing normalizer. The expanded hash supplies actual34-question membership;
this does not assert cohortC/Dwere members of the original15-question freeze.

Required bound files are:

- `M7_RESULT.json`: existing candidate contract, exact question hash and explicit
  hybrid Top30/depth50/RRF60configuration, accepted release/index bindings.
- `PREPARATION_AUDIT.json`: existing source-free public gate audit, live M8 validation,
  exact question/request/M7/M8identities, authorized included UnitIDs, parent counts,
  BGE token budget, source selections and prompt/schema versions.
- `GENERATION_AUDIT.json`: existing `generation-result-1.0`, matching package/neutral
  request/model settings, official exact request-token receipt and context fit,
  measured usage and separately versioned cost telemetry.
- `GENERATED_RESPONSE.json`: existing unchanged response2shape/reference relationships.

The adapter reuses existing M7transport compatibility checks and the current telemetry
normalizer. It does not reopen source parents on refresh or claim that receipts
replace fresh invocation-time source validation. Unsupported or malformed artifacts
are excluded; no new result is manufactured. Unknown configurations require a
reviewed adapter instead of silent joining. Duplicate provider-response identities
are not counted twice; historical attempts remain accessible.

New post-validation manifests retain the existing deterministic schema and add the
expanded manifest hash. Response-file and M8package hashes must match a completed
attempt. Unknown/unqualified semantic certificates are rejected; accepted responses
retain PENDING_REVIEW or UNAVAILABLE semantic status. No new scoring methodology or
semantic evaluator is implemented. Existing public `PostGenerationValidator` remains
unchanged and reusable; its old Q05-specific offline CLI does not become an automatic
34-question executor.

## Run-plan readiness and owner checkpoint

`GENERATION_RUN_PLAN.json` deterministically lists every question, cohort/text hash,
source-label provenance, candidate availability, M8requirements, current unchanged
Luna/v2.1/schema2settings, result locations and explicit blockers. It authorizes no
live execution and supplies no fabricated token/cost estimate.

NativeTop50/full RRFmetadata is available for17questions (frozen15plusQ02/Q06holdout).
The other17lack those target inputs in the inspected seals; separate retrieval
execution authorization is needed to fill that gap. Q02/Q06still require an audited
accepted M7envelope, not merely a list of ranks. Target M8measurements are missing
for19questions. All historical parent packages must be freshly reconstructed and
validated before a separately authorized request; report hashes alone are insufficient.
Q05has a prior successful attempt and is skipped unless explicitly reauthorized.

Each future request requires exact generator-token/context/output-reserve/safety-margin
qualification, current applicable pricing/cost envelope, explicit source-transfer and
paid-call approval, a durable one-shot marker and disabled retries/fallback. The old
Q05v2token count cannot qualify another question or the changed v2.1prompt. The fixed
4096output reserve/1024margin and model/pricing registries remain unchanged. New
post-generation results need deterministic checks and separate semantic review.

The dashboard is ready to observe compatible future runs. The benchmark is not
currently executable as an automatically authorized batch. Stop for owner review.
