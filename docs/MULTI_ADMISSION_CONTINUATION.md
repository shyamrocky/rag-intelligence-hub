# Native continuation across reviewed admissions

Owner-authorized implementation, October 30, 2026. Execution consent is separate
from policy identity; a trust successor alone never permits paid generation.

`native-generation-continuation-1.1` extends the existing recovery interface for
never-executed questions covered by multiple stopped admissions. Historical
`native-generation-recovery-1.0` remains supported unchanged.

The new contract replaces singular parent references with an exact, ordered,
distinct `parents` list. Each entry pins a sealed parent manifest and consumed
single-use authorization record by path and SHA-256. The allowlisted trust policy
pins the entire contract and exact question/request/M7/M8 bindings. It is not a
caller-selected waiver. Every parent must independently pass the existing seal,
billing, request and never-executed checks. This contract permits no retry of an
already attempted question, including an unsuccessful one.

Native history recognizes only these reviewed parent runs and use records. A third
admission, an unsealed/orphan attempt, unknown billing, changed evidence or an
already successful answer still blocks. Every parent reservation remains counted;
new admission adds its full conservative estimate. Ordinary single-use controls,
source transfer, live M8 validation, exact request comparison, fresh model/token/
context/cost qualification, 900-second receipt lifetime, durable attempts, $0.03
individual limits and the $1.00 rollout ceiling remain.

For the owner-approved Q19/Q20 continuation, the two reviewed admissions are the
original Batch04 and its Q18 recovery. Both selected questions were never sent.
The new exact plan excludes Q17/Q18/Q05 and all later batches. It has a $0.06 cap
and at most two generation requests, one each, no retries or fallback. Historic
projection $0.04730850 is not a substitute for fresh provider qualification.

Response observation and Human Review remain as documented in
[Response observation and review](RESPONSE_OBSERVATION_AND_REVIEW.md). Preserved,
known-billed output-quality findings may continue independent questions; execution
safety failures stop. Failed generation cannot silently create another continuation.

Intentional runtime hash changes require reviewed successor trust manifests.
Prior code snapshots support read-only history; prior baselines, authorizations,
results and reservations are never reset or rewritten. No new runner or UI action
is introduced.
