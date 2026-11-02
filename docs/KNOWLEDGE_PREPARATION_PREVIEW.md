## Question summary on evaluation and review pages

Post-Generation Evaluation and Human Review begin with the same read-only summary
of benchmark and Bot questions. The native table has a 390px viewport (about ten
35px rows plus its header) and scrolls vertically/horizontally. Source and execution
filters affect this summary only. Existing detailed selectors, attempts, diagnostics
and owner decision controls remain below; the table cannot run or approve anything.

Rows show the latest logical question attempt, answer/abstention preview or a
rejected-output diagnostic, model declaration, technical validation and owner-review
state separately. Mock, discarded, pending and rejected entries remain explicit.
Cost (USD) uses the selected attempt's actual token usage and saved pricing, not
preflight reservations or an invoice; unavailable values do not become zero.

Timing uses recorded exclusive spans to avoid nested double counting. Matching
sealed Bot dispatches supply whole-request totals and serial local/qualification/live
stage measurements. Historical runner/local-check totals are labeled with their
narrower scope. **Other processing**, immediately before Total runtime on both pages,
is derived from that total minus context assembly, pre-generation and generation
using unrounded values in the same scope. It includes omitted processing and
unattributed time, not an independently measured stage. If any required timing is
missing, the remainder stays Not measured; rounded display values can differ slightly.
Missing or unverified timings are not inferred. Total time also
includes retrieval, other checks, validation, persistence and review handoff where
that full scope was recorded. Generation is local request elapsed time, not
independently measured provider inference latency. No experiments or requests run
on refresh; no benchmark labels, approval records or source artifacts are changed.

# RAG Bot foundation and Knowledge Workspace preview

An isolated PDF / Markdown / HTML Knowledge Preparation workspace for owner review. This prototype
uses the existing dashboard environment, native components and a small static CSS
layer. It reads four PDFs, C04 Markdown and eleven HTML documents from the accepted durable publication
through the existing native validated corpus and chunk readers.
It does not change the canonical dashboard, its trust bindings or historical views.

From the project root:

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/knowledge_preparation/app.py --server.address 127.0.0.1 --server.port 8516 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8516> for the new RAG Bot design foundation.
Knowledge Preparation now opens at <http://127.0.0.1:8516/knowledge-preparation>.
Port 8514 remains the preserved canonical Master Dashboard.
The sidebar provides the overview and five knowledge-stage views. Every detail
page has a short Focus line below its heading. The shared breadcrumb includes
a Knowledge Preparation overview link; consistent top clearance keeps it below
the Streamlit toolbar, including compact and narrow-screen layouts. Subpage
headings have no extra top padding and a small shared gap beneath the breadcrumb;
the toolbar clearance is retained. The overview starts with a clickable pipeline,
then format/source scope controls, metrics, the source disposition breakdown and
source inventory. A subtle horizontal divider separates the inventory heading
from the source cards. **All formats** aggregates the sixteen connected sources; **PDF**, **MARKDOWN**
and **HTML** restrict totals to their respective published source sets.
Choosing a document restricts all overview counts and its disposition breakdown.
C04 is the one published Markdown source. The eleven existing HTML publications
are included; no new source acquisition is performed.
Scope is labeled explicitly, retained across navigation and applied to counts.
The Sources metric card also shows parsed-block, canonical-Section and admitted-
Section totals for that scope. Admission is the later QA disposition, not a
parsing decision; these counts are not a one-to-one conversion into units. The object-count caveat sits above the cards; the repeated flow-total
caption is omitted.

| PDF | Source | Sections | Evidence units | Chunks / embeddings / each index export |
|---|---|---:|---:|---:|
| C01 | Original RAG paper | 406 | 61 | 88 |
| C02 | Gao RAG survey | 453 | 50 | 106 |
| C06 | Evaluating Chunking Strategies | 1,095 | 128 | 140 |
| C14 | Lost in the Middle | 471 | 73 | 94 |
| Total | PDFs only | 2,425 | 312 | 428 |

**Inspect source** opens that specific document. Each detail page also has a
source selector; the selection persists across stages. Switching the document
resets its evidence unit, chunk and section pagination/filter selection to avoid
cross-document content. Detail pages inspect one source at a time, while the
overview provides aggregate and document scope.

