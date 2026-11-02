# Pre-Generation Quality & Prompt Assembly Gate v2

October 27, 2026. Owner-authorized bounded experimental successor; no production
cutover or model execution. Import the new `PromptAssemblyGate` from `prompt_v2`.
The old `ValidationGate`, its files, tests, reports and manifests are unchanged.

```python
from tools.pre_generation_gate.prompt_v2 import PromptAssemblyGate

# Reuse an existing real, explicitly selected EvidenceService.
gate = PromptAssemblyGate(evidence_service)
prepared = gate.prepare(original_question, m8_package, original_m7_result,
                        model_configuration=None)
print(prepared.audit)  # Source-free hashes/IDs/status; never log prepared.payload.
```

Use the existing `tools/embeddings/.venv` and `PYTHONPATH=.` from the project root.
No packages, provider SDK, model, tokenizer or environment are installed. The
original M8 counter remains in its original isolated environment.

The API reuses accepted M7 query validation and public
`EvidenceService.validate(package, result)` on EVERY preparation, then checks
current bindings again. The original question is preserved byte-for-byte in the
question message; M7's strip-before-hash behavior is used only to verify binding.
No requirement parser, semantic support states, gold labels or old semantic
PROCEED/RETRIEVE_MORE/ABSTAIN reducer are part of this new readiness path.

The sensitive `prepared.payload` contains:

- Exact ordered system/question/evidence messages and response schema.
- The entire unchanged M8 package retained outside the draft provider request.
- Complete `m8_package['llm_evidence']` as the evidence message, unchanged after
  one explicit data-only prefix. All included authorized parents, source context,
  source/QA distinctions, citations, qualifications and warnings remain intact.
- Externally supplied model configuration when structurally valid.

Package-level M8 audit diagnostics remain outside publisher knowledge in the
model request, while the complete package remains available in trusted memory.
No included parent is summarized, split, compacted, rewritten or removed.

This is an exact **provider-neutral draft request**. It is not claimed to be a
provider-qualified wire request until an authorized generator, tokenizer, message
framing and structured-output format are verified. `model_configuration=None`
builds the whole draft but returns `BLOCKED_CONFIGURATION`. A caller-declared
model/tokenizer/context window, or a `verified` Boolean, cannot grant READY.

The current repository has no owner-selected exact generator. GPT is a provider
direction only. There is no qualified generator request counter or SDK integration.
Actual generator token totals, schema/framing overhead and context margin are
therefore UNAVAILABLE/null. BGE counts, byte lengths and estimates are never
substituted. `ModelConfiguration` specifies the external profile fields;
`check_context_limits` tests strict capacity arithmetic independently. Those tests
are not actual model compatibility. Future qualified counting must cover the
entire exact messages + schema + provider framing and reserve, not sums of
independent component estimates.

Statuses:

| Status | Meaning |
|---|---|
| READY | Reserved for a fully verified generator request and context fit; unavailable in this build without a qualified generator/counter |
| BLOCKED_INPUT | Missing/mismatched question/transport or valid M8 with no included authorized evidence |
| BLOCKED_INTEGRITY | Native M8/source/publication validation or current bindings failed |
| BLOCKED_CONFIGURATION | Schema/configuration invalid, or generator/tokenizer/framing/output support unverified |
| BLOCKED_CONTEXT | Context/input/output/reserve/margin overflow once exact qualified counting is available; arithmetic exercised with owned controls only |

A valid empty M8 package is technically blocked from grounded generation with
`NO_INCLUDED_AUTHORIZED_EVIDENCE`; this is not a semantic abstention verdict.
Semantic adequacy never blocks a technically otherwise valid request here.

`response_v1` defines JSON Schema and strict Python shape validation for ANSWERED,
PARTIAL and ABSTAINED. Python validators additionally enforce status/claim/quote-ID
relationships. These are fixture/schema checks, not post-generation validation:
no quote fidelity, source entailment, factual correctness or answer is assessed.
Provider acceptance of this schema remains unverified. Instructions delegate
answer/partial/abstain declarations to the future model, without certifying them.

Evidence remains lower-trust user-message data, never interpolated into system
instructions. Deterministic framing cannot certify absence of malicious source
instructions; it preserves bytes and does not execute them.

`validate_preparation(...)` performs fresh native validation and exact rebuild to
reject a tampered/stale payload. The receipt is not reusable authorization. Any
separately authorized future invocation must revalidate immediately and use a
qualified READY path. No invocation, retry loop or post-generation stage exists.

See `docs/PROMPT_ASSEMBLY_GATE.md` and private results under
`data/evals/prompt-assembly/experiment-v1/`. Do not log/cache/publish full payloads.
