# Hybrid PDF parsing and validation lessons

Recorded: 2026-10-19. Scope: C01/C06 hybrid reconciliation, the completed Phase 1A completeness guard, and the user's independent R01–R12 observations. This is engineering documentation, not authorization to remediate or promote content. Production remediation and Milestone 3 remain unstarted.

## Architecture and evidence boundaries

PyMuPDF remains the authoritative **original-extraction and provenance baseline** for this workstream: immutable source hashes, atomic block IDs, Unicode text, page locations and bounding boxes. The original PDF remains the visual ground truth; faithful preservation of a parser's output does not prove that the parser extracted the PDF correctly.

Docling supplies structural observations, including suggested paragraphs, headings and reading order. In the isolated hybrid experiment, the adapter reconciles cached Docling observations with original PyMuPDF blocks using source identity, text comparisons, character intervals, page coordinates and relationship evidence. Accepted experimental parent text is reconstructed from original spans; Docling text does not replace it. Coordinate origins and offset units must be explicit. Whole-block boxes do not establish per-character geometry.

Keep derived parents separate from immutable atomic blocks. A parent references ordered block spans and their hashes, source pages, heading ancestry and specialized-content dependencies. Mapping a suggestion to identifiable source spans establishes traceability; it does not establish complete coverage, correct paragraph boundaries, reading order or valid relationships. Docling suggestions remain subject to source verification.

These lessons refine the evidence requirements around the existing [architecture](architecture.md), [ingestion behavior](ingestion.md), and [decisions D011, D018 and D019](decisions.md). They introduce no replacement production architecture or validation policy.

## Independent human review: R01–R12

The user supplied visual observations in two batches, with ChatGPT technical support. All twelve observations are recorded separately from the frozen experiment. **Remediation has not been implemented.** R01 retains the user's “proposed review decision” qualifier. The following table paraphrases findings; exact submissions remain private. Page references are physical PDF pages.

| Case / source | Inspected evidence | Human observation and defect/reference finding | Required remediation | Current status |
|---|---|---|---|---|
| R01 / C01 | pp.4–5; b00099, b00101, b00102 | One continuous paragraph; no visible boundary before b00102. The prior reference split appears incorrect. | Retain one parent; version the reference correction without overwriting the old label. | Proposed human decision recorded; reference unchanged. |
| R02 / C01 | pp.6–7; heading b00131; b00132 and b00170 | Two distinct paragraphs beneath one heading, with intervening figure/table content. The prior reference incorrectly joins them; hybrid separation is supported. | Preserve separate paragraph parents and shared heading; version the reference correction. | Human finding recorded; reference unchanged. |
| R03 / C01 | p.10; b00238–b00239; omitted b00238[90:91] | One bibliography entry. The omitted hyphen is a printed line-break artifact; grouping is supported but accounting is incomplete. | Preserve the original character and record any reversible dehyphenation explicitly. | Human finding recorded; omission unresolved. |
| R04 / C01 | p.14; b00345–b00346; omitted b00345[92:93] | One bibliography entry. The omitted hyphen is a printed line-break artifact; grouping is supported but accounting is incomplete. | Preserve original provenance and explicitly account for reversible dehyphenation. | Human finding recorded; omission unresolved. |
| R05 / C01 | p.16; b00372–b00373; omitted b00372[93:94] | Bibliography grouping is supported. The omitted lexical hyphen is meaningful despite the line break. | Restore the hyphen in a new derived representation with its exact source span. | Human finding recorded; completeness still fails. |
| R06 / C06 | p.27; b00473–b00478; omitted b00473[97:98] | One continuous paragraph; the omitted compound-word hyphen is meaningful. | Preserve the hyphen and provenance before qualifying the parent. | Human finding recorded; completeness still fails. |
| R07 / C06 | p.28; b00494–b00495; omitted b00494[92:93] | One sentence; the omitted hyphen belongs to the model identifier `all-MiniLM-L6-v2`. | Restore the exact identifier and original span; do not normalize away its punctuation. | Human finding recorded; fidelity/completeness defect unresolved. |
| R08 / C06 | p.15; b00277–b00280 and detached b00289 | Paragraph grouping is supported. The omitted Ω attaches to Precision as an inline subscript, not to the paragraph end. | Add a source-backed inline-symbol relationship at the correct position and verify reconstruction. | Human finding recorded; parent remains HOLD. |
| R09 / C06 | p.15; b00281, detached b00290 and the following equation | The missing F₁ belongs in parentheses immediately after the F-score label. The equation is a separate related mathematical element. | Preserve symbol spans and inline placement; explicitly link the prose and equation. | Human finding recorded; parent remains HOLD. |
| R10 / C06 | p.27; b00479–b00482 and detached b00484 | One paragraph; the missing Ω attaches to Precision as an inline subscript, not as trailing text. | Preserve the symbol and source-backed insertion relationship; verify the result. | Human finding recorded; parent remains HOLD. |
| R11 / C06 | pp.13–15; heading b00241 and b00273–b00274 | The heading governs the discussion; its paragraph continues from p.14. Source text exists; derived heading ancestry is unresolved. | Resolve ancestry and complete paragraph membership while preserving boundaries and mathematical dependencies. | Human finding recorded; derived relationships unresolved. |
| R12 / C06 | p.42 heading b00755; p.63 table and b01021–b01022 | The table continues under the results heading. The two identified blocks are browser page furniture, not substantive section content. | Retain furniture in accounting; exclude it from substantive parent relationships/eligible evidence; validate table ancestry separately. | Human finding recorded; relationship/exclusion remediation pending. |