**Choose evidence unit** appears inside QA & Verified Evidence immediately before
the selected unit relationships/content, including on the combined tabbed route.
It is absent from page-level Parse/Normalize controls. Related chunk/embedding/
validation views retain their existing evidence selectors; selection persists
across these views. No selector appears on the overview or Sources. On chunk and embedding pages, select one
of its related chunks. Detail pages link back to the overview. Technical details
use native expanders. Overview links open dedicated **Parse**, **Normalize** and
**QA & Verified Evidence** detail routes. The original Parsing & Evidence route
is preserved, with those three steps as tabs. Process-stage pages show Input,
Output and Previous/Next links while preserving source context.

The user-facing process is **Acquire → Parse → Normalize → QA & Verified Evidence
→ Prepare & Chunk → Embed & Index → Validate & Publish**. These process stages
are distinct from engineering milestone IDs. Acquire/Parse/Normalize and native
QA publication precede M0. M0 defines the common ChunkInput contract; M1 prepares
and profiles already verified inputs; M2/M3 split and catalog retrieval chunks.
This mapping is expandable on the overview and chunk detail page. Validation and
publication happen at several stages; the final view checks the composed chain.

Parse has a compact Focus line and grouped Extraction summary / Extracted block
records, with expandable parser provenance. Previous / Next browses groups of up to 25 rows, not PDF pages; the record range
and current/total pages are displayed. Normalize uses the same controls with
filtered totals. First/last-page buttons are disabled; source/filter changes
reset pagination and empty results are explicit. Numeric page inputs are removed.
Next: Normalize preserves source context.

Parse displays only hash-bound saved block metadata: IDs, types, sequence and
locations. It does not expose raw unverified block text. The four PDFs have
409/459/1,271/471 parsed blocks respectively (2,610 total), distinct from their
canonical Section counts. Normalize displays canonical structure and mappings;
later QA dispositions are clearly identified as QA findings. QA & Verified
Evidence explains scope eligibility, unit memberships, complete context and
qualifications without certifying publisher factual correctness. Actual source
text remains behind native evidence authorization, with all required disclosures.

PDF-only scope reconciles 2,425 canonical Sections (1,991 admitted, 358 HOLD, 76
excluded), 312 verified evidence units and 428 retrieval chunks. Adding C04 makes
the connected scope 2,583 canonical Sections (2,145 admitted, 358 HOLD, 80 excluded),
398 units and 637 chunks. Saved embedding and vector/BM25 export inventories each
bind those same 637 connected chunks.
Counts are derived from validated artifacts, not application fixtures. The native
shared loader verifies its full publication composition; the UI exposes the accepted PDF, Markdown and HTML sources.
Document projections do not mutate the shared snapshot and reject out-of-document
Unit and Chunk IDs. C01 retains its previous 61-unit/88-chunk bindings unchanged.

Sources uses a compact layout with a Focus line and persistent source selector.
The selected title appears once in the detail content, followed by the safe
publisher link. All original fields are retained in Document and Acquisition &
Permissions groups; frozen source hashes/version/publication remain in collapsed
Technical provenance. The acquisition notice and snapshot-validation explanation
remain visible, with Next: Parse carrying the selected source forward. Parsing & Evidence shows
recorded parser/normalization structure, disposition filters, section-to-unit roles
and a complete authorized parent. Chunks & Lineage displays the validated search
slice alongside its full parent and source obligations. Its structure-aware
chunking introduction is followed by a compact Source relationships summary for
the chosen parent/chunk: parent Section membership count, evidence ordinal,
chunk ordinal/sibling count and original document/source locations. These are
saved connections, not processing order; parent membership does not imply every
Section occurs in the selected slice. Existing detailed lineage table and
collapsed hashes/bindings remain available. The technical walkthrough is labeled
How evidence becomes searchable chunks, with Input contract, Evidence preparation,
Structure-aware chunking and Chunk catalog & lineage steps; engineering milestone
numbers remain in the architecture documentation. Embeddings & Indexes shows
model/configuration metadata and exact saved-export associations. Validation &
Publications distinguishes checked identities from operations that were not run.

No parsing, normalization, chunking, embedding, retrieval or index build is rerun.
No generation/provider calls or credentials are used. No Chroma database is opened;
index views verify published export bindings, not current physical database health.
Numerical model correctness and retrieval quality are not recertified. Automatic
source refresh is not configured by this UI. Source sections on HOLD or excluded
remain metadata-only and cannot be opened as authorized evidence.

The initial native snapshot can take tens of seconds to validate. Streamlit keeps
a resource snapshot with native filesystem leases; evidence is opened and validated
on demand. Changed source bindings fail closed; no detached source fallback exists.
No full-source payload or new evidence package is written. No dependencies added.

