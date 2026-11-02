# Separate pilot and remaining-stage trust policies

Owner-authorized preparation, October 29, 2026. **No live execution is authorized.**
The native runner, authorization contract and preservation checker are unchanged.
New sibling successors of v6's implementation select separate exact plan contracts:

| Stage | Trust manifest | Requests maximum | Individual ceiling | Stage ceiling | Original projection |
|---|---|---:|---:|---:|---:|
| Pilot (completed; no retries) | `data/evals/generation-trust/v13/MANIFEST.json` | 4 | $0.03 | $0.12 | $0.09480975 |
| Remaining (not authorized) | `data/evals/generation-trust/v14/MANIFEST.json` | 28 | $0.03 | $0.88 | $0.64594350 |

Both manifests pin the same implementation and preservation inventory. They are
parallel stage policies, not successive code upgrades that invalidate each other.
The deployment allowlist pins each exact path and manifest SHA; arbitrary supplied
paths or self-consistent hashes cannot establish trust. Earlier baselines remain
immutable. The source-reviewed registry remains outside the manifest self-hash
graph and is independently bound by the release review and future authorizations.
Initial v7/v8 preparation seals remain immutable as intermediate records. A
regression exposed a historical test's assumption that the latest policy must
always be Q04-only. The final v9/v10 release updates only that test assumption,
retains v6's unchanged review contract and independently tests both exact new scopes.
v9 descends from v7 and v10 from v8; neither initial seal is a current execution policy.
The automatic human-review handoff release adds v11 from v9 and v12 from v10,
pinning the minimal post-seal runner hook and review UI additions. Stage scope,
request bindings, limits and generation safeguards are unchanged. Pilot execution
is already complete and remains duplicate-blocked; v12 grants no permission to
run the remaining questions. Historical v9/v10 approvals and receipts remain
unchanged and cannot authorize the successor implementation.
Final v13/v14 preserve the initial v11/v12 handoff seals and correct the regression
test's old pending-pilot assumption: history MUST reject the completed pilot.
Only the current code/test/documentation bindings change; stage policy and caps do not.

The pilot order is M9-Q01, M9-Q09, M9-Q27, R03. Remaining membership is derived
from the frozen 34-question inventory, excluding Q04, Q05 and those four IDs.
See the [enumeration, commands and verification report](../data/evals/generation-runner-reviews/two-stage-preparation-v1/REPORT.md).

Each plan contract binds exact ordered IDs, question/M7/M8/request hashes,
preflight, model/profile/settings/pricing, output reservation, context fit, per-item
estimates, limits and maximum call counts. Only the plan creation date is excluded
from the reusable contract hash; the native gate requires today's date and a new
exact logical plan hash in the specific owner authorization. A different request,
scope, price, model or cap requires a newly reviewed policy; it cannot inherit
approval from this release or a previous stage.

Q04's full native reservation $0.02355575 remains held. With both stage projections,
the native planned total is $0.76430900, below $1.00. The two stage ceilings sum
to $1.00 but do not erase Q04's reservation: if a later reviewed estimate consumes
more, the unchanged native cross-run guard still refuses totals above $1.00.
It reserves complete admitted plan projections even on partial failure. Q05's
legacy failed attempt has unknown cost; no zero charge, refund, released reservation
or current account balance is inferred. Stage ceilings are not paid consent.

Future execution requires separate explicit paid/source-transfer owner consent per
stage under `grounded-generation-authorization-2.0`, a fresh preservation receipt
(at most 900 seconds), exact current implementation bindings and aware expiry.
Unsigned preparation has empty consent, false permissions and expired validity.
No usable authorization is issued by this release. The remaining stage requires
the owner's separate pilot review and subsequent execution decision; this policy
does not automate that judgment or chain stages. Interrupted attempts require
explicit history/usage/reservation reconciliation, not automatic continuation.

The live runner freshly reconstructs and validates M8, checks request equivalence,
then qualifies provider access, exact input tokens, context and conservative cost
before at most one generation per question. Fresh counts must match sealed recipes;
older preflight records cannot replace these checks. Zero retries/fallback,
durable attempt markers, global duplicates, single-use approvals and strict source
transfer remain unchanged. Local profile/pricing validity currently ends November 3;
future validity is not guaranteed by preparation.

R03's selection loss and Q23/Q26/R04's assembly losses remain; no gold evidence or
expected abstention labels enter prompts. Post-generation policy remains ADR D052 /
`post-generation-validation-2.0`: strict citations, bounded presentation fidelity,
and separate grounding, completeness and material-disclosure assessments. Missing
independent semantic assessment remains REVIEW_REQUIRED. Q04's local POC approval
cannot authorize pilot execution or accept another answer.

Regression invocation (offline, synthetic providers only):

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m pytest tools/generation_runner/tests/test_stage_policies.py tools/generation_runner/tests/test_native_trust.py
```

Do not launch either live stage until its exact future command and new authorization
have separately been approved. Dashboard refresh remains read-only; no UI or provider
behavior is changed by these policies.

### Local review deduplication successor — October 29, 2026

Current scoped code-compatible review/completed-pilot trust is **v15**; remaining-stage
trust is **v16**. These successors pin answer-level POC decision locking, package
history and Markdown rendering plus their tests and documentation. The native runner,
authorization helper, generation contracts and stage scopes/budgets are unchanged.
All earlier baselines and historical decisions remain immutable. The completed pilot
is duplicate-blocked. **V16 does not authorize remaining-stage execution.**

### Evidence-to-owner-assessment preparation — October 29, 2026

Current scoped review/completed-pilot trust is **v17**; remaining-stage compatibility
trust is **v18**. The successors pin the automatic local preparation step, explicit
owner-judgment form and a stricter unresolved-judgment approval guard. Native generation,
authorization, source authority, stage scope and budgets remain unchanged. Historical
v15/v16 remain sealed. No paid or remaining-28 execution authority is created.

### R03 fidelity and review stabilization successors

v19 (review/completed pilot) and v20 (remaining, **not authorized**) pin the
versioned fidelity-2.1 validator and explicit policy selection, scoped review UI
and duplicate/revision safeguards. Only reviewed implementation/test/documentation
hashes change. Original stage membership, request hashes, source permissions,
model/prompt/schema, fresh preflight requirements, caps, no-retry/fallback controls
and historical records remain unchanged. A trust successor is not paid consent.
The original pilot remains completed and duplicate-blocked. No provider call or
new answer is authorized by this stabilization release.
