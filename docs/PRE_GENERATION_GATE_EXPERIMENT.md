# Pre-generation gate — experimental implementation

October 27, 2026. Bounded owner-authorized integration and offline evaluation.
Implementation and outcomes await review. M0–M9, D051 and production defaults
remain unchanged. M10/M11 remain unauthorized.

The experimental path is saved RRF(k=60) Top-30 → accepted M8 at 128,000 BGE
measurement tokens → standalone gate. The evidence budget is not a generation
model context window. No retrieval, indexing, embedding or ranking is rebuilt.

The implementation lives in `tools/pre_generation_gate/`, separately from accepted
M7/M8. See its [invocation and tests](../tools/pre_generation_gate/README.md).
Private results, source bindings, diagnostics and sealed runtime decisions live in
`data/evals/pre-generation-gate/experiment-v1/`; they are excluded from Git.

## Responsibilities and actual capability

The existing `EvidenceService.validate(package, original_m7_result)` remains the
source-integrity authority. It reconstructs the original complete authorized
parents, verifies publication/index/candidate bindings, citations, context,
qualifications, budget accounting and exact serialized evidence. No duplicated
QA engine, admission rule or raw-section fallback is introduced.

The gate reuses M7 query validation and strip-before-SHA-256 normalization. It
requires the question hash and canonical original candidate-result hash to match
the package. It copies inputs, calls live M8 validation, records included source
field and citation pointers with hashes, and checks live bindings again before
returning. There is no detached validated-view cache or caller-supplied semantic
verdict. Packages remain ephemeral; source pointers retain native citation precision.

Requirements preserve the full question as a mandatory component and separately
record explicit interrogative clauses. This is syntactic decomposition only.
Comparisons, enumerations, procedures, implicit dependencies and qualifications
cannot be reliably decomposed semantically by the current rules. Their uncertainty
is explicit; no omitted clause is silently treated as satisfied.

**Semantic assessment is unavailable.** The project contains no qualified
sufficiency model or provider implementation. The experimental cross-encoder is
not an accepted complete-parent semantic assessor. No model, provider, inference,
network transmission or dependency is introduced. All runtime requirements are
UNKNOWN, support references are empty, and available source pointers are labeled
`NOT_ESTABLISHED` for semantic support. Authenticity, rankings, citations and
keywords never produce a semantic pass.

Source content, required context, QA observations, qualifications and provenance
remain distinct. The gate does not reinterpret illustrative code, certify scores,
upgrade citation precision, discard warnings or read omitted evidence as included.
It records obligation hashes; deciding whether qualifications materially limit a
particular requested claim remains an unsupported semantic capability.

## Versioned interface and decisions

`ValidationGate(service, configuration=GateConfiguration()).assess(question,
package, original_m7_result)` returns `pre-generation-gate-1.0`:

- Decision, status, configuration/method/version and deterministic audit hash.
- Normalized question, uncertain mandatory requirements and per-requirement state.
- Available included source pointers, original Unit/document identities and hashes.
- Empty semantic-support references when support cannot be established.
- Exact M8 package/M7-result/release/question bindings, original budget diagnostics,
  omitted parent references and complete-parent obligation hashes.
- Missing/uncertain component IDs, blocking reasons and advisory recovery only.

| Condition | Decision and status |
|---|---|
| Invalid, stale, tampered, mixed-release or question-mismatched input | ABSTAIN / VALIDATION_ERROR; semantic support NOT_ASSESSED |
| Valid input; assessor unavailable or support uncertain | ABSTAIN / INDETERMINATE; source integrity remains independently validated |
| Valid empty or budget-excluded evidence | ABSTAIN / INDETERMINATE, explicit no-evidence/budget diagnostics |
| Future qualified assessment: all mandatory requirements supported and no blocking concerns | PROCEED (reducer contract only; unavailable in actual runtime) |
| Future qualified assessment: incomplete support and explicitly plausible approved recovery | RETRIEVE_MORE, advisory only (reducer contract only) |
| Future qualified assessment: forbidden use, conflict, no support/recovery or blocking concerns | ABSTAIN (reducer contract only) |

The earlier DRAFT-D053 proposed a null decision on validation errors. The latest
owner instruction requires one of the three decisions, so this bounded build uses
ABSTAIN plus a distinct VALIDATION_ERROR status and NOT_ASSESSED semantic state.
This does not turn integrity failures into ordinary semantic insufficiency.

`generation_authorized` is always false for this experiment. A future qualified
PROCEED would establish eligibility only, subject to separate M10 authorization,
model-specific token allocation and immediate M8 revalidation. It is not a claim
of objective truth, complete generated answers or source admission.

## Evaluation interpretation

The same 15 frozen questions and 22 owner-approved known-positive groups are
used only after runtime decisions are sealed. The live runtime is denied access
to frozen label and scored-result files. No gold IDs, question-specific rules,
retrieval tuning or adaptive loop influence decisions.

The 12 packages containing all approved groups and three packages lacking at
least one approved group are **bounded benchmark proxies**, not exhaustive human
semantic sufficient/insufficient judgments. Unjudged evidence is not negative.
Missing a known-positive alternative does not prove the full parent contains no
other support. Report false PROCEED against the three known-incomplete proxies,
and blocked complete-positive packages separately. Do not claim calibrated
semantic false-positive/negative rates or successful missing-group detection.

Twelve authored reducer controls assume semantic states explicitly and test
contract behavior only. Actual M8 tamper, empty, budget and unrelated/partial
question controls independently test integration. Unknown responses on semantic
controls demonstrate the limitation; they are not correct semantic classification.
A conservative gate that blocks every question fails the semantic acceptance
criterion even if structural and source-integrity tests pass.

Full publisher packages are not persisted. The earlier budget experiment retained
only hashes/metadata, so only missing Top-30/128K packages are rehydrated and checked
against compatible historical package hashes. Existing M8 measurements are reused
for comparison; only this gate's live validation and integration checks are new.
No browser/UI or answer-quality verification is claimed.

## Review recommendation

Accept the deterministic controls only if their verification is satisfactory.
Do not adopt this build as a complete pre-generation semantic contract. The
blocking decisions are a separately specified and qualified semantic assessment
mechanism (or explicit human sufficiency review), a private owner-reviewed
sufficiency/action dataset, and input-capacity/privacy/latency qualification for
complete authorized evidence. The current 22 groups alone do not provide those
judgments. Do not expand this experiment or implement a model without separate
owner authorization.