The owner-approved visual refinement uses the macOS system font where available,
with platform fallbacks, a larger editorial heading, compact overview spacing, neutral
surfaces and explicit keyboard focus outlines. No remote fonts or Apple assets
are downloaded. Styling is local to this standalone process, not shared config.
The overview uses a muted gray canvas, white sections and strong dark headings.
Pipeline stages have centered numbers/titles and subtle vertical separators
(horizontal separators when stacked on narrow screens); excess section spacers
are removed. These presentation changes do not affect source readers or routes;
Sources and the Parsing & Evidence flow use compact spacing with small gaps
between headings, controls and tables; other detail pages retain their layout. Search Indexes explicitly shows
the separate dense (embedding/vector) and lexical (BM25) paths.

Other-format expansion, canonical navigation integration, any required reviewed
trust migration and publication controls remain future work requiring owner approval.

QA relationship guidance uses plain language: the table identifies the Sections
providing main evidence, headings and supporting background. A Section can appear
in several units; headings/background are not standalone evidence. The complete
unit is checked against its saved source, and document text remains reference
material rather than instructions. Engineering milestone references remain in
technical explanations, not this primary QA guidance. Source-use restrictions,
qualifications and mandatory disclosures are retained unchanged.

Parse and Normalize each provide a small Related items panel for one row on the
current table page. It follows hash-bound normalized block_ids into canonical
Sections, then native authorized unit membership and saved parent chunk links.
All branches are listed compactly; full IDs stay in collapsed technical details.
HOLD/excluded entries show their recorded stop reason. Supporting headings/context
are labeled as parent links, not independent evidence or exact chunk overlap.
Missing block mappings are explicit; identifiers are never joined by spelling.
No raw normalized text is displayed and no source admission changes. QA's existing
relationships and other page renderers remain unchanged.

Chunks & Lineage shows its saved chunking policy immediately beneath the Focus
line, followed by a compact full-corpus exception table. Current default is384
BGE tokens, approved exceptions up to512 and added overlap0. Counts include
headings/special tokens. The table is derived from the full validated catalog
(all published formats), independent of the selected source:4chunks above384,
C16two(507/485),C06one(474),C14one(385). Only metadata for sources outside the connected PDF/Markdown scope is
shown here; the table is metadata inspection, not a new source acquisition. Larger limits do not
introduce overlap; source sharing across units or repeated required headings is
separate from intentional overlap between chunks.

The selected chunk's BGE tokens, source characters and saved-embedding status use
three equal-width bordered cards with centered labels/values. Their explanatory
note remains underneath. Styles are scoped to this chunk metric row only.

A short Why this limit? note explains the historical C01 comparison: 384 kept more
units intact and produced fewer chunks than 256, so it became a practical default.
BGE's configured 512 ceiling permits selective intact-content exceptions. This is
an engineering choice, not a measured optimum for retrieval. Supporting detail:
[M2 verification](M2_CHUNKING_VERIFICATION.md).

Embeddings & Indexes uses its own centered bordered cards for document embeddings,
vector dimensions and data type. One chunk has one saved embedding: C01 has 88 chunks
and 88 embeddings. Dimensions 384 means 384 numeric coordinates per vector, distinct
from the 384-token default chunk limit. Document totals/model settings do not
change with the evidence selector; it selects the related chunk's saved exact
embedding/index bindings below. This is read-only inspection, not an embedding
execution control. Chunks & Lineage remains unchanged by this page refinement.

Chunks & Lineage and Embeddings & Indexes each show a Document preparation summary
card directly below the source selector, labeled Selected document totals. It
links verified evidence-unit count → chunk count → saved embedding count → vector
export records + BM25 export records. All counts follow the selected source; they
are separate from individual evidence/chunk details. Native page links connect
the two views and preserve source/evidence/chunk context. The related-chunk
selector explicitly retains session state across these page changes; source or
evidence changes still restrict selection to valid related chunks. BM25 indexes chunk text
separately; these saved-export counts do not certify current index database health.
Other page renderers and existing controls remain unchanged.

On Embeddings & Indexes, Follow evidence unit, Related retrieval chunk and their
record bindings are grouped in the collapsed Inspect individual records section.
Document totals, model settings and index export coverage remain above it.
Selection and source validation behavior are unchanged.

