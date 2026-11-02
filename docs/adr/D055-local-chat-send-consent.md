# D055 — Local Chat Send Consent and Persistent Spending Controls

- **Date:** 2026-11-01 (America/Los_Angeles).
- **Status:** Accepted architectural direction and bounded implementation scope; technical delivery awaits owner review. Real activation and provider execution are not authorized by implementation approval.

## Owner-approved amendment — default Chat, 2026-11-02

**Decision:** Normal localhost Chat is ready by default under the reviewed policy.
An explicit Send authorizes the exact submitted question's verified source transfer,
preflight and at most one paid answer within $0.03 per question and the persistent
$1.00 total Bot ceiling. Separate enablement is no longer a normal Chat prerequisite.

**Rationale:** Selecting Chat must provide the expected type → Send → answer or
clear stop-reason workflow. The previous extra gate caused confusing off states.
**Alternatives:** Hide only the off message (insufficient backend correction); keep
two normal-chat approval steps (unnecessary friction); remove integrity/spending
controls (rejected). Reuse the native runner and exact-question receipt contract.

**Status:** Explicit owner authorization for scoped implementation and offline
verification; implementation/test evidence is separate from this architectural
approval. No live test or provider call is authorized by the development task.
Old enable/revoke records are preserved under their original contract, while the
versioned successor records the new approval basis without fabricating activation.
Strict source/request/trust/cost/attempt checks, no retries/fallback, optional triage,
disabled developer-mode composer and Human Review remain unchanged.

The original decision text below is historical; the amendment supersedes only its
separate-enable prerequisite for normal Chat.

## Context

The exact-question Bot canary demonstrated the native end-to-end path. Preparing a
new trust policy plus separate preflight/generation approval forms per question is
unnecessary friction for the local educational chat POC. Native source authority,
model/context qualification, spending, duplicate, raw-output and review safeguards
must remain effective. Chat transcripts and response caches remain out of scope.

## Decision

Use one allowlisted, versioned localhost chat policy. Explicit owner enablement and
an exact Send receipt jointly authorize each new question under fixed configuration,
$0.03 per-question and $1.00 persistent cumulative Bot ceilings. The total includes
prior Bot reservations and is separate from the historical benchmark budget. No
automatic reservation release, retry, fallback or semantic approval is introduced.

Reuse existing retrieval, complete-parent evidence assembly, prompt v2.2, schema
2.0, model configuration, token/count preflight, GenerationService, native single-use
consent and durable attempt records. Dynamic plan admission requires independent
verification of the current enablement, exact submitted question, source/request
and qualification bindings. A caller-supplied plan hash alone grants no scope.

Show concise, distinct stop messages and retain source-free diagnostics. Output
contract problems remain observable in Human Review with available protected raw
output. Partial evidence is not automatically a hard failure. Invalid sources and
citations remain technical failures. Human semantic acceptance is never inferred.

## Alternatives and consequences

Retaining per-question release preparation offers narrow experimental control but
poor normal-chat usability. Removing budget/trust gates would lose essential safety.
A second runner would duplicate the tested pipeline. The selected approach adds a
small native consent/orchestration layer and persistent receipts, with no new
infrastructure, model, dependency, cache or source processing algorithm.

One-time enablement is a local owner attestation, not cryptographic authentication.
It must be explicit and revocable. New chat, restart or re-enablement cannot reset
spending. Unknown prior billing or incomplete admission blocks subsequent paid work.
Updated code/configuration requires reviewed trust migration and new enablement.

## Implementation and auditability

See [commands and boundaries](../RAG_BOT_RUNTIME.md), native
`tools/generation_runner/bot_chat.py`, existing native trust/preservation and consent
contracts, and read-only `tools/bot_runtime/chat_records.py`. Historical exact-request
controls and all original canary/benchmark/owner-review records remain preserved.
Scoped offline tests use synthetic owners and providers; they do not establish
provider availability or real answer quality. Live activation is a separate owner
checkpoint after implementation review.
