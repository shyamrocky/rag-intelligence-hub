# Experimental mandatory qualification enforcement

October 28, 2026. Implemented for owner review; no generation or provider preflight
was executed. The current experimental entry point is `tools.generation.current`.
Its default pair is **grounded-generation-prompt-v2.1 / grounded-response-2.0**.
Model, pricing, source admission, RRF, Top-K and M8 atomicity are unchanged.

## Current entry points and historical replay

```python
from tools.pre_generation_gate.current import PromptAssemblyGate
from tools.generation.current import GenerationService, load_settings
```

The new `settings-v2.1.json` differs from historical settings only in prompt version.
The current CLI defaults to local dry-run preparation for the existing Q05
experimental pipeline:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation.current --dry-run
```

It does not load `.env` or call a provider by default. No provider request or paid
execution is authorized by this documentation. Any future source transfer and
generation requires separate owner approval and explicit existing-style opt-ins.

For exact historical v2 replay use `tools.pre_generation_gate.assembly` and
`tools.generation.cli`, with the original `settings-v1.json`. Those files and their
sealed fingerprints stay unchanged. Historical v1 remains explicitly selectable
through the preserved historical assembly interface. New experimental integrations
must use the `current` entry points. Old examples/reports retain delivery-time
behavior; no import alias or historical manifest is rewritten.

The additive current service reuses native M8 validation, the official OpenAI
adapter, request framing, response parser, model capability checks and token/cost
infrastructure. Its version bridge permits the v2.1 template name while applying
the unchanged v2 model-parameter capability checks; it does not rewrite the actual
request or audit to v2. Current configuration rejects legacy/mixed pairs. Old v2
remains available through its explicit historical route.

## Prompt and schema

The v2.1 template changes only INSTRUCTIONS, CONSTRAINTS and OUTPUT FORMAT. It
requires inspection and disclosure of applicable mandatory user-facing
qualifications, claim-material qualification in answer text, and disclosure of
uncertain applicability. Empty qualification arrays assert no applicable mandatory
disclosure exists. Role, goal, context, the seven-section structure and the short
Atlas example remain unchanged. The original response JSON schema and Python
relationship validators remain **grounded-response-2.0**, byte-identical.

## Deterministic checks and their limits

`QualificationValidator(evidence_service).validate(response, package, m7_result)`
first revalidates the complete package through real, explicitly selected M8. It
checks response shape and all authorized IDs before inspecting the parents cited
by claims. Detached metadata or a fake gateway cannot authorize a verdict. Source
or publication integrity failure raises; it is not converted into an ordinary
qualification outcome. The response is never edited.

Supported native explicit disclosure signals are
`consumer.publication_expiration.display_to_user_when_used` with its warning text,
and `llm_context.qa_observations[].display_to_user_when_used` with explanation text.
Duplicate warnings within a cited parent are counted once. Warnings without an
explicit display classification, general `mandatory` qualifications and
claim-specific applicability not expressed by metadata remain uncertain. Internal
`allowed_usage`, `forbidden_usage`, `complete_unit_only` and source-fidelity rules
are not reclassified as user-facing factual content.

| Verdict | Meaning |
|---|---|
| QUALIFICATIONS_VALID | No applicable mandatory disclosure is established, or every explicit disclosure has mechanically verified presence, with no unresolved applicability |
| QUALIFICATIONS_MISSING | Explicit applicable disclosure exists but the required qualification array is empty |
| QUALIFICATION_APPLICABILITY_UNDETERMINED | Native applicability is ambiguous, or nonliteral representation cannot be assessed deterministically |

Exact standalone metadata text in `relevant_qualifications` provides a mechanical
presence match only. It is not entailment, truth or semantic compliance. Paraphrases,
negations and unrelated nonempty strings do not receive a fabricated semantic pass
or automatic semantic rejection. Answer-text presence is reported separately;
placing a warning only in the answer does not satisfy the prompt's required array.
No lexical rule certifies that claim-material limitations are correctly applied.

The current generation wrapper returns `GENERATED_QUALIFICATIONS_MISSING` or
`GENERATED_QUALIFICATION_REVIEW_REQUIRED` for those outcomes, retaining original
response and measured usage. Only a valid machine presence verdict gets
`GENERATED_QUALIFICATIONS_VALID`; that still does not certify semantic answer
quality or full validation. The audit always states that semantic compliance is
unverified. No answer repair, warning insertion or generation retry occurs.

## Q05 offline finding

The successful historical Q05 response remains unchanged. Two claims and two
verbatim source matches still pass live M8-bound checks; exact historical v2
request replay passes. C03 has `mandatory: true` and source-use limitations, but
no explicit user-facing applicability mapping. Its new verdict is therefore
**QUALIFICATION_APPLICABILITY_UNDETERMINED**, with the empty array flagged and
owner review required. Copying every native limitation would not resolve the
classification uncertainty and is not automatically imposed.

Private review package: `data/evals/qualification-disclosure/successor-v1/`.
The changed v2.1 request has not been sent to OpenAI. Its real generator-token
count/context fit remain unqualified; the old v2 count cannot be reused. No source
classification, M8 contract or model/pricing change is proposed by this finding.
