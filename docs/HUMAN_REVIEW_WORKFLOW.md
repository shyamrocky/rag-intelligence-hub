# Local human review and approval v1

## Automatic native-result handoff

Every sealed native live result now appears in **Generation Runner → Human Review**
through the **Completed generation for Human Review** selector. ANSWERED, PARTIAL
and ABSTAINED results remain visible even when their original validation failed.
The pilot is backfilled without regeneration. Q04's original approval/history remain
unchanged; selecting a newly bound package does not require another Q04 semantic vote.

The inbox distinguishes recorded technical findings, model-reported claims and
coverage, and independent assessments. It shows quotations, source references,
qualifications/conflicts, timings and compatible offline evidence-group measurements.
Missing known-positive evidence is not automatically an incorrect answer; a quote
formatting failure is not automatically a semantic contradiction.

Complete source-bound assessment inputs produce unsigned review packages automatically
after native result sealing. An assessment arriving later can be prepared automatically
as part of an explicitly confirmed decision; no separate manual package step is needed.
When those assessments do not exist, the result stays reviewable as **PENDING_ASSESSMENTS**
with explicit missing inputs and disabled decision controls. This does not manufacture
an independent claim/completeness/disclosure judgment from model self-declarations.
The current pilot observations are provisional notes, not complete passage-bound
Assessment records; those four entries correctly remain pending. See the
[handoff contract](HUMAN_REVIEW_HANDOFF.md).

Dashboard refresh/discovery writes nothing and performs no M8 reconstruction,
retrieval, prompt building or provider calls. The existing fresh M8 and strict
technical checks still run only on explicit owner submission. No automatic approval
is created; signed advanced review remains unchanged.

## Week 2 POC: no registration required

The default **Generation Runner → Human Review** mode is now **LOCAL_POC_REVIEW**.
The panel opens expanded. Select the prepared question, inspect its answer,
citations, grounding, completeness and qualifications, enter your own reviewer
label and optional notes, check the explicit confirmation, then click **Approve**,
**Reject** or **Request Changes**. No signing key, passphrase, identity registration
or manual hash entry is required. The form binds the decision to the exact displayed
question/response/evidence/assessment/policy hashes; confirmation resets when the
selected package changes. No default approval or automatic Q04 decision occurs.

`OWNER_APPROVED_POC` means an unsigned local owner attestation, **not** authenticated
HUMAN_REVIEW or formal `VALIDATED` status. The unchanged v2 authenticated assessment
remains `REVIEW_REQUIRED`. The original Q04/Q05 verdicts remain immutable. Reject
and Request Changes produce `OWNER_REJECTED_POC` and `OWNER_REQUESTED_CHANGES_POC`.
Genuine source, request, citation, schema, substantive quotation or explicit
mandatory-disclosure failures block POC acceptance with `BLOCKED_TECHNICAL`.

On submission, existing live M8 reconstruction and v2 technical validation run;
no retrieval, generation or provider request occurs. Each decision is an additive,
sealed local record with actual timestamp, owner-supplied label, notes and exact
bindings under `data/evals/human-review/local-poc/`. It is separate from the signed
evaluation namespace. Exact duplicate decisions are blocked; a separately confirmed
later decision is a new version. Partial writes stay outside discoverable history.
These are local integrity hashes, not cryptographic proof of reviewer identity.

This mode requires a literal loopback Streamlit bind and local Host/Origin; forwarded
proxy headers, remote peers, wildcard binds and missing web context are rejected.
Use direct localhost access, not a reverse proxy or public deployment. Streamlit's
reported client IP alone is insufficient; the server's bind configuration is also
enforced. These local restrictions are not a multi-user authentication service.

If the old screen remains visible or localhost checks are blocked, stop the existing
Streamlit process with **Ctrl-C in its terminal**, then restart once from project root:

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/master_dashboard/canonical.py --server.address 127.0.0.1 --server.port 8514 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8514/generation-runner>. Do not start a second server on the same
port. A browser refresh may suffice when Streamlit hot reload has picked up the changes.

The original workflow below remains unchanged and is available through
**SIGNED_HUMAN_REVIEW (advanced)**. Choose a package using the current successor trust
baseline when submitting; older packages and manifests are retained for history.

---

**October 29, 2026 — implemented for owner technical review.** D052 governs answer
quality. This workflow authenticates a local reviewer decision; it grants no source
admission, model access, API spending, generation or batch permission. Real owner
registration and Q04 approval have deliberately not been executed.

The canonical dashboard remains at port 8514. Open **Grounded Generation Runner →
Human Review**. The panel displays the original question/answer, cited Units,
proposed grounding, additional assertion inventory where supplied, completeness,
qualifications, conflicts and current signed review status. Browsing/refreshing
does not reconstruct evidence or call any provider. Only an explicit authenticated
decision submission performs fresh local M8 checks and publishes a new evaluation.

