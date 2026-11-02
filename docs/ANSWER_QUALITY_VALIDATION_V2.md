# Post-generation answer-quality validation v2

**October 29 update:** the [local human-review workflow](HUMAN_REVIEW_WORKFLOW.md)
now supplies authenticated reviewer/artifact trust through explicit enrollment and
per-answer signatures. It reuses the existing importer below and unchanged quality
policy. Real owner enrollment/Q04 confirmation have not been performed. Historical
statements below describe the original v2 delivery boundary.

D052 approves the architecture. Implementation is a bounded experimental successor, pending owner technical review. Historical `tools/quality_dashboard/post_generation.py` and all original verdicts remain unchanged.

`tools.answer_quality.validator.PostGenerationValidator` reuses the exact public M8 validation, query normalization and native qualification reader. The native runner supplies its already requalified request-binding row. It reports schema validity, strict citation integrity, quotation fidelity, claim support, requirement completeness, qualifications/conflicts and an overall outcome separately. No model invocation or gold-label scoring occurs in the validator.

## Quotation fidelity

Raw exact checks remain diagnostic. Limited prose whitespace and curly quotation-mark normalization retain exact original character offsets, field and passage hashes, and native locators. These offsets are audit positions in decoded fields, not new publication/citation precision. Code, table-like text and technical-symbol contexts are conservative. General punctuation, hyphens, numbers, units, comparison operators and negations remain unchanged. A bounded comma/terminal-period difference returns INDETERMINATE until a trusted, span-bound independent human review confirms meaning preservation; it is never automatically accepted or labeled a factual error. Commas inside numbers and periods inside technical tokens are not normalized.

Line-end word splitting is ambiguous in general. An unreviewed `adapt-\nability` candidate returns `INDETERMINATE`. A trusted span-bound layout review may permit that exact rejoin; the algorithm checks the field hash, quote hash, same Unit and span, and allows only lower-case line-end word joins. Meaningful ordinary `pre-retrieval` hyphens remain intact. There is no dictionary, question-ID rule, fuzzy matching or global hyphen deletion. The Q04 investigation supplies previously reviewed forensic span evidence, explicitly distinct from independent human semantic acceptance.

In-memory fidelity results include original source text. Persisted/dashboard receipts remove that text, retaining pointers, offsets, hashes and locators. Neither complete parents nor full prompts enter dashboard records.

`SUBSTANTIVE_MISMATCH` means the text cannot be certified as a quotation under this policy. It is not alone proof that a paraphrased claim lacks support. A claim may be supported by authentic content elsewhere in its cited parent; a selected-quotation coverage gap is recorded separately. Presenting an invented/paraphrased string as a source quotation still blocks full validation, under `SUBSTANTIVE_MISQUOTATION`, never `INVALID_CITATION` solely for formatting.

## Independent semantic assessment

`SemanticAssessor` is an evidence-aware, read-only interface. The assessment binds exact question, response, package, request and claim hashes, evidence-field hashes and source spans. It includes a reviewed inventory of question requirements, claim rationales, qualifications/conflicts, uncertainty and response-status appropriateness. The reviewer must consider factual statements in the answer beyond the model's declared claim list and attest that inventory is complete. M9 groups can inform offline evidence availability; no automatic inference of correctness or exhaustive relevance is made.

`HumanReview` imports an externally trusted hash-bound review artifact and approved reviewer identity. That identity and hash must come from application-controlled review configuration, never from model text or a self-supplied assertion. Local hashes attest integrity, not reviewer identity/competence or cryptographic approval. A complete authenticated human-review workflow and independently qualified reviewers remain operator responsibilities.

`LLM_JUDGE`, `ASSISTANT_ANALYSIS`, and `OFFLINE_FIXTURE` results are provisional. A model judge can implement the same interface, but there is no provider adapter or paid judge invocation in this implementation. No favorable model assertion can override citation failure or produce `VALIDATED` without independent human acceptance. No numerical confidence or lexical entailment proxy is used.

## Acceptance

- Source/request or citation failure: `VALIDATION_FAILED`, before semantic assessment.
- Invalid structure or substantive misquotation: `VALIDATION_FAILED` in its own dimension.
- Established material unsupported/contradicted claims, undisclosed material caveats/conflicts, or an inappropriate complete-answer declaration: `VALIDATION_FAILED`.
- Missing/provisional/uncertain semantic or material-disclosure assessment: `REVIEW_REQUIRED`.
- Complete, independently accepted claim support and requirements/disclosures, with technical checks passing: `VALIDATED`.
- An appropriately disclosed partial answer or justified abstention can be validated only when independent review explicitly confirms its status is appropriate. A model's declaration alone is insufficient.

No semantic reviewer is configured by default in the native runner. Its future responses therefore retain `REVIEW_REQUIRED` unless deterministic failures occur. This is honest missing evaluation capability, not demonstrated automated answer-quality success.

## Invocation and verification

```python
from tools.answer_quality.validator import PostGenerationValidator
validator = PostGenerationValidator(existing_evidence_service)
# Existing runner has reconstructed the exact request and verified its sealed recipe.
result = validator.validate(response, package, m7_result,
                            question=original_question, request_binding=qualified_row)
```

The read-only runner dashboard discovers separately sealed matching answer-quality assessments by question ID, response hash and request hash. It displays dimensions, claim rationales, requirements and review reasons; raw records are expandable. Refresh performs no validation, reconstruction or provider operations. Historical quality-dashboard counters retain their existing native-run ingestion limitation; no broad redesign is included.

Offline regression command:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m pytest tools/answer_quality/tests tools/generation_runner/tests tools/quality_dashboard/tests/test_post_generation.py
```

No generation, authorization issuance, retries or provider access is authorized by these instructions. See the [Q04 separate assessment](../data/evals/answer-quality/q04-v2/REPORT.md) for actual measured and pending dimensions.

## Fidelity successor 2.1 — October 29, 2026

`POLICY_2_1.json` and `validator_v21.py` add `quotation-fidelity-2.1`. The
historical `POLICY.json`, matcher and default v2.0 evaluation remain replayable.
The native runner uses the successor for future results. Review packages select
an explicit policy/hash; existing decisions continue to bind their old policy.

The only new automatic case operation is **The/the at the beginning of a prose
sentence**, with a lowercase next word, unique full quotation alignment inside
that same supplied Unit and all other normalized characters unchanged. Code,
operators, abbreviations and ambiguous matches do not qualify. This does not
case-fold identifiers or arbitrary words. Existing PDF line-end word rejoining
still requires a separately reviewed, exact field/quote/span/layout binding;
normal hyphens, numbers, units, negations and substantive wording remain strict.
Raw exact diagnostics and original source offsets remain in each receipt.

R03's page-8 split was inspected against the original C02 PDF line boxes and
rendering. Its separately sealed successor assessment accepts 6/6 quotations
(3 exact, 3 presentation-equivalent); the original failure is unchanged. Core
question coverage is provisionally complete, but additional BM25/QA assertions
and declared ANSWERED appropriateness still require owner judgment. Neither
presentation equivalence nor a Codex assessment establishes human acceptance.
See [R03 stabilization report](../data/evals/generation-runner-reviews/r03-stabilization-v1-review/REPORT.md).
