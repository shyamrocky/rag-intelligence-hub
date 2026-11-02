## Compact Chat presentation

The Bot heading places its smaller icon beside “What would you like to explore?”
with one subtitle: “Ask a question about RAG. We’ll find and verify the evidence
before answering.” The three example cards remain.

Controls appear in this order: collapsed **Guidance & limits**, collapsed
**Developer settings**, then **New chat**. Guidance holds current spending limits,
remaining funds after reservations, the unchanged Send/source-transfer disclosure,
provider-call/retry limits, private-record/no-cache information and the note that
preparing verified evidence can take a couple of minutes. Serious configuration or
spending-check warnings remain visible. The normal Chat mode label is hidden;
developer modes still identify themselves and disable the main composer.

The submitted question remains visible above its processing status/Bot reference
and answer. A visible instruction says to click **New chat** before another
question; each starts fresh. This is session presentation, not saved conversation
history. Existing execution records, native consent, budgets and review safeguards
are unchanged. UI refresh or expanding Guidance does not submit work.

## Default Chat — Send is the exact-request approval

At <http://127.0.0.1:8516>, **Chat (Default)** is ready without a separate
Enable live chat step. Type a question and press **Send**. The page acknowledges
receipt, shows processing, and displays the answer or a clear recorded stop reason.

The owner-approved, allowlisted `EXPLICIT_SEND_WITHOUT_ENABLEMENT` contract binds
each explicit Send to its registered question, current trust manifest, configuration
and source-transfer disclosure. It permits automatic native evidence preparation,
model/token/context/cost checks and at most one paid response within **$0.03 per
question / $1.00 total Bot cap**. The existing maximum of two metadata and two
count checks is unchanged. There are no automatic retries or fallback models.
Opening the page, selecting Chat or restoring a draft grants no per-request consent
and executes no pipeline stage. Implementation verification itself submits no question.

The total includes conservative existing Bot reservations; New chat, restart and
mode changes never reset it. Budget, duplicate, unknown billing, source, request-hash,
freshness, model, pricing and context checks still fail closed in the native backend.
Completion does not establish semantic correctness. Raw diagnostics, usage, timings
and Human Review handoff retain their existing protected storage and behavior.

**Developer settings** contains one mutually exclusive Request mode selector:
Chat, Request Approvals / Triage, or Offline Simulation. Both developer modes disable
the main question composer. Triage retains optional exact-request tools; normal Chat
does not require them. The unchanged backend simulation commands remain available.
Drafts survive mode changes without automatic submission; New chat clears only the
session display. No chat-history database or answer cache is introduced.

Historical enable/disable events remain immutable records of the earlier contract.
They are not rewritten or resurrected to manufacture new approval. The owner-approved
successor replaces that contract for normal Chat: exact Send is now the required
request approval. Old policies and their historical results retain their original
verification path. Future code/configuration changes still require reviewed trust
migration; a self-supplied policy hash cannot grant authority.