The other preparation views use the same summary-first layout. Parse collapses
its block browser and related items; Normalize collapses its filtered Section
browser and related items. QA & Verified Evidence keeps disposition metrics
visible and groups unit selection, relationships, content and accompanying
qualifications under Inspect evidence unit. Chunks & Lineage groups parent/chunk
inspection beneath its policy and document summary. Validation & Publications
keeps source/derivative checks, HOLD/exclusion warnings and publication chain
visible, with selected-parent validation in Inspect evidence validation.
Collapsed panels retain existing read-only checks; collapsing is presentation,
not lazy execution. Sources, Overview and Embeddings & Indexes are unchanged.

Validation & Publications now starts with a selected-document Section outcomes
box: canonical total → admitted / HOLD / excluded. Recorded QA reasons are grouped
by status and counted without inferring missing explanations. Inspect withheld
Sections provides status filtering, 25-row pagination, source locations/types and
recorded reasons; exact IDs are collapsed and withheld source text is not exposed.
Counts reconcile with the saved document inventory or fail closed. This view reads
QA decisions; it does not perform QA or admit/repair source content. The publication
chain uses process names instead of milestone codes and distinguishes vector
indexing from the separate BM25 text index. Publication means versioned local
artifacts, not online release. Existing integrity and selected-parent checks remain.

The 8516 sidebar presents Knowledge Preparation as the summary link, followed by
a native collapsible Preparation stages group containing the five existing
subpages. It starts expanded for discoverability. Native page links and the hidden
navigation registry preserve all existing URLs and direct process-stage routes.
No page implementation, selected-source behavior or canonical 8514 navigation is
changed by this sidebar-only hierarchy update.

Knowledge Retrieval is a sibling workspace link below the collapsible preparation
stages on 8516. Its /knowledge-retrieval route is a design placeholder only: no
data readers, retrieval execution or provider controls are connected. Preparation
routes and the canonical 8514 dashboard are unchanged.

Each preparation subpage has a collapsed Technical backbone directly below its
Focus line and before source selection. It describes technology, purpose, saved
outputs and verification boundaries. Parsing & Evidence covers Parse, Normalize
and QA together; direct stage routes show their own layer. Saved parser versions,
model metadata and token limits come from the verified snapshot. Dense BGE/ChromaDB
and lexical BM25 are separate preparation paths; RRF combines rankings later in
retrieval. Panels are educational readback, not pipeline execution. Overview and
the Knowledge Retrieval placeholder remain unchanged.

## Markdown connection (C04)

C04 reuses its hash-bound parsed/normalized JSON and existing native evidence,
chunk, embedding and index publications. No parser, QA, model or index is rerun.
Its saved Markdown/MDX parser version is mdx-v1; implementation uses markdown-it-py
and a bounded container/fence grammar, not general MDX execution.

C04 contributes 215 parsed blocks → 158 canonical Sections → 154 admitted Sections,
with 4 excluded and no HOLD Sections in the current native publication; 86 authorized
evidence units → 209 chunks → 209 saved embeddings → 209 records in each search
index export. Admission remains limited by each unit's mandatory qualifications;
current native QA authority is used rather than historical ingestion flags.

Parse shows line locations, language, provider/tab and code-group metadata without
raw block content. Normalize/Related items use saved block_ids from the bound
Markdown Section records; removed blocks show their recorded normalization action
rather than invented downstream links. Evidence payload, context, code/provider
qualifications and citation bindings remain native. Code/MDX is never executed.
Source/metadata identity mismatches fail closed. The PDF-only reader default and
existing PDF bindings remain unchanged; the 8516 loader opts into Markdown.
New acquisition and pipeline changes remain outside this task; the subsequent HTML
connection is documented below.

The unified C04 catalog deliberately carries compact source metadata. Sources
therefore displays an allowlisted acquisition-metadata projection from the bound
parsed publication, checking its source hash and shared identity fields against
the native catalog. It does not overwrite that catalog or use acquisition notes
to grant evidence eligibility. Missing metadata is never inferred. Selecting the
single-source Markdown overview scope carries C04 into subsequent stage pages;
source widgets restore stable context without conflicting default/state values.

## HTML connection

The 8516 loader explicitly opts into the eleven existing HTML publications in
addition to PDF/Markdown. The historical PDF-only reader default is preserved.
HTML source IDs: C03, C05, C07–C13, C15 and C16. No parser, acquisition, QA,
chunking, embedding, retrieval or provider execution is invoked.

