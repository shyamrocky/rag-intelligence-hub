# Abstention explanations — experimental prompt v2.2

The owner authorized a bounded offline prompt/display enhancement under ADR D052.
Implementation is submitted for owner review; this does not authorize provider
preflight, generation or seven-batch preparation.

Future experimental preparations select `grounded-generation-prompt-v2.2` with
the unchanged `grounded-response-2.0` schema. The model must keep `answer` and
`claims` empty for `ABSTAINED`, identify the missing requested evidence in
`missing_information`, and explain why the supplied evidence cannot establish
the answer. Absence of evidence is not proof of nonexistence. No new example,
model, retrieval configuration, evidence projection or output field is introduced.

The original v2.1 template, settings and request contracts remain unchanged.
Explicit historical construction uses
`tools.pre_generation_gate.prompt_v21.PromptAssemblyGate`; new construction uses
`tools.pre_generation_gate.current.PromptAssemblyGate`. The old `assembly.py`
v2 and `prompt_v2.py` v1 routes are also unchanged.

`abstention-explanation-check-1.0` adds a source-free structural diagnostic to
future native post-validation results. The response schema already rejects
missing/empty reasons; the additive validator names that failure
`ABSTENTION_EXPLANATION_MISSING_OR_INVALID`, separately from citation validity.
It reuses post-generation-validation-2.1 and changes no semantic acceptance rule.
Vague text, an invented number, a false free-text citation or an incorrect
nonexistence inference can be structurally valid. Their grounding/adequacy stays
`REVIEW_REQUIRED`; there is no lexical meaningfulness or factual-support scorer.
Structured unauthorized Unit IDs still fail the existing strict reference checks.
Presence of a reason never implies approved abstention.

Generation Runner and both local POC and advanced signed Human Review show
**Unable to answer from available evidence**, followed by the original
`missing_information` when an abstained answer is empty. The model status stays
`ABSTAINED`, and the text is labeled model-reported. Historical Q27 is rendered
from its original sealed response; no response, verdict or approval is rewritten.
Refresh/navigation only read artifacts. Existing decision/duplicate controls remain.

## Request and trust migration boundary

New instructions change every affected full request identity. Preserve the
original 28-question inventory/order and saved M7/M8 inputs. Do not reuse old
generator counts, costs, context qualification or authorizations for v2.2.
The current gate audit records `provider_requalification_required=true` and
`historical_token_receipts_reusable=false`; a model-independent preparation still
returns `BLOCKED_CONFIGURATION`, not `READY`.

Successor trust bindings pin the intentionally changed implementation while
retaining prior stage scopes and historical v2.1 plan contracts. They confer no
generation authority or v2.2 request qualification. The existing runner rejects
old preflight settings against the new default. No seven-batch plans are created
in this task.

Four historically pinned Python modules have exact immutable pre-change snapshots
under `data/evals/implementation-history/abstention-explanations-v1/`.
The reviewed `tools/generation_artifact_lineage.py` registry permits their old
artifact bindings only while both the original snapshot and the exact reviewed
successor hashes match. Historical references are labeled as snapshot verification.
No source, configuration, evidence, request, authorization or arbitrary Python file
has a substitution rule. The native preservation checker still directly validates
current implementation hashes. This preserves historical readback without
qualifying old requests for the new implementation.

After owner review, separate batch preparation must bind the accepted prompt and
new request hashes. Separately authorized provider qualification must establish
exact tokens, context/output reserve/margin and current cost before executable
plans and paid execution authorizations can be completed. Historical
`$0.64594350` remains a v2.1 projection, not a v2.2 estimate. No token or cost delta
is invented from character counts. The 900-second receipt limit is unchanged.

Restart the existing Streamlit process if it retains cached Python imports, then
refresh `http://127.0.0.1:8514/generation-runner`. Use the canonical launch command
in the README; do not start a second server on the same port.