## One-time enrollment — owner performs this locally

Choose your own stable reviewer ID and display name. The placeholders below are
not registered identities. From the project root in an interactive terminal:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.human_review register --reviewer-id YOUR_STABLE_ID --display-name "YOUR DISPLAY NAME"
```

Type the exact `REGISTER … AS …` confirmation shown and choose/confirm a strong
passphrase (at least 12 characters). Do not send it to Codex or paste it in chat.
No passphrase arguments, environment variables or browser-persisted login tokens
are supported. Check enrollment with:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.human_review status
```

The local OS operator is the enrollment authority. Explicitly supplied ID/name,
proof of possession and passphrase authentication establish this project's local
reviewer identity; they do not independently establish legal identity or expertise.
This is appropriate for a single-owner localhost educational project, not a hosted
multi-user identity service. Keep Streamlit bound to `127.0.0.1`; do not expose
this passphrase form on an unreviewed network deployment.

Encrypted Ed25519 private keys, public enrollment anchor, signed key history and
duplicate-decision ledger live under `~/.config/rag-intelligence-hub/human-review/`,
outside the repository and evaluation artifacts. Directories require owner-only
access, credential files mode 0600, and symlinks are rejected. Existing local
OpenSSL is used via subprocess, without a shell or new Python dependency.
Passphrases use an inherited pipe, never argv, logs or key files. A private
temporary directory holds only the canonical source-free signing input and
public verification materials. No plaintext private key is persisted.

Protect this private directory with the OS account. An attacker controlling that
account can replace its trust anchor or roll back its complete storage; this
workflow does not claim hardware-backed identity, external timestamping or
protection against a compromised local operator. Back up keys privately if needed.

## Per-answer decision

1. Select the unsigned prepared review in **Generation Runner → Human Review**.
2. Inspect the bound answer/findings and the full manifest hash. Q04 incorporates
   its already recorded substantive owner decisions; no repeat semantic vote is
   needed. The final confirmation is new and specific to this exact record.
3. Enter the enrolled ID and signing-key passphrase. Type the exact confirmation,
   for example `APPROVE M9-Q04 FULL_MANIFEST_SHA256`, and check the explicit record
   confirmation box. Click **Approve**, **Reject** or **Request Changes**. Use the
   corresponding `REJECT` or `REQUEST_CHANGES` prefix for those decisions.
4. The application freshly validates M7/M8, policy/trust/source and passage hashes,
   authenticates the decision, and passes the signed assessment hash and registered
   ID to the existing `HumanReview` importer. It reruns unchanged validation v2.
5. A separate sealed evaluation appears automatically. An approval can still yield
   `VALIDATION_FAILED` or `REVIEW_REQUIRED` when technical or semantic conditions
   are unsatisfied. A human vote cannot override invalid citations or sources.