HTML contributes 457 saved blocks/canonical Sections (427 admitted, 30 excluded,
0 HOLD in the current native publication), 155 evidence units and 355 chunks /
embeddings / records in each search export. Combined scope: 16 sources, 3,282
blocks, 3,040 Sections (2,572 admitted, 358 HOLD, 110 excluded), 553 units and 992
chunks. Overview counts remain calculated from verified metadata, not these notes.

The saved non-executing semantic adapter version is fixed-html-1.0, implemented
with Python HTMLParser. Parse shows DOM paths, classifications, anchors and source
line locations. Related-item mappings use normalized block_ids; no fuzzy title/ID
matching is used. Acquisition metadata comes from each bound .source.json, checked
against the native catalog identity; HTML page meta tags are never interpreted as
source permission/provenance records. Missing registered metadata/mappings display
UNAVAILABLE rather than using raw-file fallbacks. Current native QA authority takes
precedence over historical ingestion HOLD flags. All qualifications/context remain
with the complete native evidence parent, including scope-limited C16 material.

Publisher HTML is never rendered with HTML components, browser frames or unsafe
Markdown. Native source text/structured display helpers preserve evidence as data;
no JavaScript execution or remote images/assets are introduced. The only custom
HTML remains the existing static, UI-owned CSS. All existing routes, source/unit/
chunk state, canonical 8514 and historical experiments remain unchanged.

The overview Search index coverage card reports chunks present in the saved BGE
embedding, vector-index and BM25 exports, divided by selected-scope chunk count.
Its caption separates BGE saved-vector and BM25 text-record counts and follows
format/source selection. These are verified saved-export counts, not a live index
database health check.

The overview caption includes the total connected verified-source count as well
as counts by format. Both derive from the current verified document inventory.
Future sources count only after their processed, approved publication and index
bindings are connected; copying raw files alone does not add them to the UI.

## Workspace sections

The 8516 sidebar now follows this order: Knowledge Preparation, Knowledge Retrieval,
Offline Retrieval Evaluation, Pre-Generation, Generation, Post-Generation Evaluation, and Human Review. Preparation retains its existing collapsible subpages.
Knowledge Retrieval now reads verified historical measurements through the existing
completion telemetry adapter. Offline Retrieval Evaluation displays verified historical experiments;
Pre-Generation and Generation show saved request qualification and actual execution records.
Post-Generation Evaluation displays read-only findings; the separate Human Review page
connects the existing local POC and signed advanced review controls. Page refresh never executes pipeline stages, models, provider calls or decisions.
Explicit review submissions retain the existing confirmation, identity, integrity and duplicate guards.
Offline evaluation remains an assessment layer rather than a runtime retrieval stage.

New routes: /offline-retrieval-evaluation, /pre-generation, /generation, and
/post-generation-evaluation-human-review. Existing routes and canonical 8514
remain unchanged. The preserved 8514 service is not required to use the connected review page.

## Knowledge Retrieval — shared 34-question journey

Open http://127.0.0.1:8516/knowledge-retrieval. A single Question selector drives
Search & Ranking, Selected Top-30, Evidence Reconstruction, and Context Assembly.
Cohort and Benchmark answerability filters are optional and collapsed. The selected
question remains stable across tabs/reruns whenever it still matches the filters.
The full question is visible above the tabs. Aggregate cards and the question
journey table remain under the collapsed Benchmark summary section.

The integrated Explorer reuses the historical, hash-verified HTML template, display
model and UI. Versioned display adaptations supply just the selected question and
hide the internal question selector. All 34 questions have verified BM25 and vector
Top-50 inputs. Selected RRF order and scores are copied from the sealed M7 Top-30
envelopes, never recalculated or reranked. Arithmetic only checks/explains those
saved scores. The native union/deduplicated pool is display order, not a new ranking.
Candidates outside Top-30 remain visible in native lists but have no invented
downstream RRF rank. All 30 selected chunks map to the same receipt's M8 parents.

Native inputs come from original Phase 2/Phase 1, holdout or completion publications,
with per-file SHA and exact question hashes verified. The metadata-only vector
export supplies parent identities for additional candidates. Existing locator/Section
metadata is retained where present; missing metadata is explicitly unavailable.
No publisher text is embedded, fetched or reconstructed. Full authorized parents
still require the existing accepted reader; no new source authorization is implied.