Block IDs in the table use the source prefix in the case column. Intervals are zero-based Unicode code points, end exclusive. No review time was supplied or measured in the recorded observations; elapsed chat time is not a substitute. These exposed, targeted cases do not estimate whole-document accuracy or review throughput. Receipt of observations does not constitute verification of corrected artifacts, content approval or formal milestone acceptance.

## Generalizable lessons

- **Continuation and shared headings are different relationships.** A paragraph can cross a page boundary; two paragraphs can share a heading without becoming one paragraph. Verify indentation, spacing, intervening content and reading order against the source layout. Semantic similarity alone is insufficient.
- **Hyphens require source-specific treatment.** R03–R04 support reviewed line-break dehyphenation; R05–R07 require exact meaningful punctuation. Applying one deletion rule to all five cases corrupts lexical forms or identifiers. Code and model identifiers require exact preservation.
- **Exact claimed spans can still be incomplete.** A parent hash can match its selected spans while those spans omit a prefix, internal character or suffix. Account for every character in the declared source scope, including punctuation and whitespace, or record an explicit reviewed transformation/disposition.
- **Detached symbols have positions and roles.** Preserve their original spans and attach them at source-supported inline locations. Appending an omitted symbol to the paragraph end does not restore mathematical notation. Equations remain distinct elements with explicit prose relationships.
- **Headings and page furniture require separate handling.** Headings may govern content across several pages. A native heading association inherited by browser headers/footers is not a substantive section relationship. Preserve excluded furniture in the audit ledger; tables and captions need their own ancestry checks.
- **Execution, fidelity and structure are separate claims.** Successful parsing and valid hashes demonstrate limited properties. Neither independently proves accurate extraction, correct grouping or sufficient downstream context.

## Reusable validation requirements

Keep three assessments distinct:

| Assessment | Question | Appropriate evidence |
|---|---|---|
| Source fidelity | Were source characters, critical tokens and locations extracted/preserved accurately? | Original-source comparison, exact spans/hashes, critical-token checks and accounted transformations |
| Structural correctness | Do paragraph membership, reading order, ancestry and specialized relationships match the source? | Source-layout references, explicit graph edges and independent structural labels |
| Contextual completeness | Is the surrounding source context/dependency available at the appropriate parent or later retrieval unit? | Parent/section links, dependency resolution and later chunk-context evaluation |

A faithfully extracted fragment can need parent context without being corrupted. Atomic blocks need not be independently understandable. Conversely, adding context cannot repair a missing identifier character or mathematical symbol. Existing eligibility policies remain unchanged; these distinctions guide a separately approved revision.

The following are reusable requirements, not claims that every check is implemented:

| Check | Required behavior | Phase 1A / follow-up |
|---|---|---|
| Span completeness | Validate bounds and exact reconstruction; find prefix/internal/suffix gaps, duplicate or overlapping claims; account for all characters within declared scope. | Guard implemented for referenced blocks of selected proposals; wholly unreferenced content remains outside its detection claim. |
| Critical characters/tokens | Compare numbers, operators, signs, symbols, code and identifiers exactly; fail unresolved changes even when aggregate scores pass. | Synthetic guard regressions exist; source-wide PDF fidelity qualification remains pending. |
| Transformation accounting | Retain original spans and before/after hashes; record rule/version, exact operation, offsets and review basis; reproduce and reverse the change without inventing text. | Reviewed dehyphenation/disposition mechanism not implemented. |
| Paragraph boundaries/joins | Check source-supported starts, ends and ordered membership; prevent merges across unrelated columns, sections or intervening specialized content. | Historical suggestions retained; human findings recorded; reference correction and fresh acceptance pending. |
| Cross-page continuation | Verify both page regions and any intervening context; distinguish continuation from a new paragraph beneath the same heading. | R01/R02/R11 provide diagnostic evidence; reusable qualification remains pending. |
| Heading graph | Resolve every accepted ancestry target to a source-backed heading; retain externally scoped references as unresolved until explicitly resolved; reject cycles and invalid ownership. | R11/R12 identify required distinctions; resolution not implemented. |
| Symbols/equations | Preserve original symbol spans, inline insertion positions and roles; link prose to separate equations without silently rewriting notation. | R08–R10 remediation pending; uncertain mathematical content stays HOLD. |
| Tables/captions | Keep their element identity, order and heading/prose relationships; verify cells, labels and numerical values separately. | No table qualification follows from heading review; uncertain content stays HOLD. |
| Page furniture | Use source-supported classifications and justified exclusions; preserve accounting; do not remove substantive content by visual resemblance alone. | Existing normalization audits remain unchanged; new R12 relationship treatment pending. |
| Provenance/reproducibility | Bind source/snapshot/block/span hashes, locators, implementation/configuration, review/reference versions and audit evidence; identical inputs reproduce stable outputs. | Guard integrity/reproduction evidence exists; actual attempt times remain separate from stable result identity. |
| Conservative qualification | Publish independent fidelity/structure outcomes and unresolved context; required missing/failed evidence prevents success; isolate critical hazards on HOLD. | No new PDF eligibility decisions or readiness clearance. |

