# Content quality validation — Milestone 2.5

**Forward status — October 25, 2026:** This page preserves historical Milestone 2.5 policy/results. Current admission authority and explicit publications are documented in [current operations](current-operations.md#read-the-qa--unified--m3--m4-chain). Historical HOLD records do not override selected successor admissions; the current corpus retains 358 QA HOLD and 110 exclusions.

This stage validates the immutable Milestone 2 output. It adds no chunking, embeddings, indexing, retrieval, generation, UI or HTML/URL acquisition. It does not overwrite ingestion records or original review receipts.

## Run commands

```sh
uv run --locked rag-hub validate-content
uv run --locked rag-hub validate-content --expand-cohort C04:prose --reviews workspace/milestone2.5-review/reviews.json
```

The first command produces checks and a private review queue; it cannot newly auto-promote anything without complete representative review. The second reproduces the completed review run when the original private files and receipts are available. Public metadata policy: `config/validation-policy.json`. Source text, review material and outputs remain gitignored.

Commands also support `--root`, `--policy`, `--role calibration|acceptance`, `--exclude-samples` (private JSON list of prior calibration IDs) and repeated `--expand-cohort` arguments. A future rule fix must exclude previous calibration IDs from the new acceptance sample; unavailable required coverage keeps the affected qualification blocked. Calibration alone cannot authorize promotion.

## Components

| Module | Responsibility |
|---|---|
| validation_models.py | Separate typed policy, check results, review evidence and decisions |
| source_fidelity.py | Independent raw Markdown line/fence/metadata comparison and conservative context checks; never calls ingestion parsers |
| content_validation.py | Pins all eight input artifacts, verifies raw/snapshot hashes and original receipts, validates every baseline HOLD record, assigns risk/reasons |
| validation_sampling.py | Stable seeded selection, metadata/page/hazard coverage expansion, cohort follow-up and disjoint selection |
| validation_reviews.py | Validates hash-bound reviews, qualifies cohorts and applies fail-closed promotion rules |
| validation_pipeline.py | Produces immutable private validation runs and approved-content/HOLD manifests |

## Checks and risk

Every baseline HOLD section receives integrity, provenance, audit, source-fidelity and contextual checks. Source/normalized/block hash mismatch, wrong ancestry/provider labels, unaccounted transformations, invalid locators or changed source bytes cannot qualify. The policy pins the existing 1665 HOLD records and nine original approvals.

Low risk is limited to Markdown records without recorded/new hazards. It is a candidate class, not approval. Medium PDF prose/headings require visual/source review. High includes uncertain tables/equations/images, glyph damage, fragments, unsupported markup or detected integrity hazards. Unknown issues escalate rather than disappearing. Risk labels prioritize review; they do not establish absence of a formula/table. Some mathematically named prose and inline parameters/URL query strings trigger conservative false positives.

The Markdown verifier independently compares raw original spans and canonical output, accounts for fence/MDX indentation changes, and checks heading/provider/code-group identity. It does not execute source code or import providers. AST parsing checks standalone Python syntax/bindings; it is not proof that vendor examples run correctly. Conservative shell grammar may reject valid quoted installs. These false positives stay held rather than broadening the accepted grammar during review.

Prose/context checks flag fragments, list items, unresolved references and bare headings. These heuristics are incomplete: representative review found an implicit-context miss in tutorial outro prose. Therefore C04:prose is blocked as a whole, including its ten otherwise passing candidates. This is an unresolved validation-rule defect contained by the cohort gate, not a repaired source or a claim that all context can be validated automatically.

## Qualification and promotions

Automatic promotion requires **every individual check to pass**, low risk, C04 Markdown eligibility and a qualified cohort. Acceptance review must be complete; source/type/provider/language/code-group/length coverage and minimum eligible passing examples must be present. A defect or reviewer disagreement blocks the entire affected cohort; sample success never approves medium/high neighbors. Required marginal coverage is tracked separately from finer per-cohort metadata coverage, which may remain missing for deliberately held hazard cohorts.

Review evidence binds exact source/section hashes, policy, validator implementation and sample fingerprints. Changing rules invalidates old evidence. Unknown policy versions, stale/duplicate receipts, missing reviews, calibration-only evidence and unresolved contextual blockers cannot authorize promotion. Automated and manual evidence bases are distinct. Existing manual receipts are rechecked, not relabeled as automated verification.

No medium/high automatic promotion exists. A new medium-risk manual approval requires explicit visual-source evidence and no unresolved context/hazard/integrity reasons. This run creates no new manual PDF approvals.

The nine original source-check receipts and original statuses remain unchanged in the ingestion run. The stricter new manifest suspends seven earlier approvals because their samples depend on adjacent formulas, prose or external code bindings. Source-fidelity evidence remains preserved; it does not prove context completeness. Two original C04 code approvals remain eligible under the new policy.

## Actual reviewed result

Validation run: `bf9ec63f85912861a86677647d2056a6e23a7e0758315682cec29d78c0fe4580`.

- 1665/1665 baseline HOLD sections checked; 149 low, 923 medium, 593 high.
- Sample: 125 initial, 148 after coverage expansion, 195 after C04 prose follow-up census. All 195 have Codex source/visual triage records: 27 pass, 167 confirmed HOLD, 1 rule defect. This is not independent human certification or an accuracy confidence bound.
- 38 newly automated approvals, all low-risk C04 code; 2 retained original manual approvals, also C04 code. No new manual approvals.
- 40/1674 sections eligible; 1634 held in the new manifest. Of these, 1627 were in the baseline HOLD set and 7 are suspended original samples. C01/C06 currently have no eligible sections in this stricter manifest.
- C04 prose requires a versioned contextual-rule fix and fresh disjoint acceptance review; no such fix is silently enabled here.

Low-risk cohort counts do not imply substantive question coverage. The resulting subset is code-heavy and not a three-document retrieval-ready corpus. Indexing/answer evaluation is still future work.

## Audit artifacts

Each `data/validation/<run-id>/` contains `policy.json`, `identity.json`, `results.jsonl`, `sample.json`, `review_queue.jsonl`, `reviews.json`, `decisions.jsonl`, `approved_manifest.json`, `holds.jsonl`, `original_reviews.json` and `report.json`. Identity includes source artifact hashes through policy, policy version, validator implementation, dependencies, lockfile, sample and supplied review evidence. Identical inputs reproduce all artifact bytes; changed existing artifacts are rejected.

The approved manifest is the proposed handoff for later chunking. Its source/receipt/policy freshness must be checked by that future consumer; an arbitrary approval field is insufficient. Source eligibility is not permission to redistribute, a searchable index or answer-quality evidence.

## Future PDF prose eligibility — criteria to investigate, not enabled

1. Recover complete paragraphs and reliable heading ancestry with exact span/neighbor lineage; preserve or resolve references before considering approval.
2. Confirm reading order, page/column boundaries and layout containment against original page images. Avoid table/math/figure regions and neighboring fragments; do not trust the current prose label alone.
3. Compare independent extraction methods as a disagreement detector after a separate parser/dependency decision; agreement alone is not proof.
4. Establish source/parser/layout-specific challenge sets with independently reviewed positives and difficult negatives, including formula fragments currently labeled prose, captions, bibliographies and mid-sentence page splits.
5. Validate candidate rules on fresh held-out material, document false-clear/false-HOLD behavior and require explicit approval of any future PDF automatic route.

HTML parsing and controlled URL acquisition remain required for later 16-source V1 expansion. They need their own format-specific validation cohorts and are not implemented in this milestone.
