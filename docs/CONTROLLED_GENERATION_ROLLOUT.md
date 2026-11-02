# Controlled generation rollout — prepared, not authorized to execute

Date: October 28, 2026. Owner-authorized preparation only. The existing
`tools.generation_runner` remains the sole execution runner. No provider calls,
generation, live attempt markers or authorization-use records are permitted by
this preparation task.

Review package: `data/evals/generation-rollout/v1/`. It contains three exact runner
plans, three deliberately invalid authorization templates, question-level projected
costs and request identities, Q04 local validation and verification/preservation receipts.
See `REPORT.md`, `ROLLOUT.json`, `COMMANDS.md` and `MANIFEST.json` there.

| Stage | Exact selection | Requests at most | Projected stage ceiling USD |
|---|---|---:|---:|
| Canary | M9-Q04 | 1 | 0.02355575 |
| Pilot | M9-Q01, M9-Q09, M9-Q27, R03 | 4 | 0.09480975 |
| Remaining | Manifest-derived remaining IDs in PLAN.json | 28 | 0.64594350 |
| Combined | 33 distinct pending questions; historical Q05 excluded | 33 | 0.76430900 |

The pilot order is the existing runner's lexicographic order, not a newly defined
execution order. The canary and pilot require owner acceptance before authorizing
the next stage. No stage is currently approved for execution. These estimates reuse
sealed provider counts and locally date-valid pricing, not fresh model access or
provider token-count observations. Maximum output reservation is 4,096 tokens,
safety margin 1,024, prompt v2.1, response schema 2.0, unchanged RRF30/M8 128K.

## Before any separately authorized execution

1. Reconcile successful generations **and unknown/failed billable attempts** across
   historical generation artifacts, sealed runner results and unsealed durable markers.
   A schema/qualification issue never authorizes another generation request.
2. Review the previous stage's actual response, citations, quotations, qualifications,
   usage, estimated cost, timing receipt and unresolved independent semantic review.
3. Rebuild the plan through existing `build_plan` and require byte/logical equivalence
   to the reviewed plan. Plan identity includes its creation date. A changed date,
   source, implementation, request, profile or pricing requires a new reviewed plan;
   never edit a sealed plan or backdate execution.
4. Verify current source/M7 bindings, fresh M8 assembly, exact recipe/request hash,
   source-transfer permission, model access, fresh input count, context and price
   through the existing live workflow, only after separate approval of provider access.
5. Complete a **new** owner file under `workspace/owner-approvals/`, using the existing
   `grounded-generation-authorization-1.0` contract. Record the actual owner statement,
   both explicit permissions and a short future timezone-aware expiration. Bind exact
   question order, logical plan SHA, preflight SHA, every runner implementation hash,
   stage aggregate cap and per-question caps. Hash the completed file for the CLI.

Templates have an empty statement, false permissions and an expired timestamp.
They are deliberately rejected by the existing authorizer. Do not pass a template
to live execution or interpret this guide as approval. No approved authorization,
signature or execution-consumption marker is created during preparation.

## Spending and duplicate boundaries

Per-question ceiling remains USD 0.03. Each stage's aggregate cap equals its sum of
reviewed question estimates, so the three disjoint stages together reserve no more
than USD 0.76430900, below the USD 1.00 owner ceiling. Costs cannot silently grow:
the existing runner also binds each question to its reviewed estimate. Failed or
unknown outcomes retain reservations. No retries, fallback or automatic repair.

**Existing limitation:** Budget and attempt admission are scoped to a run; the
single-use authorization is exclusive across run IDs, but a different authorization
is not a global cross-stage budget ledger. The legacy `completed_questions` reader
does not itself ingest new runner live results. This task does not change that
implementation. The separate owner review must reconcile all live results/markers,
exclude prior attempts and successes, preserve stage caps, and refuse duplicate or
overlapping reauthorization. Plan partition tests establish disjoint planned sets;
they do not prove global duplicate prevention against arbitrary new approvals.

## Read-only dashboard

Canonical entry: `apps/master_dashboard/canonical.py`, port 8514. The Grounded
Generation Runner page includes a sealed rollout-readiness section, stage status,
question cohorts, historical evidence completeness, planned costs and future real
outcome/timing fields. Existing run history supplies response/usage/validation details.
No live buttons exist. Refresh only reads and verifies artifacts.

`tools/generation_rollout` contains planning composition and read-only telemetry,
not another generation runner. Historical stage timings and mock results remain
distinct from real results. Semantic correctness and qualification applicability
remain separate review questions; citations/schema success alone cannot certify them.

STOP for owner review. The next possible action requires separate explicit approval
of exactly one M9-Q04 canary and its current reviewed plan/source-transfer/cost bounds.