The integrated frame uses the current installed native st.iframe API. All HTML/JS
is project-owned and hash-verified; JSON data is escaped and displayed as inert
text. The inherited CSP prohibits network requests and remote scripts/assets.
No new dependencies. Historical Explorer files and canonical 8514 remain unchanged.

M8 views show chunk-to-parent relationships, included/excluded parents and reasons,
BGE token usage and approved evidence gaps. R03's cutoff and R04/Q23/Q26 delivery
gaps remain visible. Coverage is against known positives, not precision or answer
quality. Unsupported controls have no positive-group denominator. Strict-witness
and historical overlap methods remain labeled separately.

The native completion adapter verifies historical manifests, source bindings and
measurement accounting on refresh. Missing/tampered selected-question inputs fail
closed, without substituting another question. No retrieval, assembly, provider
call, approval, index build or scoring script runs through this page.

### Retrieval readability and evidence accounting

The main pipeline explicitly names exact Chunk ID deduplication. Parallel search
help explains query-vector BGE search and lexical BM25, with Top-50 per search
and final RRF Top-30. Filter questions explains the four benchmark cohorts.
Search rank, final RRF rank and combined RRF score have separate labels; reciprocal
rank contributions are explained as scores, not rank positions. Main UI labels
use stage names; original milestone IDs remain in question/group identifiers,
registered artifact paths and collapsed technical details for auditability.

Evidence Reconstruction calls parents Evidence Units and displays the selected
chunk → distinct unit → included/excluded chain, exact serialized BGE package
size/budget, and recorded per-unit counts/reasons where available. Units are never
truncated; exceeding the remaining budget is distinct from exceeding total capacity.
Historical receipts that omit per-unit token counts display UNAVAILABLE. No counts
are estimated or recomputed by loading source text.

Context Assembly separates evidence delivery from coverage of the selected
question's human-approved evidence requirements. Each group maps to supporting
included Evidence Units using saved delivery observations, preserving OR/joint-AND
and historical scoring boundaries. The question-specific denominator is explained
alongside the full benchmark total. Unsupported controls have no positive-group
requirements. Labels without a recorded description show that absence explicitly
and retain the approved source/locator references, rather than inventing a label.
Coverage is evidence delivery, not proof of generated-answer grounding.

A source-inspection link opens Chunks & Lineage. It does not auto-select a record
or introduce a free-text Chunk ID lookup: use the source/Evidence Unit selectors
and compare the exact ID in technical details. No source content is added here.

## Offline Retrieval Evaluation — experiment learning journey

Open http://127.0.0.1:8516/offline-retrieval-evaluation. This page reuses
`tools.quality_dashboard.completion_adapter.load_completed`, the same sealed
artifact reader used by canonical 8514. No separate evaluator, benchmark database,
scoring algorithm or execution engine is introduced. Canonical 8514 remains
available until its corresponding 8516 capabilities have been separately developed
and verified; no routes are retired by this page.

The TL;DR explains what/why/how/key learnings, followed by eight narrative chapters:
original evaluation baseline; reviewed/frozen focused benchmark and comparable
candidate pools; RRF versus MiniLM and accepted decision D051; search-signal
complementarity; atomic small-budget studies; intersection-first and supplementation
selection experiments; verified delivery across budgets; expanded 34-question
reconciliation and measurements. Same-day studies are grouped by the questions
they answered, not assigned an invented fine-grained execution chronology.

All results retain their actual scope and scoring definition. The original
29-question evaluation (26 answerable/3 unsupported), focused 15-question/22-group
experiments and expanded 34-question/40-group measurements are not pooled as one
accuracy series. Macro witness recall, group micro coverage, parent location and
actual evidence delivery remain separate. Unsupported controls have no positive
recall denominator; unlabeled candidates are not negatives. Retrieval precision
and nDCG are not fabricated. Delivery is not generated-answer grounding.

Detailed measurements, existing strategy/budget comparisons, a native budget-effect
chart and project-relative hash provenance are collapsed under their chapters.
Question-level historical comparisons reuse the canonical adapter's observations,
with cohort/question filtering, exact configurations, method descriptions and
recorded gaps. Results are not recomputed. Missing or changed pinned studies fail
closed rather than being substituted. Additional historical studies are read only
through pinned manifests and the existing artifact Store.

RRF(k=60) is retained under the accepted ranking decision. Top-30/128K BGE is the
current evidence-backed experimental configuration, not a universal optimum or a
production-default change. Its selection comes from the focused delivery study;
the later expanded measurements expose broader coverage and remaining gaps. BGE
evidence budgets are not provider tokens or model context-window qualification.