Read-only status and the existing backend entry point:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot chat-status
# Explicit future submission for a NEW registered question; can contact OpenAI.
# Never run this as an offline verification command or automatic test.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot chat --question-id <NEW_BOT_ID> --confirm-exact-request
```

## Historical enablement contract (superseded for normal Chat)

The following records the previous one-time-enable design. Its controls and receipts
remain available for historical verification; they are not normal Chat prerequisites.

## Simple localhost live chat — implemented, activation pending

A reviewed native chat policy supports one-time explicit owner enablement. Once
enabled, **Send** authorizes only that submitted Bot question's source transfer,
token/cost qualification and at most one generation request. The fixed per-question
ceiling is **$0.03** and the owner-selected persistent total Bot ceiling is **$1.00**.
The total includes conservative reservations for previous Bot requests, including
the earlier exact-question canary; it does not reset with a new chat, restart or
re-enablement. Benchmark reservations retain their separate historical controls.
Reservations are conservative planning amounts, not billed charges, and failures
never automatically release them.

**This release does not enable live mode or grant real provider access.** After
owner review, the localhost **Enable live chat** form requires an explicit approval
statement and confirmation. Turn off live chat revokes further processing under
that enablement. Code/configuration or trust changes require new reviewed enablement.
When chat is off, existing local preparation and synthetic simulation remain
available. The advanced exact-question approval workflow remains intact.

Send reuses the native local-check, source validation, prompt, model-preflight,
GenerationService, raw capture, deterministic validation and Human Review handoff.
The existing double qualification sequence permits at most two metadata and two
count requests plus one generation request per submission, with no retries/fallback.
Full authorized evidence is transmitted during provider counting as well as generation.
Fresh request/source/model/context/pricing checks, 900-second receipts, exclusive
single-use authorizations and durable generation-attempt markers remain enforced.
No benchmark ground truth is added to Bot questions or prompts.

Budget, context, source validation, no-evidence, duplicate, provider, unknown-billing,
capture and response-contract conditions produce concise user messages plus sealed,
source-free reason records. A response-contract failure retains protected output
for diagnostic Human Review; it does not become an approved answer. Partial evidence
alone does not block otherwise permitted requests. Missing model semantic review
remains pending. Neither completion nor a model declaration establishes correctness.

Controller and Send receipts are private under `data/runtime-chat/v1/`; native
stage artifacts retain their existing locations. Operational pages automatically
show chat stop findings with question, stage, attempted-generation state and known
or unknown cost. No question is admitted to frozen Offline Retrieval Evaluation.
Refresh/navigation never enables chat, dispatches a request or creates an approval.

Backend commands use the same native runner (not a second API implementation):

```sh
# Read status only.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot chat-status

# Future activation ONLY after explicit owner approval. The private file must
# contain the actual owner's statement; no template/example grants permission.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot activate-chat --owner-statement-file workspace/<OWNER_STATEMENT_FILE> --confirm-exact-request

# Future explicit Send for a NEW registered ID, after activation. This can contact
# OpenAI and generate one paid answer; NOT authorized by implementation approval.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot chat --question-id <NEW_BOT_ID> --confirm-exact-request

# Explicit local revocation; never auto-retry an interrupted request.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot disable-chat --owner-statement-file workspace/<OWNER_STATEMENT_FILE> --confirm-exact-request
```

For offline testing use the existing `bot mock` command or synthetic native-chat
regression tests. No real activation, credential read, provider call or paid execution
is needed for the tests. Failed submissions cannot be silently retried; each deliberate
new question has its own registration nonce and durable execution record.

Historical documentation below describes the earlier exact-question release.

---

# RAG Bot — local checks and offline simulation

The Bot UI and backend CLI use the **same native Generation Runner**.
Local checks and simulation are available; live qualification/execution require
separate, exact-question native policies and owner consent. No provider call is
authorized by implementation or by a generic Send click.
The 8516 page starts empty. Enable **offline simulation** to exercise a single turn;
**New chat** clears the display. Questions and execution diagnostics remain in private,
Git-ignored storage; conversation transcripts and application answer caches are not created.

## Backend commands

Write your question to a private UTF-8 file. Run from the project root:

```sh
# Register and run the owned offline simulation (no provider or real corpus search).
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot mock --question-file /private/tmp/my-rag-question.txt

# Optional fixture outcomes: answered, partial, abstained (default), schema-error,
# api-failure, empty-evidence. These are orchestration controls, not answer quality.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot mock --question-file /private/tmp/my-rag-question.txt --scenario partial

# Register only; stdout returns its BOT-000001-style reference.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot register --question-file /private/tmp/my-rag-question.txt

# Actual local retrieval/source reconstruction/prompt preparation; zero provider calls.
# Run only when local execution is intended/authorized, using the returned ID.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot local-check --question-id BOT-000001