The CLI provides the same flow with an interactive confirmation and hidden
passphrase prompt (replace the manifest and hash with those in the review packet):

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.human_review inspect --manifest REVIEW_MANIFEST
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.human_review decide --manifest REVIEW_MANIFEST --sha256 FULL_MANIFEST_SHA256 --reviewer-id YOUR_STABLE_ID --decision APPROVE
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.human_review verify --manifest NEW_EVALUATION_MANIFEST
```

CLI inspection prints the question, generated response and source-free assessment,
not reconstructed complete publishers. Use a local terminal, not unrestricted
logging. UI passwords/confirmation fields clear on submission. Credentials and
complete M8 packages never enter reports or dashboard telemetry.

## Preparing future answers

`python -m tools.human_review prepare --input PRIVATE_SOURCE_FREE_INPUT.json` takes
`source`, `question`, `assessment`, `trust`, and optional `supporting_artifacts`
and `layout_reviews`. `source` specifies a completed native LIVE result's manifest
path/hash and result path/hash. The assessment uses the existing
`answer-quality-assessment-2.0` schema. `trust` specifies an exact deployment-
allowlisted successor manifest and hash. Preparation never registers or approves.
The initial owner confirms the draft's actual evidence-aware findings, including
additional factual assertions, uncertainty and appropriateness of the answer.
Source-free draft generation does not create independent semantic evidence.

Currently supported inputs are completed **native runner** live results; legacy
Q05 is preserved and is not silently converted to a new native generation result.
An explicit adapter would be needed to review that older envelope through this
entry point. No generation implementation is rebuilt here.

Packages expire after seven days and pin exact question, response, M8 package,
request, assessment, layout records, policy and successor trust reference. New
drafts/changed policies need a new package and explicit confirmation. No prior
approval transfers to another answer. The Q04 preparation helper additionally
pins the original owner-decision/provisional-review seals. See the delivered
Q04 onboarding receipt for its exact package/hash.

## Decisions, recovery and credential lifecycle

- **Approve:** signed HUMAN_REVIEW assessment plus existing v2 evaluation.
- **Reject:** signed rejection and `VALIDATION_FAILED`; original response retained.
- **Request Changes:** signed request with `REVIEW_REQUIRED`, unless strict checks
  already fail. There is no answer repair or regeneration.
- One decision is admitted per exact response/evidence/draft/policy target.
  A duplicate package cannot bypass this. A revised draft is separately confirmed;
  older decisions remain visible and are never rewritten.
- Publication is transactional: staging is outside the discoverable evaluation
  namespace; signature/import/source checks precede an exclusive durable marker
  and atomic directory publication. Failed/partial staging is not accepted.
- If a crash occurs after reservation but before publication, run the authenticated
  `recover --target TARGET_HASH --reviewer-id YOUR_STABLE_ID` command and type
  `ABORT TARGET_HASH`. It archives the uncommitted marker with a signed abort.
  A published review cannot be aborted or overwritten. No automatic retry occurs.
- `rotate --reviewer-id YOUR_STABLE_ID` requires the current passphrase, a new
  confirmed passphrase and exact `ROTATE …` confirmation. Rotation has proof of
  both old and new keys. `revoke --reviewer-id …` requires current authentication
  and exact `REVOKE …`. Historical signatures remain preserved; revoked/rotated
  credentials cannot establish current accepted status. Reassessment under a
  new active key needs a separately confirmed revised record.
- Lost credentials cannot be recovered by typing a name or clicking a button.
  Recovery/re-enrollment after key loss needs an explicit local trust-root review;
  no bypass or silent replacement is provided.

Signed records bind the decision, reviewer/enrollment/key history, actual decision
timestamp, exact assessment and evaluation hashes, and full review-package hash.
The source-free quality reader verifies signatures and active registration before
displaying authenticated acceptance. Verification of a historical signature is
not fresh source authorization for any future generation.

## Verification scope

Tests use disposable synthetic identities, encrypted keys and owned evidence.
Real cryptographic verification, the existing HumanReview importer, v2 validator
and Streamlit forms execute; production M8 reconstruction is exercised only for
unsigned Q04 onboarding. No real owner key or human acceptance is created by tests.
No external authentication service, new provider call or LLM judge is introduced.

```sh
PYTHONPATH=.:tools/generation/.venv/lib/python3.12/site-packages apps/ingestion_dashboard/.venv/bin/python -m pytest tools/human_review/tests tools/answer_quality/tests
```

Source/update trust follows the existing exact allowlisted, sealed successor
baseline process. Old baselines are preserved; changed implementation is not
approved by its own runtime hash. Owner technical review of this release remains
separate from registering the real reviewer or approving Q04.

## One logical answer, one current local POC decision

The default local review view groups packages by exact question ID/text hash,
response hash, M8 evidence-package hash, request hash and validation-policy identity.
Renewed packages, assessment drafts and trust migrations do not create another
review opportunity. A changed answer, evidence, request or policy is a separate
pending target. The newest intact, unexpired package is selected; older intact
packages remain in expandable history. Generated Markdown uses the Markdown renderer
with Streamlit's default HTML protections.

Sealed local POC decisions are verified on every refresh. A matching
`OWNER_APPROVED_POC`, `OWNER_REJECTED_POC` or `OWNER_REQUESTED_CHANGES_POC` locks all
three ordinary decision controls, including across packages and reviewer labels.
The backend enforces this under the existing filesystem lock, including concurrent
submissions. This remains unsigned owner attestation, not formal `VALIDATED` status.
No decision transfers to a changed response/evidence/request/policy version.

Reassessment is deliberately absent from the ordinary UI. An explicit new revision
can be submitted through `local_poc.decide` only with the exact latest decision's
`revision_of={"path": ..., "sha256": ...}` and a nonempty `revision_reason`, in
addition to the usual current package, owner label, explicit confirmation, direct
localhost and fresh technical checks. New `local-poc-review-1.1` receipts retain
revision number, predecessor and reason. Existing 1.0 receipts remain unchanged.
A stale predecessor, missing reason or concurrent losing submission is rejected.
This interface does not authorize Codex to issue a real decision or reassessment.
The optional signed workflow and its authentication contract remain unchanged.

The October 29 inventory contains **four** intact Q04 packages (including v11/v13
trust-migration copies), all for one exact answer and policy. The original sealed
POC approval locks that logical answer; no replacement approval is needed.
Pilot questions still awaiting complete independent assessments remain visible as
pending entries, with disabled decision controls and explicit missing inputs.
R03's native fidelity failure and missing R03-G1 group remain separate from semantic
review status. No semantic judgment is inferred from either diagnostic.

## Evidence preparation and owner judgments

Native live results now enter a bounded, durable local assessment-preparation step
through the existing post-seal handoff. No provider or semantic judge is invoked.
Existing source-aware provisional assessments are reused when available. Otherwise
all semantic dimensions remain INDETERMINATE and the status is OWNER_REVIEW_NEEDED.
The owner can inspect authentic supplied publisher fields and separately labeled QA
metadata, decompose the original question, assess each claim and additional assertion,
record qualifications/conflicts and decide whether the generated status is appropriate.
Unassessed dimensions are never silently filled with SUPPORTED or COMPLETE.

In Generation Runner → Human Review, select an answer. ASSESSMENT_READY means an
actual provisional evidence-aware assessment exists, not human acceptance.
OWNER_REVIEW_NEEDED means materials exist for direct owner assessment.
ASSESSMENT_UNAVAILABLE shows a failed or unfinished preparation and its safe error
category. The explicit **Prepare evidence & review materials** action retries one
selected question locally, once per click. Refresh never reconstructs sources.

Review the source fields and provisional findings. Edit support/completeness and
rationales, select fields examined, add assertions outside the claim list, resolve
material qualifications/conflicts and declare status appropriateness. Supply your
reviewer label, inventory/requirements confirmations and the per-decision confirmation.
Approve requires resolved judgments and fresh technical checks. Reject/Request Changes
can retain unresolved judgments. A technical failure still prevents owner approval;
a recorded negative intent on a technically failed answer remains BLOCKED_TECHNICAL,
not accepted validation. The sealed native verdict is never rewritten. An approved
answer remains locked across packages as before. Signed advanced controls are unchanged.

Provisional assessments, owner judgments and local POC decisions have distinct records.
The owner form writes a new hash-bound draft and additional-assertion inventory before
calling the existing POC decision handler. It never submits an unsigned owner label to
the authenticated HumanReview importer. Formal v2 VALIDATED status is not conferred.

The four pilot entries are backfilled through this path. Q01/Q09/Q27 can be considered
for explicit owner POC approval subject to the displayed judgments and fresh validation.
R03 remains approval-blocked by its existing fidelity failure; alternative source
support and missing R03-G1 are independently shown. No quotation policy was relaxed.
Q01's required expiration warning remains applicable: the accepted unchanged-cohort
reading policy permits retrieval with disclosure and does not renew QA authorization.

The reusable local CLI is:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.human_review.preparation --question M9-Q01
```