This is our reusable offline retrieval-evaluation reference and observability page.
Future testing must use the existing versioned evaluation workflows under separate
authorization. Refresh does not run retrieval, assembly, rankers, scoring scripts,
preflight, provider calls, generation or review actions. Preflight, Generation and
Post-Generation Evaluation and Human Review stay separate workspace destinations.

## Pre-Generation workspace

`/pre-generation` reuses the canonical benchmark/completion adapter, Preflight Suite
sealed-run reader, and historical-observation reader. All 34 questions are selectable.
The overview uses the latest saved suite observation per question; an explicit
observation selector keeps local checks, model preflights and prompt versions separate.
Q05 retains its separately verified funded-request qualification, including its provider
token-count receipt; its earlier prompt audit is a different version. Model-token
measurements are never substituted from actual generation usage. Missing measurements
remain unavailable.

The page connects complete Evidence Units and the evidence-only 128K BGE budget to
prompt assembly, exact saved generator-token counts, output reservation, safety margin,
context headroom and conservative projected request cost. BGE and generator tokens
are distinct units. No component-token breakdown is estimated. Generic instructions
appear only when their digest matches the recorded prompt identity; complete
source-bearing requests are never exposed. Preparation and retrieval links support
source inspection without duplicating passage browsers.

Main views use full stage names without dates. Technical provenance preserves exact
run identifiers, hashes, pricing-version identities and history. Saved qualification
is never presented as fresh execution approval. Changed-dependency observations are
explicitly historical; malformed/unsealed artifacts fail closed through existing readers.
No execution controls, provider calls, reconstruction or qualification occurs on refresh.
This page does not alter the canonical 8514 dashboard or execution trust baseline.

The default Pre-Generation presentation is a single preparation journey, not a
side-by-side experiment comparison. The latest saved check is selected automatically;
the per-question check selector lives in the collapsed **History / Technical details**
section. Selecting an earlier check explicitly labels the page as historical for that
selection. Plain-English summaries distinguish local validation, recorded model
qualification and blocked checks without granting fresh execution approval.

The model-capacity table has **Measurement**, **Description**, and **Saved observation
(tokens / result)** columns. **Total context allocation** adds recorded input tokens,
output reservation and safety margin. The exact arithmetic appears below the table;
missing inputs produce `UNAVAILABLE`. This includes reserved capacity and is neither
actual billed usage nor a sum of BGE evidence tokens and generator tokens.

## Generation workspace

`/generation` reuses the canonical completion/attempt reader and Final Generation
Benchmark Tracker adapter. It displays the 34-question real-run inventory, all-attempt
cost totals and unknown-cost count; mock observations never inflate real generation.
For a selected question, the latest native attempt is the default, while Q05 retains
its original funded answer as default. Earlier attempts remain selectable in collapsed
history. A newer response does not inherit an earlier response's approval.

Four sections show model output (or its abstention explanation), actual measured
usage and estimated cost, exclusive stage latency, and original technical findings
with separately bound reassessments and owner-review state. Missing data remains
unavailable. Cache and reasoning subcategories are not added again to total usage.
Provider inference latency is not inferred from locally measured request duration.
The page uses full stage names and no dates in the main presentation.

Rejected output remains inspectable without being accepted as a valid answer. The
existing localhost-guarded observation reader and verified raw-capture reader are
reused; full raw output requires an explicit checkbox and read-time hash verification.
Unavailable or failed capture is labeled honestly, with no reconstruction of lost text.
No approvals, retries, reconstruction, validators or generation endpoints are invoked.
The preserved 8514 Human Review destination remains linked; its service must be running.
8516 now links to populated Post-Generation Evaluation and separate Human Review pages.
Generation migration does not enable or rewrite owner decisions.

Generation latency is presented in seconds across **Request preparation → Generation
→ Post-generation**. The first phase includes saved-input verification, evidence
reconstruction/source validation, prompt assembly, request-policy checks and model
qualification. Generation groups the request and its service overhead. Post-generation
groups response validation, persistence and final source checking. Only exclusive
recorded stage durations are summed; recorded unattributed overhead is separate.
The longest measured phase and its share of question-level elapsed time are shown.
Individual stages, measurement states and full-precision receipts remain collapsed.
The usage table formats request duration as rounded milliseconds and seconds. These
are display-only derivations; sealed millisecond receipts remain unchanged.