Report accuracy **and coverage** per source and content type, with explicit denominators, abstentions, unresolved relationships and unassessed regions. Character coverage alone does not establish paragraph-boundary accuracy. Known accepted numerical, code, order or provenance defects cannot be hidden by aggregate thresholds.

## Stage ownership and reporting

The approved logical progression is **Acquisition → Parsing → Normalization → Quality Assurance → Ingestion Readiness Gate**. Each stage has one authoritative outcome per source and execution attempt. Supporting adapters/checks retain inspectable evidence; the stage owner consolidates it with component versions, artifacts, issues and provenance. QA preserves independent fidelity and structural assessments without concealing disagreement.

The existing authoritative quality engine owns content eligibility; only the readiness gate determines source readiness. The eventual Admin Dashboard consumes authoritative outcomes and provides drill-down; it never calculates competing stage statuses or readiness. Missing or unresolved required evidence prevents success. See the canonical [stage-result contract](stage-results.md) and [architecture](architecture.md).

Phase 1A exercised a private experimental reporting envelope: QA published partial outcomes, other stages/gate were not executed, and no eligibility/readiness decision was added. The later human submission did not rerun those stages. Frozen records that say review was pending describe their execution-time state; the appended human submission records subsequent observations without rewriting history.

## Current status and next checkpoint

Phase 1A completed as a **source-span completeness guard**, not production PDF remediation:

| Guard scope | Assessed proposals | Completeness passes | Unresolved terminal-hyphen cases |
|---|---:|---:|---:|
| C01 | 121 | 118 | 3 |
| C06 | 64 | 62 | 2 |
| Total | 185 | 180 | 5 |

All five known residues were detected; no repair was applied. Another 315 historical views were outside this selected guard scope. All twelve targeted human observations are recorded, while structural and source-wide PDF qualification remain pending. The nine original receipts and historical **40 eligible / 1,634 HOLD** decisions remain unchanged. No production remediation, new source acquisition or Milestone 3 chunking was initiated.

The **next proposed checkpoint** is bounded, versioned PDF reconciliation in the same workstream: preserve old labels and add reviewed reference corrections; account for the five hyphens through exact spans/reversible dispositions; model inline symbols and equation links; resolve heading ancestry and page-furniture relationships. Produce new derived evidence and regression/preservation results. Its detailed plan and execution require separate approval; documentation does not authorize it.

Before tuning that checkpoint, freeze fresh, independently source-reviewed acceptance examples and explicit criteria. Keep development and acceptance units separate, avoid shared-paragraph/page leakage, and disclose prior exposure. R01–R12 and the known residues become exposed regressions, not fresh acceptance evidence. Include cross-page joins/non-joins, headings, columns, meaningful and line-break hyphens, identifiers, symbols, equations, tables/captions and furniture. Report precision/recall, reading-order accuracy, complete-parent coverage and abstentions separately for C01/C06 and content type. Require full accounting/provenance for accepted scope, zero known accepted critical defects and HOLD for unresolved hazards. Re-review corrected artifacts; human observation receipt alone cannot qualify them.

Use actual measured review effort before expanding a review commitment. C02/C14 must receive separately authorized, version-pinned acquisition and source-specific qualification: this pilot supplies reusable checks, not evidence that their layouts or extraction are reliable. See [milestone boundaries](milestones.md) and [current quality/eligibility policy](content-validation.md).

## Supporting source-of-truth records

Public architectural authority remains in the documents linked above. Private links below resolve in the current working copy; they are intentionally absent in a clean checkout and must not be replaced with fabricated evidence or copied corpus content:

- [Independent human findings summary](../workspace/pdf-remediation/review/submissions/human-review-2026-10-19-v1/SUMMARY.md): paraphrase basis for R01–R12; [structured receipt](../workspace/pdf-remediation/review/submissions/human-review-2026-10-19-v1/observations.json) preserves exact submissions and fingerprints.
- [Phase 1A results](../workspace/pdf-remediation/RESULTS.md) and [final guard manifest](../workspace/pdf-remediation/runs/f22c71c6ae2777a2b5169923ff0d23faf616cb6af8ab7b5f39158b1adc7b81fa/manifest.json): measured guard scope/findings; [preservation evidence](../workspace/pdf-remediation/preservation.json) binds historical integrity checks.
- [Earlier hybrid experiment results](../workspace/hybrid-pdf-experiment/RESULTS.md): original provisional comparison and reference limitations; no retrospective rescoring is implied.

Private source text, PDF page images and exact review submissions remain outside version control. No user-specific absolute paths are needed to reproduce the documentation trail.
