# D052 — Semantic Grounding as the Primary Post-Generation Validation Criterion

- **Version:** 1.0.
- **Date:** October 29, 2026 (America/Los_Angeles).
- **Status:** Accepted — architectural direction approved by project owner; implementation and automated semantic evaluation remain pending verification and owner technical review.
- **Authority:** Explicit owner “Semantic Grounding & Answer Quality Validation v2” instruction, including ADR requirements. This records that instruction, not a cryptographic identity assertion.
- **Implementation:** [Validation v2 contract](../ANSWER_QUALITY_VALIDATION_V2.md), [versioned policy](../../tools/answer_quality/POLICY.json), [validator](../../tools/answer_quality/validator.py), [external assessment contract](../../tools/answer_quality/review.py).

## Context and problem

M9-Q04's live canary produced authorized citations but failed the historical character-for-character quotation check. The sealed investigation mapped all eight quotations to the same authoritative cited Units: six differ only in whitespace/line breaks; two also rejoin words split by PDF line-end hyphenation. It found no fabricated quotation content or incorrect source attribution in those eight passages. Main claims appeared supported in the bounded assistant analysis, but independent semantic certification remained pending. One indexing-optimization subclaim has support elsewhere in its cited parent rather than in its selected quotations.

The historical validator grouped quotation failures under `INVALID_CITATION`, conflating distinct dimensions. A source being authorized does not establish that a claim is supported, and a raw formatting mismatch does not establish a factual error.

Supporting immutable records:

- [Original Q04 canary report](../../data/evals/generation-runner-reviews/live-q04-native-canary-v1/REPORT.md), native manifest SHA-256 `5672e13e710d38f84bd97c3c994d2892ffe9b000723c663a58e3e978419c1038`.
- [Quotation investigation](../../data/evals/generation-runner-reviews/q04-quotation-investigation-v1/REPORT.md), [matrix](../../data/evals/generation-runner-reviews/q04-quotation-investigation-v1/QUOTATION_MATRIX.json), manifest SHA-256 `e47ce47b390eeb6261571724a9afc54fbff29189db1a15c9747104486693df63`.

## Decision

Independently report five answer-quality dimensions, with structural/schema validity as an additional technical prerequisite:

1. **Citation integrity — strict and mandatory.** Validate authorized included source IDs, publication provenance, source hashes, question/package/request bindings and claim-reference structure. Semantic approval cannot override unauthorized citations.
2. **Quotation fidelity — presentation tolerant.** Permit bounded, traceable formatting equivalence; retain raw exact diagnostics. Each accepted quotation maps to an original span of the same cited Unit. Reject substantive misquotation. A paraphrase can support a claim without qualifying as a verbatim quotation.
3. **Semantic grounding — primary quality criterion.** Independently assess every material factual claim against its cited evidence and relevant supplied context. Citation presence and string similarity cannot establish support.
4. **Answer completeness — primary quality criterion.** Assess all question requirements, appropriate partial answers and abstention. M9 human-approved known-positive OR/AND witness groups inform evidence availability; they are not exhaustive semantic labels or automatic answer-correctness judgments.
5. **Qualifications and conflicts — mandatory assessment.** Assess material restrictions, disclosures, limitations and conflicting evidence. Unresolved applicability cannot silently pass.

Harmless PDF formatting differences alone must not classify an answer as factually wrong. Outcomes are `VALIDATED`, `VALIDATION_FAILED` and `REVIEW_REQUIRED`. Essential unresolved semantic or disclosure assessment yields `REVIEW_REQUIRED`. An optional separately authorized LLM judge is provisional; independent human acceptance remains distinct.

## Alternatives considered

- Retain raw character matching as the overall gate: simple and reproducible, but creates factual-error verdicts from layout changes without evaluating meaning.
- Force the prompt to reproduce PDF newlines/hyphens: may improve exactness but prioritizes extraction formatting over answer quality and leaves semantic evaluation unresolved.
- Broad fuzzy matching: risks erasing numerical, negation, unit, technical-symbol and compound-hyphen differences; rejected.
- **Presentation-tolerant fidelity plus independent evidence-aware semantic assessment: selected.** Aligns acceptance with grounded, complete answers while preserving strict source authority and auditable mechanical diagnostics.

## Consequences and tradeoffs

This reduces false failures from PDF extraction while retaining provenance enforcement. Semantic review adds complexity, uncertainty, possible cost and latency. Model judges can err, share generator biases and need independently reviewed benchmark qualification. No model judge is invoked or automatically qualified by this ADR. Exact, presentation-equivalent and paraphrased text remain distinguishable. Ambiguous typography and semantic issues require explicit review rather than permissive normalization.

## Implementation, auditability and remaining work

The new versioned native reporting path uses `post-generation-validation-2.0`; the old validator and sealed Q04/Q05 verdicts remain unchanged. A successor trust baseline records authorized implementation hashes; it issues no generation permission. Source authority, authorization freshness, single-use controls, durable attempts, spending caps and zero retries are preserved.

The separate Q04 v2 assessment records presentation findings and provisional assistant analysis. It does not retroactively upgrade the original failure or establish human acceptance. Future human-review imports require an independently trusted artifact hash and reviewer identity; authenticated review workflow/competence remain deployment responsibilities. Optional judge execution needs separate authorization, provider privacy/cost review and evaluation qualification.

Acceptance of this architectural direction does not accept the technical milestone, certify automated semantic coverage or authorize Q04 regeneration, pilot/full generation, new provider calls, or M7/M8/prompt changes.