Repeat `--question` for a bounded set; omit it to process completed native results,
skipping answers already decided. Each invocation verifies source/trust bindings;
completed matching preparation is reused. No retrieval, generation, provider calls,
real approval or paid authorization is performed. All native generation-result and
review histories are retained. Current scoped trust successors are v17/v18; v18 is
**not** remaining-benchmark execution authorization.

## Concise review and explicit policy revisions — October 29, 2026

The native Human Review selector displays **Approved (Local POC)**, **Rejected**,
**Changes Requested** or **Pending Review** from verified sealed decision records.
A technically blocked Request Changes intent is shown with **Technical Block
Recorded**; it is not a passed validation. Model ANSWERED and ASSESSMENT_READY
never become owner-decision labels. Historical packages remain in expandable
history, including cross-policy packages of the same exact answer.

The default view shows the question, Markdown answer, provisional grounding and
completeness summaries, citations/fidelity, qualifications/conflicts, outstanding
issues and current decision. Detailed editable matrices/source references are in
collapsed **Advanced Review / Edit Findings**. All inventory, requirement,
reviewer-label and explicit confirmation controls remain enforced by the backend.

A new validation policy does not transfer approval or unlock duplicate decisions.
Existing completed reviews retain their policy. A separate policy reassessment
requires opening **Deliberate reassessment — explicit new revision**, supplying
a reason and explicitly initiating it. This changes only local form eligibility;
no decision is published until a separately confirmed submission. The backend
rechecks the latest decision path/hash under its lock and records revision lineage
across policy versions in `local-poc-review-1.2`. Old 1.0/1.1 receipts remain intact.
Fresh source/citation failures still block approval, including during revisions.
No generation permission is conferred. The signed advanced mode retains its
signature/authentication contract and validates the explicitly selected policy.

Restart the existing Streamlit process if it has cached older imports; use the
unchanged canonical localhost:8514 command in the README. Do not start a second
server on the same port. Refresh/navigation reads sealed records only.
