# Native generation to human review — handoff v1

Implemented for owner review under ADR D052. No provider call, new answer or owner
approval is part of this release.

The native runner calls `tools.human_review.handoff.after_generation` **after** its
immutable run manifest is sealed. This creates separate hash-bound handoff records;
it never rewrites a result, invokes generation, changes an authorization or retries
an answer. Handoff failure cannot consume another paid request. Discovery remains
available even if persistence was interrupted. Handoff work is outside the existing
question-level timing scope; old timing receipts are preserved.

The Streamlit inbox reuses `generation_runner.dashboard.discover`, the frozen
question reader, saved M8 delivery validation and existing review-package loader.
Only completed native **live**, non-fixture responses enter it. A generated
ABSTAINED result can have no claims or citations. REVIEW_REQUIRED and VALIDATION_FAILED
are displayed, never silently filtered out. Unsealed/tampered input fails closed.
Each unique source/answer/request/package identity has a stable entry ID. Separate
actual attempts remain distinguishable; refresh/restart never duplicates records.

**Discovery is read-only.** It cannot call `workflow.prepare`, M8, retrieval, a
provider or an approval method. `synchronize` is the post-seal writer and explicit
offline-backfill API. It uses a filesystem lock, content-bound identities, exclusive
writes and atomic publication. Existing records are immutable. Complete assessments
reuse `workflow.prepare`; package expiry and fresh decision-time source checks are
unchanged. No opaque publisher package or full prompt is copied into the inbox.

An automatic review package is still unsigned and unaccepted. The existing
LOCAL_POC_REVIEW requires direct localhost, an owner-supplied label, explicit
per-answer confirmation, exact bindings and fresh technical validation. Technical
failures continue to prevent approval. The signed workflow, keys and importer are
unchanged. Handoff trust selection comes from the source-reviewed bootstrap registry,
not a caller-supplied arbitrary policy. Current review trust is v13; a sibling v14
preserves the remaining-stage contract for a future separately authorized run.
No paid execution permission follows from either migration.
The initial v11/v12 preparation seals remain immutable; final v13/v14 also pin the
regression correction requiring the already-completed pilot to be duplicate-blocked.

## Assessment inputs

Existing prepared packages are reused (or additively rebound to the current review
trust); originals and decisions remain historical. A future independent assessment
producer can publish a sealed input at:

`data/evals/human-review/assessment-inputs/<version>/MANIFEST.json`

The manifest schema is `human-review-assessment-input-1.0` with `created_at` and
SHA-256 `files` bindings for `INPUT.json` and `ASSESSMENT.json`.

`INPUT.json` contains exact `question`, `response_source` (native manifest/result
paths and SHA-256), optional `supporting_artifacts` hashes and `layout_reviews`.
`ASSESSMENT.json` must satisfy the existing `answer-quality-assessment-2.0` schema,
cover every reported claim with exact claim hashes and required passage references,
provide reviewed question requirements and inventory flags, and bind question,
response, M8 package and request. Its method/reviewer fields do not authenticate it.
Source passages are rechecked through unchanged M8 on actual submission. A raw
model `requirement_coverage` list or informal Codex observation cannot substitute
for this input. Invalid/tampered assessment inputs leave a pending entry.

When inputs exist after a run, a selected confirmed UI decision performs the
unsigned preparation internally before invoking the existing POC handler. It
rechecks the displayed input hashes first. No extra preparation button or Codex
prompt is needed. Refresh still performs no writes. Assessment authoring or semantic
judging is not invented by this handoff: incomplete inputs require real review work.

The one-time authorized backfill is equivalent to:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.human_review.handoff
```

This command synchronizes review artifacts only; it is not generation or approval.
Ordinary browsing does not execute it.

The pilot's Q01/Q09/Q27/R03 records are visible immediately with missing independent
assessments listed. R03 retains its original fidelity failure and separately shows
the absent R03-G1 known-positive evidence group. Neither finding establishes a
semantic error on its own. Q04 retains its existing prepared assessment and local
owner decision. No original response, M9 label or validation verdict is changed.

### Answer-level projection successor

The local POC inbox now coalesces identical answer/evidence/request/policy identities,
including duplicate source references. It retains source history and all immutable
package history. Its stable logical target is separate from old handoff receipt IDs;
old handoff seals are not rewritten. New answers and evidence/policy versions remain
separate. Refresh reads verified decisions and never creates packages or approvals.
Review trust v15 and compatible remaining-stage trust v16 pin this scoped change;
v13/v14 and all earlier seals remain historical. V16 is not execution authorization.

### Durable assessment preparation

The existing native `after_generation` hook now invokes
`tools.human_review.preparation.run` after the run seal. This is local post-processing,
not a second generation runner. It uses original M7/M8 public validation,
PostGenerationValidator v2, Assessment2.0 and workflow.prepare. New source-free
receipts are in `data/evals/human-review/preparations/`; restricted publisher context
is in `workspace/human-review-evidence/` (directories 0700, files 0600, Git-ignored).
The private context contains supplied publisher fields and separately labeled source-use
metadata; it is never a reusable source-authorization token. Actual decisions revalidate M8.

A filesystem lock serializes preparation. Successful logical inputs reuse sealed
receipts and packages; interrupted unsealed work is not accepted and explicit retry
creates a new version. Failures have separately sealed source-bound receipts and
never retry generation. Already-decided targets are skipped. No new Q04 package or
decision is needed. Read-only discovery hashes receipts/private context but never
reconstructs evidence, runs an assessor or contacts a provider.

No qualified automatic semantic model is installed. Without a genuine assessment
input, claims/requirements/qualifications/conflicts remain unassessed and the owner
can provide judgments in the form. Existing optional SemanticAssessor/LLM_JUDGE
interfaces remain separately authorization-gated; this capability adds no model calls,
provider credentials or automatic semantic certificates. Provisional Codex pilot
analyses are ASSISTANT_ANALYSIS, not authenticated HUMAN_REVIEW. Owner POC judgments
remain unsigned. Technical and semantic failure dimensions are distinct.

The bootstrap review selector is v17; sibling v18 preserves the unchanged remaining
stage. Historical v15/v16 and every prior baseline remain immutable. No execution
permission follows from this migration. Preparation happens outside the original
question-level execution-timing scope; historical latency receipts are unchanged.
