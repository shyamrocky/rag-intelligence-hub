> Current HTML admission successor: see [automatic HTML qualification](html-automatic-admission.md).
> The predecessor results below are preserved historical scope; current opt-in publications do not rewrite them.

# HTML support in the existing QA framework

HTML QA v2 is implemented and tested in an isolated candidate. HTML dispatch has
not been applied to main because the PDF admission workstream owns overlapping
files. That workstream changed three shared files during the final preservation
audit. The HTML patch must be coordinated/rebased against its completed baseline;
earlier patch checks do not qualify the newly changed checkout. This HTML work
changes no historical decision, parser, source artifact or application default.

`html_validation.py` supplies source-specific evidence and enriches the existing
`ValidationResult`; `shared.qa.assess` remains the only QA owner and still calls
the baseline `validation_reviews.make_decisions`. There is no second eligibility
engine. `ValidationPolicy` still permits automatic promotion only for C04 MDX.

The staged dispatch changes only `content_validation.py` (an optional evidence
field and HTML result enrichment) and `shared/qa.py` (an optional evidence input
and the HTML dispatch seam). The PDF and Markdown branches are unchanged. The
exact patch and coordination instructions are in
`workspace/html-qa-v2/INTEGRATION_HANDOFF.md`.

## Evidence and outcomes

Frozen HTML manifest, raw/snapshot bytes, acquisition receipts, parsed blocks,
normalized Sections and structural trees are verified offline. One read-only
lexical tag/text scan per source checks the persisted raw DOM claims; it does not
rerun the maintained article parser or regenerate canonical corpus artifacts.
No website, browser, script, MDX component or source example is executed.

Applicable checks cover identity, artifact bindings, complete DOM children and
locators, source text, raw spans, source order, paragraph element boundaries,
heading ownership/scope, hierarchy gaps, code whitespace/fences, list/table markup,
context containers, furniture, citations and selected-body text accounting.

- Technical **PASS**: the applicable automated claim is supported by the pinned
  source and structure. It is not semantic correctness or indexing permission.
- **HOLD**: evidence or dependency meaning is missing, ambiguous or unreviewed.
- **FAIL**: source bytes, text, locators, structure or another required claim is
  demonstrably inconsistent. This cannot be cleared by a review override.
- `not_applicable`: the check does not apply to this record; it is not a PASS.

All 457 Sections have meaningful staged QA results: 388 technical PASS, 69
technical HOLD, zero demonstrated FAIL. All 457 retain independent-fidelity HOLD
and effective eligibility HOLD; zero new approvals. Source-wide qualification and
readiness are not established. The source/CSS/browser view, implicit context,
whole semantic paragraphs, table numerical meaning and visual content remain
outside automated certification. Existing generic contextual reasons stay intact.

## Future source-specific review contract

`html_reviews.HtmlReviewReceipt` composes the existing `QualityReview`. It binds
the corpus and Section, original/canonical URLs, snapshot and normalized hashes,
DOM/raw interval/fragment, citation locators, heading path, container/heading/
neighbor dependencies, current checks/result hash and QA artifact. It requires
versioned reviewer decisions and hash-bound source/QA/evidence references.

`validate_receipt` requires the exact submission hash from separately trusted,
explicitly owner-confirmed input. The receipt cannot confirm itself. It reuses
the existing `review_map` checks for policy/sample/role, stale evidence and
integrity/high-risk restrictions. No HTML manual-approval override is accepted.
`validate_cohort` requires exactly the declared IDs, without duplicates or extras.
Local receipts are operator attestations, not cryptographic signatures.

Missing confirmation, source/QA evidence, stale context or forged submissions fail
closed. A valid receipt returns a review only. It cannot clear source-level or
Section dependencies and cannot create eligibility. An eventual precisely scoped
admission policy/authorization must enter the same existing QA/decision authority;
neither technical PASS nor a review preview activates that future path.

## Offline artifacts

`data/validation/html/v2/manifest.json` binds eleven per-source results,
`identity.json`, `review-bindings.json` and `review-receipt.schema.json`.
Per-source files include applicable checks, original existing-framework results,
HOLD decisions, current policy/sample and future review bindings. Enumerating
possible review bindings does not request review of all 457 or create labels.

For an offline consumer, verify the manifest identity with
`digest(encode(manifest_without_manifest_identity_sha256))`, every declared artifact
hash, and its `identity.corpus_manifest_sha256` against the current frozen HTML
manifest before reading any result. Deserialize `shared_QA.validation_results`
and `quality_decisions` through the unchanged existing models. No acquisition,
parsing, QA rerun or admission is needed to read these persisted results.

`data/validation/html/v1/` and the historical 40 eligible / 1,634 HOLD ledger stay
unchanged. C04 remains 40 eligible / 118 HOLD. Results, controls and the smallest
remaining owner action are in `data/validation/html/v2/HTML_QA_REPORT.md`.
