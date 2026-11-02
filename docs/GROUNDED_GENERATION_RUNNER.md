# Grounded Generation Runner v1 — build awaiting owner review

## Stage-level latency instrumentation — pending owner review

New mock and future separately authorized live executions publish an additive,
sealed `STAGE_TIMINGS.json`. See [timing definitions and boundaries](GENERATION_STAGE_TIMINGS.md).
Historical results remain unchanged and show `NOT_MEASURED`. Instrumentation does
not add retrieval, validation, provider calls or retries. One M9-Q01 mock is
authorized for this instrumentation task; the full benchmark and live execution
remain unauthorized.

The runner orchestrates existing Preflight Suite v1, M7 input validation, live M8
complete-parent assembly, prompt v2.1/schema 2.0, `GenerationService`, pricing and
`PostGenerationValidator`. It changes no retrieval, evidence, prompt or model defaults.

## Offline commands authorized for this build

Run from the repository root with the existing generation environment:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner dry-run --pending-generation
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner mock --pending-generation
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner mock --question R03 M9-Q27
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner dry-run --cohort A B
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner mock --question M9-Q01 --scenario api-failure
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner mock --question M9-Q01 --scenario schema-error
```

`--pending-generation` selects the full pending inventory (currently 33).
`--question` selects exact IDs; `--cohort A B C D` selects pending questions in those
cohorts. Q05 is excluded even for cohort selection, and explicitly requesting it fails.
Later verified successful historical generations are excluded through existing telemetry.
No current build grants live execution permission.

`dry-run` verifies the sealed preflight, all bound source/configuration files,
model profile, context limits, saved exact token receipt and current price arithmetic.
It writes a plan and readiness matrix. It does **not** freshly reconstruct a prompt,
refresh account access or claim a fresh provider qualification.

`mock` additionally reconstructs and validates actual M8 packages, prepares the
unchanged prompt, requires exact equivalence to sealed request recipes and calls
existing `GenerationService.generate` with an **owned in-memory offline adapter**.
Its metadata/count functions replay saved observations; its synthetic responses,
usage and costs are **test fixtures**, never real benchmark answers or charges.
The default fixture abstains for every question, deliberately without looking at
answerability or relevance labels. This tests orchestration, not abstention quality.
The deterministic post-validator runs only on structurally valid fixture responses.
API-failure/schema-error fixtures exercise failure handling without an SDK or network.
Sockets are blocked for the complete offline command, and no `.env` is read.
Only `MOCK_ATTEMPT.json` is created by mock executions; dry runs create no attempts.

## Cost and single-attempt safeguards

Default per-question ceiling: **USD 0.03**. Default aggregate estimated ceiling:
**USD 1.00**. Both are configurable decimal strings (`--per-question-cap`,
`--aggregate-cap`). The full initial plan estimates USD 0.76430900 from the sealed
33-question provider token observations and unchanged pricing registry. This is
not an invoice, account balance, new measurement or execution authorization.

Planning rejects over-budget sets before creating a run. Before a future paid
send, fresh exact-count pricing must fit the question's reviewed estimate, its
individual ceiling and the remaining aggregate reservation. A failed/unknown
attempt keeps its reservation. Exclusive fsynced files and parent-directory fsync
precede generation; a crash after reservation cannot authorize a retry. No resume
or retry feature exists. An authorization is single-use across run IDs. After an
unknown billable outcome or invalid response/cost, a live run stops; unattempted
questions require a new explicit owner decision.

The current generation service performs one metadata call, one token-count call
and at most one generation call per question. Full future plan: **33 + 33 + at
most 33 calls**; retries, fallback, tools and background batches are disabled.
The transport independently limits each exact endpoint/body to one attempt,
uses SDK and HTTP retry count zero, rejects redirects and other hosts/endpoints.
See [official SDK retry documentation](https://developers.openai.com/api/reference/python).

## Future live CLI — NOT authorized now

Only after code review and a separate explicit owner authorization:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner live --pending-generation --owner-authorization workspace/<owner-approved-file>.json --authorization-sha <sha256> --execute-approved-live --per-question-cap 0.03 --aggregate-cap 1.00
```

The owner attestation must use `grounded-generation-authorization-1.0` and bind:

- Exact `plan_sha256` (including question set, date, caps and preflight hash).
- `question_ids`, in the plan's exact deterministic order.
- `preflight_sha256`.
- Current `implementation_bindings`: SHA-256 of every top-level runner `.py` file.
- `aggregate_cap_usd` and `per_question_caps_usd`, exactly matching the plan.
- `owner_statement` recording the actual separate owner approval.
- Explicit booleans `allow_paid_inference` and `allow_source_transfer`.
- `maximum_generation_requests_per_question: 1`.
- Timezone-aware future `expires_at`.

No approval file or live attempt marker was created by this build. A local owner
attestation is an audit mechanism, not a cryptographic signature. Do not fabricate
an approval statement. The attestation hash is reserved exclusively before any
live provider access, so it cannot be reused after a crash or new run ID.

Before live execution, the runner revalidates all current preflight dependencies,
pricing dates, M7 query bindings, source publication bytes, complete M8 assembly,
request identity and transfer policy. Existing `GenerationService` then refreshes
model access/token count/context/cost and validates M8 again before invoking.
Changed token counts require new qualification/review; no silent substitution.

## Storage and dashboard

Each CLI invocation creates a unique private `data/evals/generation-runner/<run>/`
with source-free PLAN/START, per-question RESULT/local-audit records, RESULTS and
MANIFEST. Directories are 0700, files 0600, exclusive-created and Git-ignored.
Runtime evidence remains in memory; responses may contain source quotations and
remain private. Public dashboards show compact telemetry and answer text, never
full evidence packages, prompts, quote payloads, keys or arbitrary file paths.

The canonical launcher remains `apps/master_dashboard/canonical.py` on port 8514.
Its additive navigation delegates existing pages unchanged and adds **Grounded
Generation Runner**, a read-only configuration/readiness/mock-results/history view.
It discovers sealed compatible run records on refresh. Mock attempts are never
counted as successful benchmark generation. Future live history uses the same
reader; previous Q05 and all existing telemetry remain separately intact.
No dashboard action runs M8, provider methods or runner execution.

Historical canonical launcher bytes are retained in the private review package;
its two-line navigation import/docstring update is the only existing source change.
Old `app.py`, `expanded.py`, `coverage.py`, `preflight.py`, existing views, and all
accepted M0–M9 contracts are unchanged. This module adds navigation only; it does
not replace any existing dashboard page or telemetry authority.

## Validation boundaries

Post-generation checks reuse authoritative schema, Unit ID, source-only exact
quotation, native citation and qualification validators. Unclear qualification
applicability stays indeterminate. Semantic correctness/completeness stays pending
independent review. No automatic answer repair, regeneration or gold-label access
is added to runtime decisions. Partial evidence is permitted; unsupported controls
receive no benchmark expected-outcome instructions.

Run focused tests using the existing environments:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m pytest tools/generation_runner/tests/test_controls.py tools/generation_runner/tests/test_plan.py
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m pytest tools/generation_runner/tests/test_ui.py
```

The owner review package under `data/evals/generation-runner-reviews/v1/` records
actual executed checks, preservation hashes and run identities. Passing mocks
cannot qualify real provider schema responses or establish answer quality.
