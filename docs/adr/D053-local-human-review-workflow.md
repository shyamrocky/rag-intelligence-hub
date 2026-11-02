# D053 — Local authenticated human-review workflow

- **Version:** 1.0.
- **Date:** October 29, 2026 (America/Los_Angeles).
- **Status:** Owner-authorized bounded implementation; delivered capabilities await
  technical review. Real reviewer registration and Q04 approval remain unexecuted.
- **Decision:** Extend D052 with explicit local OS-operator enrollment, encrypted
  Ed25519 credentials and per-answer signed, hash-bound approval/rejection/change
  requests. Reuse HumanReview and unchanged v2 quality criteria.
- **Rationale:** Q04's substantive owner decisions are recorded, but an unauthenticated
  name or locally computed hash cannot satisfy the importer trust boundary. A
  local possession/passphrase mechanism supplies that boundary without a service.
- **Alternatives:** Trust a reviewer-name field alone (insufficient); deploy an
  external identity service (unnecessary here); continue manual external-hash
  configuration only (not the requested short reusable UI workflow).
- **Authority:** Explicit owner “Reusable Human Review & Approval Workflow” instruction,
  including functional dashboard controls and mandatory stop before real enrollment.

The [workflow guide](../HUMAN_REVIEW_WORKFLOW.md) defines enrollment, OS trust
assumptions, rotation/revocation, failed-publication recovery and exact invocation.
The [versioned policy](../../tools/human_review/POLICY.json) separates review
authentication from paid generation. The local operator explicitly supplies and
confirms identity; this is not independent certification of legal identity or
reviewer expertise. Compromise or complete rollback of the trusted OS account is
outside this local mechanism's guarantees.

Only a fresh confirmed decision can publish a new signed assessment. Strict live
M8 source and citation checks remain mandatory. Authentication cannot promote a
technically invalid answer. Dashboard refresh/navigation remain read-only;
explicit review submission performs local validation and creates additive review
records, never generation or provider requests. Original Q04/Q05 verdicts, prompts,
labels, M7/M8 and generation safeguards remain unchanged. The implementation is
pinned through a reviewed successor trust baseline, not an arbitrary runtime
policy path. This record does not enroll or approve anyone.
