# Native generation trust gate v1

Status: implemented for offline owner review. No paid execution is authorized.
This replaces the missing native preservation boundary, not retrieval, M8,
prompting, generation, pricing or production settings.

The runner now accepts new live attestations only under
`grounded-generation-authorization-2.0`. Historical 1.0 artifacts remain unchanged
and readable; they cannot authorize a new live run. `runner.authorize` validates
scope, exact requests, M7/M8/question identities, plan/preflight hashes, code,
permissions, expiration, caps and a fresh preservation receipt. Receipt age is
at most 900 seconds, without future timestamps. Immediately before credentials
and inference, the runner rechecks code, authorization, receipt and protected
state. Fresh provider access/count/context/cost checks remain mandatory and
unchanged. A preserved request is not authorization or semantic validation.

## Trust and upgrades

`tools/generation_trust_anchor.py` is the explicit, source-reviewed deployment
trust root. Its allowlist pins the exact path AND SHA-256 of the successor trust
manifest. Supplying a different, internally consistent policy path/hash fails.
There is no command to approve a policy, replace the allowlist or create owner
consent. The registry is independently pinned by the release review seal and by
each owner's authorization implementation map.

The trust manifest pins the updated runner, native authorization/checking code,
CLI, unchanged evaluator, schemas, configurations, source/retrieval publications,
preflight, prompt/model/pricing contracts and historical Q05 artifacts. It cannot
include the hash of the registry that names it: that would be circular. This
explicit bootstrap root is a deployment assumption, not a self-attestation.
Anyone able to replace both trusted application code and the owner-approved
execution artifact is outside this local file-integrity threat model; no claim
of cryptographic owner signatures or OS tamper resistance is made.

For a future legitimate upgrade:

1. Obtain scoped owner implementation authorization.
2. Verify the previous seal and unchanged critical inventory; archive original
   bytes and enumerate only approved old/new hashes and reasons.
3. Create a new immutable baseline version, preserving all earlier baselines.
4. Pin that exact new seal in the reviewed deployment registry and publish an
   independently sealed review of the registry and migration.
5. Run native admission/integrity regression tests. Request separate execution
   approval bound to the new plan, implementation and fresh receipt.

The running application cannot migrate or approve its own trust baseline.

## Preservation boundary

Policy v2 remains unchanged. Successor policy 3.0 inherits its protection and
replaces only explicitly authorized implementation hashes. Its two exact reviewed
missing capture/checkpoint refs remain nonblocking audit findings; an unexpected
reappearance with different bytes blocks. Deletion cause remains UNKNOWN.

One other exact inherited Codex turn-diff checkpoint, present at migration, is
moved to a separately enumerated historical transient audit inventory based on
the installed Codex lifecycle evidence in the original investigation. Its original
hash remains recorded; a differing reappearance blocks. Future tool-created
capture/checkpoint refs are not enrolled as generation prerequisites. This does
not waive any Git source refs, index, reflogs, objects, worktree recovery records,
archived recovery inventories or packed-refs safeguard. There are no blanket
`.git` exclusions, no ref restoration/deletion, and no recovery-policy adoption.
The migration inventory lists every boundary change explicitly.

## Native admission and history

A process lock serializes live authorization/history/admission. It is only opened
for explicitly requested future live execution, never preparation or dashboard
refresh. A consumed authorization or admitted live plan blocks the same question
across runs. Orphan attempts, missing live START records, unknown reservations
and unresolved consumption fail closed. Legacy generation attempts are also
checked, while Q05 remains explicitly excluded. An admitted native live plan's
whole maximum estimate is conservatively reserved across runs, including failures;
no automatic reservation release or retry is supported. Future rollout total is
capped at USD1.00, excluding Q05's separately authorized historical experiment.
Q04's current policy permits Q04 only and at most USD0.03 for question and stage.
No pilot or remaining-benchmark permission is implied.

The existing durable per-question attempts, exact request comparison, transfer
checks, cost guards, one-call transport, zero retries/fallback and post-validation
remain active. The native gate tightens admission; it does not permit repair,
regeneration or an additional provider call.

## Unsigned preparation and eventual execution

The permanent CLI mode `prepare-authorization` performs offline planning and
preservation, then writes an unsigned template with empty owner statement, false
permissions and expired timestamp. It cannot issue approval. Artifacts are
exclusive-create, private and source-free. Failure cannot leave a usable approval.
The owner must separately approve the exact successor, plan/request and spending
scope; a fresh receipt and explicit owner attestation are required before live.

See the versioned native-trust review's `COMMANDS.md` for exact Q04 preparation
and proposed execution commands. Never reuse historical provider observations as
a substitute for fresh pre-execution M8/source/model/token/context/cost checks.
No dashboard refresh or navigation runs any gate or provider operation.
