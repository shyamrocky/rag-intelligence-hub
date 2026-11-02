# RAG Preflight Suite v1

Owner-authorized bounded M10 implementation, October 28, 2026. Implementation and
measured results require owner review. This suite never generates answers and
never changes accepted M7/M8, prompt, pricing, model or production defaults.

## Reusable execution

From the project root, use the existing locked generation environment:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.preflight_suite local-check --pending-generation
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.preflight_suite local-check --all
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.preflight_suite local-check --question R01 R02
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.preflight_suite local-check --cohort A B
```

Each invocation creates an exclusive UUID-suffixed, dated directory under
`data/evals/preflight-suite/`. Do not rerun a completed historical experiment merely
to inspect it. Cohorts and pending-generation selection come from verified existing
identities/measurements. Failed attempts are not successful generations.

Only with explicit owner authorization for the selected questions and full source
transfer to OpenAI:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.preflight_suite model-preflight --question R01 R02 --local-manifest data/evals/preflight-suite/<local-run>/MANIFEST.json --authorize-transfer '<explicit owner authorization reference for this exact question set>'
```

An authorization reference is an operator attestation, not a digital signature or
a new source-admission authority. The CLI cannot grant permission on its own.
`model-preflight` rejects questions without successful, sealed local receipts;
it reopens sources, rebuilds through trusted modules, and compares the exact
reconstruction recipe and request hash before provider access. All dependencies,
including prompt/schema, source/index bindings, model/profile, settings, pricing
and suite implementation are hash-bound. A changed dependency requires a new
local run. Expired model/pricing reviews fail closed, without changing registry
values or backdating the qualification date.

## Trusted modules reused

- Accepted M7 envelopes and `validate_candidates`: no retrieval or ranking rerun.
- `EvidenceService.assemble` and the live public `validate` path: complete-parent
  authorization, source/publication bindings, exact BGE budget and qualifications.
- Current `PromptAssemblyGate.prepare`: v2.1 / response 2.0, exact original question,
  unchanged full evidence and separate message trust boundaries.
- Existing `wire_request` and `GenerationService.dry_run`: model metadata, exact
  Responses input-token count, context/output reserve/margin and Decimal pricing.
- Existing artifact Store and Master Dashboard/Candidate–Parent Explorer.

Local validity is distinct from model qualification. The model-independent prompt
gate continues to report BLOCKED_CONFIGURATION pending generator qualification;
a separate successful local receipt means assembled, source-verified request,
not semantic completeness or model readiness. Partial M8 evidence may be valid.
An empty package remains blocked by the existing grounded-prompt contract.

Fixed experiment: hybrid native depth50 / RRF60 / Top30; M8 128000 **BGE** tokens;
OpenAI gpt-6-luna; prompt v2.1; response2.0; output4096; safety1024. The qualified
model is a moving alias, not an immutable snapshot. Token-count endpoint acceptance
and a reviewed capability profile do not establish generated-response schema
compliance, semantic answer support or actual billed cost.

## Packages and security

Per question: REQUEST_PACKAGE.json, LOCAL_VALIDATION.json, MODEL_PREFLIGHT.json,
PROVIDER_CALLS.json and QUESTION_MANIFEST.json. Request packages are **source-free,
verified deterministic reconstruction recipes**, not persisted publisher prompts.
They retain exact M7/M8/request/template/schema/settings/profile identities. Full
source evidence exists only in trusted process memory while live validation and
prompt construction run. Directories are mode0700, files0600, gitignored under
data/. No environment values, provider error bodies, prompt passages, answer labels
or expected unsupported outcomes appear in telemetry. Gold labels never influence
runtime preparation, ordering or readiness. Independent historic completeness
annotations belong to offline reporting only.

The count-only adapter forbids invocation. Its HTTP transport independently allows
only GET /v1/models/gpt-6-luna and POST /v1/responses/input_tokens, with exact content
hash verification, fixed HTTPS host, no redirects, one attempt each per question,
SDK/transport retries0 and durable pre-send markers. Every other endpoint,
including POST /v1/responses, is rejected. No fallback, tools or batches exist.
A provider failure is recorded without retry; safe independent questions may continue.

OPENAI_API_KEY is read only in explicitly authorized provider mode, from the
process environment or the local .env key assignment. It is never printed,
hashed, placed in artifacts or sourced as shell code. Existing source-use
restrictions travel unchanged in complete evidence. Explicit native transfer
prohibitions fail closed; owner permission is not a waiver of source restrictions.

## Dashboard

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/master_dashboard/preflight.py --server.address 127.0.0.1 --server.port 8514 --server.headless true --browser.gatherUsageStats false
```

The additive current Master entry preserves all previous entries, routes and the
exact Candidate–Parent Explorer. It adds RAG Preflight Suite and a compact linked
question-level readiness history. Refresh verifies/discovers sealed compatible
runs; it never imports execution code into its data adapter, reconstructs evidence,
reads credentials or calls providers. CLI examples are descriptive only; no active
execution buttons are provided. The run's hash-bound source-free metadata supports
history comparisons of prompt/request hashes, tokens, parent counts, headroom,
cost ceilings and status changes. Malformed/unsealed/incompatible runs are rejected.

## Verification and stop boundary

Run new synthetic/real-source mock-provider tests in the existing generation
runtime, and Streamlit AppTest in its existing dashboard runtime. Provider-negative
controls use mocks only. Local replay tests compare real request hashes and protect
source obligations. Root scaffold/lint/smoke checks remain separate from full
historical multi-environment gates. See the private review packet for actual
commands, passes, limitations and preservation receipts.

A model-qualified request candidate is **not authorization for generation** and
is not permanently fresh. Before any future paid request, separately authorize
question IDs/source transfer/spending cap, then independently revalidate current
source validity, request hashes, model access, context limits and pricing/cost.
Never use old Q05 v2 counts for v2.1 or other questions. Q05 is excluded from the
first pending33 run; its successful/failed history remains unchanged.

The official [OpenAI token-counting guide](https://developers.openai.com/api/docs/guides/token-counting)
describes request input counting. The suite reuses the already accepted adapter;
no new API implementation or pricing assumptions were introduced.

### Changed-dependency history

The existing strict preflight reader rejects stale requests for current use.
The additive historical-observation view separately verifies immutable run payloads
and internal receipt hashes, while allowing old prompt/settings/pricing dependency
bindings to be unavailable. These records are explicitly
`HISTORICAL_NOT_CURRENTLY_QUALIFIED`; they never count as current qualification.
It retains observed tokens/costs under their original policy identity rather than
recomputing historical costs with current prices. Tampered or unsealed payloads
remain unavailable. This read-only display adapter does not relax runner checks.
