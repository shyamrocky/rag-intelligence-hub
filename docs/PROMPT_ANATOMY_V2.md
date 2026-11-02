# Grounded-generation prompt v2: experimental architecture

October 27, 2026. Owner-authorized bounded implementation; technical result awaits
owner acceptance. This opt-in successor does not change accepted M0–M9, production
Top-10, RRF(k=60), M8 atomic parents, or the sealed prompt-v1 path.

The request remains three ordered messages: trusted system instructions, the exact
original M7/M8-bound question, and complete unchanged M8 evidence marked as
lower-trust data. Response JSON Schema and external generator configuration remain
separate request fields. The complete M8 package is retained only in trusted memory.

The seven logical components are explicit: ROLE, GOAL / TASK, CONTEXT,
INSTRUCTIONS, CONSTRAINTS, one synthetic EXAMPLE, and OUTPUT FORMAT. Context is
supplied dynamically by the question and evidence messages. The role is the
approved evidence-grounded RAG Research Assistant. Instructions request concise
response declarations, never private chain-of-thought reasoning.

Opt in explicitly:

```python
from tools.pre_generation_gate.prompt_v3 import PromptAssemblyGate

# evidence_service is the existing explicitly selected, real EvidenceService.
# question, m8_package and m7_result are the original bound verified inputs.
gate = PromptAssemblyGate(evidence_service)
prepared = gate.prepare(question, m8_package, m7_result, model_configuration=None)
# Log only prepared.audit. prepared.payload contains private publisher evidence.
```

The Python module suffix identifies the gate implementation generation; its
rendered template is `grounded-generation-prompt-v2`, schema `grounded-response-2.0`.
The existing `prompt_v2.PromptAssemblyGate` still renders template v1 with schema
1.0, byte-identically. No default import or selector changes.

The successor reuses the original gate's public live M8/query/config checks before
rendering the new system message/schema and checking live bindings again.
`validate_preparation` inherits the fresh public M8 validation and exact-rebuild
check. A prior receipt never substitutes for current source validation.

The short fictional Atlas example has one exact supporting quotation and one
example-only ID. It is not a current evidence record. A dedicated fixture validator
validates this example; the live structural validator rejects EXAMPLE-prefixed IDs,
even if a caller tries to place them in its allowlist.

The response adds required `requirement_coverage` and `conflicts_detected` arrays.
They are model declarations, not verified coverage or conflict detection. Both may
be empty. Each asserted support reference must belong to the supplied current
M8-derived ID scope; claim/quote references must agree. An internal conflict may
reference one parent. ANSWERED rejects any declared non-SUPPORTED requirement or
reported unresolved conflict; PARTIAL requires claims and explicit missing
information; ABSTAINED requires an empty answer/claims and a missing reason.

Owned-fixture validation uses:

```python
from tools.pre_generation_gate.response_v2 import validate_response_shape

# Obtain this scope only from the currently live-validated package, never from
# the model's response. This call checks shape/reference scope, not source admission.
ids = {p['evidence']['unit_id'] for p in m8_package['parents']}
checked = validate_response_shape(owned_response_fixture, authorized_unit_ids=ids)
```

This is schema/relationship validation infrastructure, not an executed generation
or post-generation evaluator. It cannot determine whether a genuine or fabricated
quotation supports a claim, verify quotation fidelity, identify all question
requirements, or certify factual correctness. A schema-valid response with an
unrelated quotation can pass. These remain future grounded-answer evaluation work.
JSON Schema covers structural types; Python additionally enforces cross-field
relationships and ID scope. Provider-specific schema compatibility is unqualified.

No generator is authorized or qualified. The real Q05 prompt therefore remains
BLOCKED_CONFIGURATION, with generator-token counts unavailable. BGE evidence costs
are not generator token counts. Exact model/tokenizer/message/schema accounting,
input/output limits, output reserve and margin must be separately qualified before
a future invocation can be considered. No inference, API call or model selection
is part of this build.

Private review package: `data/evals/prompt-anatomy/experiment-v1/REPORT.md`.
The redacted Q05 inspection and v1/v2 comparison expose only system text, the
already approved question, hashes, IDs, counts and synthetic demonstration content.
No publisher passage is persisted. Historical reports and source bindings remain
unchanged. Stop for separate owner review; no production adoption is implied.