# Read saved execution status without executing the pipeline.
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner bot inspect --question-id BOT-000001
```

Do not copy an example ID blindly. Use the ID returned by registration.
`--submission-id` accepts a 32-character lowercase hexadecimal nonce. Reusing it
with identical original text returns the same question; changed text fails closed.
One execution per question **per offline mode** is admitted. Interrupted submissions
are not automatically replayed. Register a deliberate new submission for a new run.
Local-check and mock claims are separate; a local check does not consume paid authority.
CLI output contains IDs/status references, not publisher evidence or API credentials.

## What is real versus simulated?

| Mode | Retrieval / evidence | Prompt | Model / token count | Validation |
| --- | --- | --- | --- | --- |
| local-check | Existing public hybrid search and whole-parent source-validated assembly | Current v2.2 gate, response schema 2.0 | Not called; not model-qualified | Source/request preparation only |
| mock | Owned synthetic service boundaries, not the actual corpus | Existing v2.2 gate | Existing OfflineAdapter and GenerationService; synthetic counts/usage | Existing parser, raw capture and deterministic validator; no semantic acceptance |

Configuration stays hybrid BM25 Top-50 + BGE Top-50, RRF k=60, maximum Top-30,
128,000 BGE evidence tokens, GPT-6 Luna identity, prompt v2.2/schema 2.0,
4,096 output reservation and 1,024 safety margin. Mock costs are simulations;
actual spending remains unavailable, with zero real requests. Current profile and
pricing validity are checked; an expired configuration blocks rather than being extended.

No-evidence local preparation returns **INSUFFICIENT_EVIDENCE**, not a fabricated
model ABSTAINED status. Nonempty retrieval does not establish answerability.
A mock answer does not establish real source integrity or semantic correctness.

## Records and dashboard plumbing

- `data/runtime-questions/v1/BOT-…/`: immutable original/canonical text and hashes.
- `data/runtime-executions/v1/bot-…/`: sealed stage records, protected request/evidence,
  raw-capture references, response/diagnostics and versioned stage timings.
- Existing `workspace/generation-response-captures/`: protected raw bodies.

Files are exclusive-created, private and hash-bound. Allocation and execution claims
use local locks; refresh cannot allocate IDs or dispatch work. Missing seals remain
**INCOMPLETE / RECOVERY_REQUIRED**. Malformed/tampered records are rejected explicitly.

Select **Bot questions** on Retrieval, Pre-Generation, Generation, Post-Generation
Evaluation or Human Review. Each uses one read-only projection with the same question,
attempt and request bindings. Questions, statuses, evidence-unit counts, exclusions,
actual saved timing and diagnostics remain visible. Protected raw inspection requires
an explicit checkbox and the existing direct-localhost check.

Bot questions are **UNASSESSED / UNLABELED**, not unsupported controls. They do not
enter frozen benchmark/cohort totals, known-positive recall or Offline Retrieval
Evaluation. Simulated results are diagnostic-only: Approve/Reject/Request Changes
are disabled. The existing benchmark Local POC and signed workflows remain unchanged.

## Native trust and the next owner checkpoint

The offline Bot path uses an exact allowlisted successor of the existing native
preservation baseline, including original source/index/prompt/model/pricing/review
bindings. Only the reviewed implementation additions/CLI dispatch change are migrated;
historical baselines and the exact transient Git-reference audit policy remain preserved.
No caller-selected policy/path/hash can enable paid execution.

**Live Bot execution is not activated.** The CLI now supports gated model-preflight
and live modes through the existing native runner, with no active Bot provider
allowlist or live scope in the implementation release. Activation requires a reviewed
exact-question policy and separate source-transfer/paid consent. Bot-specific
cumulative spending scope and provider-call limits must be explicitly approved. Benchmark authorizations,
unused reservations, mock buttons and Human Review decisions grant no Bot spending permission.
Mandatory fresh metadata/count/source/context/cost qualification and the existing
900-second receipt, single-use, durable-attempt, no-retry/no-fallback controls must
remain in force. This implementation creates no real authorization or live attempt.

Actual-corpus local canary, provider qualification and real Bot review decisions
remain separate execution checkpoints; offline fixtures do not establish those results.


## Controlled live integration — implemented, execution not authorized

The Bot displays: “Preparing a grounded answer can take a couple of minutes while
we find and verify the evidence.” Performance optimization remains deferred.

The live readiness expander reads **sealed exact-question preparation** under
`workspace/bot-authorizations/`. Nothing runs on refresh. It shows the question,
request limits and conservative cost ceilings before requiring the owner's explicit
statement and confirmation. Localhost is required. Model qualification and paid
generation have distinct forms/attestations; a count-only grant cannot authorize
answering. The UI and CLI share the same native gates.

Future operator sequence (all execution below is **NOT AUTHORIZED** by this release):

1. Preserve the existing real local-check manifest and registry reference.
2. Review/allowlist its exact provider-preflight context in a versioned native policy.
   No current Bot context is allowlisted. Do not reuse benchmark source-transfer permission.
3. Prepare an unsigned transfer-only template:
   `bot prepare-model-preflight --question-id <ID> --local-manifest <LOCAL_MANIFEST> --trust-manifest <APPROVED_MANIFEST> --trust-sha <SHA> --output workspace/bot-authorizations/<NEW_ID>`.
4. Owner confirms that preparation in the UI, or uses
   `bot issue-preflight-consent --question-id <ID> --preparation-manifest <MANIFEST> --preparation-sha <SHA> --owner-statement-file <PRIVATE_FILE> --confirm-exact-request`.
5. Execute `bot model-preflight --question-id <ID> --local-manifest <LOCAL_MANIFEST> --preflight-consent <CONSENT> --preflight-consent-sha <SHA>`.
   It allows at most one metadata and one exact token-count call, zero generation and
   zero retries. A consumed/interrupted preflight cannot silently repeat.
6. Review the qualified artifact, current prices and exact Bot spending scope. A
   successor native live policy must pin the plan contract, exact request/source
   hashes and Bot cumulative cap, while preserving the overall reservation ceiling.
7. Prepare unsigned native generation consent with
   `bot prepare-live --question-id <ID> --preflight-manifest <QUALIFIED_MANIFEST> --per-question-cap <OWNER_CAP> --aggregate-cap <OWNER_CAP> --trust-manifest <APPROVED_MANIFEST> --trust-sha <SHA> --output workspace/bot-authorizations/<NEW_ID>`.
   Caps have no implicit Bot allowance; the owner must accept them explicitly.
8. Owner confirms in the UI, or uses `bot issue-live-consent` with the same preparation/
   statement/confirmation flags. Then `bot live` accepts the exact question, qualified
   manifest, caps, `--owner-authorization`, `--authorization-sha` and
   `--execute-approved-live`. Fresh model/count/context/cost checks remain mandatory.

Use the existing `PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner`
prefix for each `bot` command. IDs/hashes above are placeholders, not usable permission.
Pending/unsigned files cannot execute. Approved attestations publish atomically and
remain bound to exact displayed bytes. Issuing permission never executes by itself.

Native generation retains the unchanged raw capture/parser, technical validator,
conservative reservations, durable single-use/attempt controls and no retry/fallback.
Metadata/count calls performed during initial qualification are separate from the
fresh metadata/count immediately before generation: **maximum two of each plus one
generation** for the complete authorized single-question sequence.

Native Bot results are discovered automatically in all operational pages. Accepted,
partial and abstained responses use the existing source-bound review preparation,
Local POC controls and optional signed workflow. Missing semantic assessments remain
INDETERMINATE/REVIEW_REQUIRED. Rejected output remains protected diagnostic triage,
not an approvable answer. Existing review locks and question/response/evidence/policy
identities prevent transfer or duplicate approval. Historical verdicts are preserved.

The qualification reader verifies the original source-transfer attestation, native
policy allowlist, request/token receipts and source artifacts. It does not treat old
qualification as permanent authority. File SHA-256 and canonical object identities
are stored separately; whitespace changes to artifact files are not silently ignored.

Provider counting reuses the existing adapter and documented
[Responses input-token counting endpoint](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens/methods/count).
No model availability, current prices or live request quality was verified online.

## Question entry and staged approvals

The 8516 chat input accepts a question by default. A submission registers its Bot ID
and runs **local-only evidence preparation** through the existing backend CLI.
This does not transmit evidence to OpenAI, read provider credentials, or generate
an answer. The offline-simulation toggle instead selects the existing synthetic
mock path. New chat starts a new display; earlier execution records remain intact.

After local preparation, the backend's `bot prepare-next --question-id <ID>
--output workspace/bot-authorizations/<NEW_ID>` resolves the next stage under the
**currently allowlisted native policy**. It prepares unsigned templates only.
It cannot allowlist a new question, publish a trust successor, approve itself,
retry a consumed stage, or turn benchmark budgets into Bot spending permission.
The same operation is available from the UI's **Prepare next approval step** button.

When exact scope is available, the Bot shows **Approve token/cost preflight**.
Only explicit source-transfer consent invokes that provider stage. Its saved
input tokens, context fit and conservative maximum cost are displayed. The next
unsigned generation preparation is then checked locally; **Approve generation**
requires a new, separate confirmation. No paid request follows automatically.
Execution references link to Retrieval, Generation and Human Review with the same
Bot question selected. Completed provider steps disappear from pending controls;
failed/interrupted stages remain non-retryable through this flow.

The current release still has **no active Bot provider or paid scope**. Therefore
an arbitrary typed question can finish local preparation and show
**POLICY_REVIEW_REQUIRED**. This is an honest execution boundary, not permission
to bypass the exact-question native policy. Real provider qualification and one
capped live canary remain separately authorized checkpoints.

Backend test coverage includes `mock` and the actual native `live` path exercised
with synthetic provider adapters in disposable test roots. There is no special
`mock-live` CLI mode and no test needs a real API key or provider call.

## End-to-end request progress and failure diagnostics

New Bot executions carry an append-only **Request progress** trace. It observes
existing operations; it does not rank candidates, assemble extra evidence, authorize
provider access, evaluate semantics or retry requests. The Bot and operational
pages show stage status and measured seconds. Source/service initialization and
encode/vector/BM25 worker requests are identified separately. Existing result
receipts continue to supply candidate counts, evidence inclusion/exclusion reasons,
token budgets, model usage/cost, raw-response references and Human Review status.

Trace events contain the Bot/question reference, execution ID, timestamps, stage,
operation, status, elapsed time and a previous-event hash. Complete trace receipts
use `REQUEST_TRACE/SEAL.json`; the containing execution manifest binds the receipt
and event hashes. Unsealed observations are labeled **progress**, never accepted
as completed execution. Stage completion means an operation returned; validation
and owner acceptance still come from their original independent receipts.

Normal local/provider submissions update the progress display while the same
single backend process runs. Refresh only reads observations and never executes
a stage. The existing end-to-end timing receipt remains the authority for totals;
nested trace durations overlap and must not be summed.

**Technical details — trace and protected failure locations** exposes verified
observations with an explicit localhost checkbox. Failure records retain exception
class, recognized safe internal error codes, and file/function/line stack locations.
Arguments, local variables, source lines, environment values, credentials, full
prompts and arbitrary provider/publisher exception text are not logged. Untrusted
exception text is represented by a digest and an omission status. Existing protected
raw-response capture remains the path for original provider output.

UI/CLI dispatch diagnostics are private under `workspace/bot-dispatch-traces/`;
they are transport observations, not generation/consent authority. Temporary logging
writes use private spool files and exclusive atomic publication. A logging failure
cannot overwrite or corrupt an accepted execution result, grant permission, trigger
a retry, or claim that a complete trace exists. Missing/incomplete trace evidence
is reported explicitly.

Historical results without traces remain readable using saved timings. In particular,
BOT-000003 retains its original local retrieval failure and generic ValueError.
This logging release cannot reconstruct that missing historical exception, does
not repair its unknown cause, and does not rerun or unlock it. A future deliberate
local test needs a new submission under the existing controls; no OpenAI activity
is authorized by logging implementation.

## Discarded failed local submissions

An explicit owner instruction can mark a sealed, failed/blocked **local-check**
with zero provider calls as `DISCARDED`. A separate immutable, hash-bound record
under `data/runtime-dispositions/v1/<BOT-ID>/` references the original question and
failed execution. Original question, failure, timings, logs and duplicate-prevention
claims are preserved. This is bookkeeping, not answer acceptance or generation authority.

Discarded items are excluded from default active selectors and approval preparation.
Select **Show discarded questions** to inspect their history; their original technical
status remains visible separately. A Bot page already showing that ID displays the
discarded notice and offers no next-stage approval. **New chat** creates a new
submission/ID; discard never permits retrying or overwriting the old ID. Unverified
or tampered dispositions fail closed. This bounded facility does not discard live
paid executions or release their reservations.