## Post-Generation Evaluation and separate Human Review

Open http://127.0.0.1:8516/post-generation-evaluation-human-review for read-only findings.
The existing URL is preserved; its page title is now Post-Generation Evaluation.
Human Review has its own sidebar entry immediately afterward at
http://127.0.0.1:8516/human-review. Both pages retain question and exact attempt selection
through source-bound, session-only navigation context. The summary
connects saved benchmark evidence delivery, original response structure/source/citation
checks, quotation fidelity, answer-quality questions and the current owner decision.
Saved benchmark coverage is explicitly separate from exact supplied-request provenance.

Technical validation checks response structure, authorized evidence references and
quotation fidelity. It does not establish factual correctness or completeness. Original
failed verdicts and raw diagnostics remain accessible; later assessments and owner
attestations do not rewrite them. R03's missing known-positive group and unresolved
grounding remain separate from its accepted semantic-completeness finding.

The separate Human Review page reuses `tools.human_review.poc_ui.render` and its existing children. Local POC
Approve / Reject / Request Changes retain explicit reviewer label and confirmation,
localhost enforcement, backend duplicate protection, locked decisions and deliberate
revision controls. Rejected contracts retain diagnostic owner triage, not approval.
Signed advanced review retains its existing registration/signature requirements.
No decision or preparation runs during refresh; preparation remains an explicit existing
action when required source-bound review materials are unavailable. No generation
controls are exposed. Publisher evidence and raw provider bodies retain existing
protected local inspection and hash-verification requirements.

Primary summaries use stage names; historical technical traces retain their original
milestone IDs for audit. All 34 saved question entries remain available. No trusted
runner, validator, approval component, policy or sealed artifact is modified by this
8516 layout integration; no execution trust-baseline successor is needed.


### Reading the final review summary

- **Evidence supplied and cited** reports supplied Evidence Units, evidence size,
  cited-unit counts and saved benchmark coverage. It is not a claim-by-claim evidence comparison.
- **Recorded technical findings** shows structure, source/citation integrity and quotation
  fidelity. `REVIEW_REQUIRED` is an overall unresolved-assessment outcome, not proof that
  every technical check failed.
- **Review guidance and recorded status** explicitly separates the assessment checklist
  from recorded findings and owner decisions. The checklist is not an evaluation result;
  available claim/requirement findings remain on the separate Human Review page.

These wording changes do not change validation, decision eligibility or historical records.


### Post-Generation → Human Review handoff

Post-Generation Evaluation contains evidence supplied/cited, original technical findings,
review guidance, recorded owner status and a Continue to Human Review link. It renders
no approval, diagnostic-triage or review-preparation controls. Human Review contains the
existing answer, citations, evidence/claim/requirement findings, qualifications, diagnostics,
local POC decisions and signed advanced review. It links back to Post-Generation.

Navigation remembers the exact question, experiment, result hash, request hash and evidence
package hash in session state and verifies them against loaded records. This context is
neither an approval nor an execution authorization. Selecting a different answer never
transfers confirmation or approval; existing backend technical and duplicate guards remain
unchanged. A stale/tampered navigation target fails closed. Q05 defaults to the funded
answer and its earlier failure remains available in history. Generation links to both pages.
The old combined URL remains valid for Post-Generation Evaluation, avoiding broken links.


## RAG Bot — UI foundation only

The default 8516 landing page is RAG Bot. The sidebar starts with RAG Bot / New chat,
then Knowledge Workspace with the existing pages. Preparation stages start collapsed
on the bot page and remain expanded on knowledge pages. Existing stage URLs are unchanged;
Knowledge Preparation has moved from the root to `/knowledge-preparation`, and its
breadcrumbs/overview links follow that route.

The welcome screen uses the existing Apple-inspired system-font stack and heading sizing,
with muted blue, sage and lavender example cards. Examples are static inspiration, not
retrieval queries. The native chat composer is visibly disabled until a separately approved
workflow integration. No question is accepted or sent, no answer is fabricated, and there
is no conversation history, message persistence, message/draft session state, database,
chat cache, provider call, retrieval or evidence assembly. Refresh, a new browser session
and returning to New chat all show the empty welcome screen. This storage boundary applies
to the new bot, not the existing immutable experiment records or knowledge reader caches.

The foundation imports only Streamlit and reads no corpus, benchmark or generation records.
There are no model controls or execution endpoints. The remaining 8514 parity gaps and
separate explicit-generation authorization requirements are unchanged.
