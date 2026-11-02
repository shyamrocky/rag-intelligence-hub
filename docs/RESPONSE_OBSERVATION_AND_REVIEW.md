# Response observation and Human Review

Owner-approved implementation scope, October 30, 2026. Offline verification and
native trust migration are recorded in the associated review report.

The generation stage captures raw provider bytes before decoding. An additive
`generation-response-observation-1.0` records original text parts, refusals and an
**untrusted** JSON candidate in protected, Git-ignored project storage. Duplicate
keys remain ambiguous; no silently repaired candidate is promoted. Schema 2.0,
prompt v2.2, retrieval, M8 policy and model configuration remain unchanged.

The runner separates answer quality from execution safety. Known-billed,
persisted output-quality failures may continue to the next independently
qualified question. Invalid citations still fail that answer. Source/request/trust
violations, unknown billing, output limits, provider/model mismatch and persistence
failures stop the batch. Each next question still passes the existing fresh native
authorization, source, model, count, context and cost gates. No retries, fallback,
authorization reuse, admission unlocking or reservation release is introduced.

New runs preserve M8/M7 review material already present in memory. Raw observation,
source material and hashes are separate from unrestricted telemetry. Sealed results
include observation references, supported field-level checks and batch disposition.
Unexecuted planned questions are explicit `NOT_RUN_SAFETY_STOP`, never fake attempts.

The canonical dashboard uses one native/legacy attempt projection. Counts distinguish
parsed answers, attempts without parsed answers and never-attempted questions; all
measured attempts contribute cost, including rejected/repeated outputs. Unknown cost
is reported separately. Mock output remains separate. Legacy Q05 remains visible.

Under **Generation Runner → Human Review**, one question selector leads to exact
attempt history. Ordinary local POC and signed review controls remain intact.
Rejected output has a readable candidate/refusal, exact contract findings and an
explicit localhost owner-triage form. Triage records `ANSWERED`, `PARTIAL`,
`UNANSWERED` or `UNASSESSABLE` as owner observations, **not approval, source
certification or formal VALIDATED status**. Confirmation, exact source bindings,
policy identity, an exclusive decision lock and immutable receipts prevent silent
transfers and duplicate submissions. Failed/incomplete writes cannot be accepted.

The expandable M0–M10 trace distinguishes reused preparation/index releases,
saved M7 inputs, request-bound M8 delivery, offline M9 known-positive labels and
M10 output/validation. Protected source text requires localhost. Missing historical
material is explicit; a separately clicked local preparation action can reconstruct
and verify the exact historical M8 hash without provider access. Refresh never
assembles evidence or calls a provider. Existing candidate/parent and knowledge
preparation workflows are preserved.

Historical Q12/original Q18 raw text cannot be recovered. Current Q18 raw text is
hash-verified before display. Historical verdicts and approvals remain immutable.
Q19/Q20 admission locks remain: implementation is not continuation permission.
