# Experimental prompt quality and assembly gate

October 27, 2026. Owner authorized one bounded technical prompt-building cycle.
This implements a new opt-in path alongside the preserved semantic experiment.
M0–M9, D051/RRF60, production Top-10 and accepted M8 contracts remain unchanged.
No generation or production cutover is authorized.

The active experimental responsibility is:

**Sealed RRF Top-30 → unchanged M8 at 128K BGE measurement tokens → live quality
checks and complete prompt construction → generator compatibility qualification.**

Semantic sufficiency is explicitly removed from the new pre-generation acceptance
criteria. The future generator may declare ANSWERED, PARTIAL or ABSTAINED; their
truth/grounding will require a separately authorized post-generation stage.
Neither stage is implemented here.

Implementation: [v2 API and invocation](../tools/pre_generation_gate/PROMPT_ASSEMBLY_V2.md).
The original semantic gate and its report remain unchanged historical evidence.
Private per-question audits, verification and report live under
`data/evals/prompt-assembly/experiment-v1/`. No full prompt/source package persists.

Reuse: M7's normalization and exact result contract; accepted M8 public live
validation and complete-parent reconstruction; existing frozen Top-30 candidate
envelopes; deterministic hash/test infrastructure. No new retrieval, embedding,
source authority, parent grouping, source compaction or evaluation framework.

The prompt has three ordered messages: static trusted system instructions, exact
original question, and complete unchanged M8-authorized evidence with an explicit
data-only prefix. A versioned response schema and external generation configuration
are separate request fields. The entire original M8 package is retained in the
sensitive in-memory payload; package audit metadata does not become extra factual
knowledge in the prompt. Citations, native precision, qualifications, warnings,
source/context/QA distinctions and complete-parent obligations survive unchanged.

`READY` is technical eligibility only. It cannot mean semantic completeness or
answer correctness, nor authorize a model call by itself. Distinct blocks identify
input, integrity, configuration and context failures. No usable included evidence
is an explicit BLOCKED_INPUT outcome for this grounded-only prompt contract.

No exact generator is authorized in existing configuration. OpenAI GPT remains a
direction, not a selected model. A provider SDK/API is not installed or contacted.
The model-independent draft is built, but real model/tokenizer/framing/schema
compatibility remains BLOCKED_CONFIGURATION. Generator input tokens, output reserve
and context margin remain unavailable when no profile exists. No BGE-to-generator
conversion or fabricated READY verdict is permitted.

Strict context arithmetic is implemented for separate input limit, output maximum,
output reservation, safety margin and total context window. Positive/overflow tests
use explicitly owned numeric fixtures. They cannot establish actual generator fit.
A future verified counter must bind exact serialized messages, response-format
schema and provider-specific overhead to an owner-authorized model/tokenizer.
Independent component counts are diagnostic and need not add to the exact total.

Response fixtures validate strict field types, forbidden extras, answer-status
relationships, claim/quote reference consistency and missing-information behavior.
No answer generation, quotation fidelity or semantic entailment check is executed.
The provider-neutral JSON Schema's provider-specific structured-output support is
not asserted.

Next owner review must select the generator and qualify its full-request counting,
input/output limits, message formatting and schema support. Only then can exact
context compatibility be established and a separate bounded generation experiment
be considered. The 128K BGE ceiling is not a generation context allocation.
