# Configurable experimental OpenAI generation

October 27, 2026. Bounded integration and token/cost observability, pending owner
review. No paid inference, provider preflight or private evidence transmission was
executed. Accepted M0–M9, prompt v2/schema 2, default prompt entry point, RRF60,
production Top-10, M8 atomic reconstruction and frozen labels remain unchanged.

## Runtime and configuration

New isolated environment: `tools/generation/pyproject.toml` + `uv.lock`, Python 3.12,
OpenAI SDK 2.54.0 and existing compatible NumPy/PyMuPDF/Pydantic versions. All six
previous runtime locks/environments are preserved. Reconstruct the new environment
with `UV_CACHE_DIR=/private/tmp/rag-generation-uv-cache-v1 uv sync --project
tools/generation --locked`; private M8 evidence and existing chunking/tokenizer
runtime are still required. No generation model weights are downloaded.

`tools/generation/settings-v1.json` selects the provider/model, output reserve,
safety margin, reasoning effort, timeout, tier and cache lifetime. The default
model is gpt-6-luna. `model-profiles-v1.json` contains documented Luna and Terra
profiles; both still lack account/request qualification. These public aliases have
no verified dated snapshot in this review; the profile records that limitation.
Temperature is omitted because it was not qualified; this does not assert that
every model universally forbids it. No implicit fallback, tools, retry or router.

Default local-only Q05 dry run:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation.cli --question-id M9-Q05 --dry-run
```

Model switching without business-logic changes:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation.cli --model gpt-6.1-terra --question-id M9-Q05 --dry-run
```

This second model is a documented configuration alternative, not an account-qualified
or invoked replacement. Unsupported models block. Adding other models requires a
reviewed external profile/pricing policy; the library accepts an explicit registry.
Profile capacities are sourced from official model pages. The input bound is the
conservative total-context ceiling, not a separately documented provider input cap.
The full prompt, output reservation and margin must fit together.

## Source checks and readiness

`GenerationService` requires the real canonical PromptAssemblyGate. It calls
`validate_preparation` to revalidate M8 live and rebuild exact question/prompt bindings.
It translates the unchanged three messages into Responses input and uses the
unchanged response schema. The explicit annotation-only transformation
`openai-json-schema-annotations-only-1.0` removes $id/$schema; all validation
constraints and stricter Python relationship validators remain. OpenAI structured
output uses text.format with json_schema and strict=true. Request storage is false,
truncation disabled, and no tools are enabled.

The historical/model-independent prompt assembly receipt remains unchanged and
blocked. A **separate generation qualification envelope** can become READY only
after account model access and the exact provider request token count are checked,
context limits pass, and native source validation repeats. It never rewrites an
old audit or promotes structural authenticity into semantic sufficiency.

Default dry runs make no provider calls, even if a key exists. An authenticated
preflight requires `--provider-preflight`; sending the evidence to the provider's
request-token endpoint additionally requires `--allow-source-transfer`. Those flags
must only be used after owner authorization of that transmission. Set
OPENAI_API_KEY locally in the process environment; no dotenv loader is introduced.
Never put the key in chat, code, command arguments or receipts. Codex/ChatGPT
subscription credentials are not API credentials. Debug SDK logging and unapproved
base-URL overrides are blocked.

Exact counting uses the official Responses input_tokens endpoint with model, the
complete messages, response schema, reasoning configuration and truncation policy.
It includes model framing; neither BGE counts nor character estimates substitute.
Lacking credentials, request accounting remains unavailable. Merely inspecting
docs, finding a model in the catalog or passing mock tests does not qualify it.

## Live boundary

No live call is authorized by this delivery. Future explicit invocation requires
all three flags `--live --allow-paid-inference --allow-source-transfer`, successful
preflight and immediate source revalidation. It makes one responses.create call,
with SDK retries disabled. A successful dry run never invokes generation by itself.
There is no automatic model fallback or retrieval loop.

The CLI prints source-free audit metadata only. The Python GenerationResult.response
contains parsed sensitive answer/quotation content in trusted memory and is excluded
from repr. No full prompt/provider response is persisted by this implementation.
Structured parsing checks fields, status relationships and authorized Unit IDs;
it does not verify quotation fidelity, semantic entailment or factual correctness.
The status GENERATED_STRUCTURE_VALID means exactly that. Future grounded-answer
assessment remains separate.

## Usage and cost

The application-owned usage object is separate from grounded-response-2.0 and
never model-generated. It captures selected/returned model, inclusive input tokens,
cached reads, cache writes and 30m/12h breakdowns, inclusive output tokens, optional
reasoning detail, total tokens, measured API-call latency, response status and actual
processing tier. Raw SDK response JSON preserves types before validation; typed
SDK model coercion must not turn invalid booleans into valid token counts.

`pricing-v1.json` is a versioned configurable registry. It binds rates to model,
input/cache/write/output categories, long-context conditions, response tier, region
and effective dates. Its seven-day validity is an application review policy observed
on October 27, not a claim about the provider's original price-change date. Stale,
missing, ambiguous or unaccounted categories yield COST_UNAVAILABLE, never a guessed
total. `--pricing` selects a separately reviewed successor JSON policy.

Ordinary input is input_tokens minus cached reads minus cache writes. Cache writes
are partitioned by lifetime and charged once. Reasoning tokens are already part of
output_tokens and are not charged again. Use actual response tier, not the requested
tier, because processing may differ. Regional multipliers are supported in the
cost engine, but this adapter only targets the global endpoint. Unknown tiers or
other billable categories block totals. Missing reasoning detail alone does not
block output pricing when the inclusive output total is valid; a missing billable
write/read count does.

All money calculations use Decimal; JSON serializes USD amounts as decimal strings.
Actual-usage-based calculations are labeled ESTIMATED_API_COST, not invoice charges.
No taxes, credits, currency conversion or negotiated discounts are assumed. An API
failure with no usage reports unknown cost and possible billing, not a zero charge.

Dry-run cost estimates require a verified generator input count and use the full
configured output reservation. The estimate conservatively uses the maximum input
category rate, including either cache lifetime. It does not invent actual output
usage. After invocation, measured usage replaces the empty actual-usage fields;
separate diagnostics compare input count, unused output reserve, and observed
estimated cost versus the prior estimated maximum. Integrity/JSON failure does
not discard billable usage that was actually returned.

The actual Q05 dry run is BLOCKED_CONFIGURATION / OPENAI_API_KEY_MISSING. Its 30
candidates and 17 complete parents consume 126,720 BGE evidence tokens, but generator
tokens, actual output/usage, estimated maximum cost and actual-usage cost are all
unavailable. No answer was generated. Read the private integration report under
`data/evals/generation/integration-v1/`.

## Official references

- [Luna capabilities and pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Terra capabilities and pricing](https://developers.openai.com/api/docs/models/gpt-6.1-terra)
- [Request-token counting](https://developers.openai.com/api/docs/guides/token-counting)
- [Caching usage and write-lifetime billing](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Pricing](https://developers.openai.com/api/docs/pricing)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Processing tier behavior](https://developers.openai.com/api/docs/guides/fast-mode)

These establish documented behavior, not account access or a completed live test.
