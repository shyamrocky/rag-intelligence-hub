# Approved decision log

**Current direction — October 26, 2026:** M0–M9 are OWNER_ACCEPTED / CLOSED for their completed engineering/evaluation scopes. D049 records M9 acceptance and authorizes only a saved-record ten-case BM25 diagnosis. D041–D048 remain the architectural direction. Compact evidence, runtime gates, remediation, M10/M11 and Git operations remain unauthorized. See [the readiness sequence](architecture.md#post-m9-direction-and-m10-readiness).

Historical status at the D036 checkpoint: M5 persistent numerical storage was accepted; M0–M4 and H0–H5 remain accepted. The current M5 source delta is uncommitted. New Git staging/commit, global-default cutover and M6 remain separately unauthorized. Historical decisions below retain their original dates and scopes.

Dates use America/Los_Angeles. Entries below record explicit project directions from the supplied bootstrap instructions or the user's repository-governance instructions. Implementation completion does not imply user acceptance. Proposed stack selections and draft decisions remain in `workspace/DRAFT_DECISIONS.md` until approved; that private file is absent from clean checkouts by design.

| ID | Date | Decision | Rationale | Alternatives considered | Status / authority |
|---|---|---|---|---|---|
| D001 | 2026-10-18 | Build a cited Learn / Explore / introductory Decide RAG assistant | Focus the Academy project on trustworthy evidence-based learning | Broad technology advisor; autonomous agent | Approved direction: bootstrap §§1,3 |
| D002 | 2026-10-18 | Python with LangChain; add LangGraph only when useful for state | Code-based learning with bounded complexity | n8n; unconditional graph orchestration | Approved direction: bootstrap §3 |
| D003 | 2026-10-18 | Local-first execution and deterministic V1 | Keep initial infrastructure and operational burden small | Managed cloud deployment; autonomous loops | Approved direction: bootstrap §3 |
| D004 | 2026-10-18 | OpenAI GPT API is the intended generation provider; defer exact model | Separate managed answer generation from local embedding/indexing work | Local generation; alternative hosted provider | Provider direction approved: bootstrap §3; model and credit eligibility unresolved |
| D005 | 2026-10-18 | Complete Milestone 1 only, then stop for review | Make setup reviewable before ingestion work | Build the entire application in one pass | Approved scope: bootstrap §§5,8 |
| D006 | 2026-10-18 | Keep durable approved documentation in docs/ and private working material in workspace/ | Preserve shared project knowledge without publishing draft/private artifacts | Mix temporary work with public documentation | Approved: user's repository-governance instruction |
| D007 | 2026-10-18 | Record decisions with rationale, alternatives, status and date; stop at every major milestone | Prevent silent reversals and uncontrolled scope expansion | Implicit decisions; a single final review | Approved: user's repository-governance instruction |
| D008 | 2026-10-18 | Keep implemented Milestone 1 scaffold pending formal readiness review | Latest user instruction makes formal acceptance conditional on Git/reconciliation/scope review; earlier positive feedback was recorded too broadly | Treat earlier positive feedback as final closure | Historical checkpoint; superseded by D010 |
| D009 | 2026-10-18 | Initialize Git locally on main without staging, commit or push | User requested inspection of initial commit candidates before formal acceptance | Delay local Git initialization | Authorized and completed; no remote configured |
| D010 | 2026-10-18 | Accept Milestone 1 and authorize C01/C04/C06 ingestion, parsing, normalization, provenance and HOLD through G0–G2 | User explicitly approved after originals were supplied; all hashes/bytes matched before implementation | Keep waiting; extend to downstream RAG stages | Approved scope; Milestone 2 results pending review; Milestone 3 not authorized |
| D011 | 2026-10-18 | Use proposed PyMuPDF plus markdown-it-py with bounded MDX handling for local ingestion | PDF geometry/rendering and standard Markdown tokens support independently auditable evidence; source-specific MDX state is needed | pdfplumber/pypdf; generic Markdown alone; original HTML replacement | Implemented within authorized spec direction; PyMuPDF AGPL/commercial terms noted, project release licensing unresolved |
| D012 | 2026-10-18 | Keep unreviewed records on HOLD, with exact-section/source-hash review receipts and immutable private snapshots | Avoid expanding five historical sample approvals into full-source approval; reproduce input/output lineage | Auto-approve extracted text; silently repair formulas/tables | Implemented under approved HOLD/provenance requirements; sample results await review |
| D013 | 2026-10-19 | Approve Milestone 2.5 direction: all-HOLD deterministic checks, controlled low-risk auto-promotion after fidelity/representative validation, adaptive sample, strict hazard/context HOLD, no medium-risk auto-promotion | Scale quality review without treating parser success or sampling as full-source approval | Manual review of every section; unrestricted batch or PDF auto-promotion | Direction approved with constraints; execution requires separate user approval after scope/test-plan summary |
| D014 | 2026-10-19 | Require URL-based source acquisition and HTML parsing for remaining eligible sources in intended 16-source V1 | Original publisher web content must be ingested with format-aware structure and provenance | Local PDF/MDX-only V1; treating HTML support as optional | Roadmap requirement approved; later implementation milestone to approve; excluded from 2.5 |
| D015 | 2026-10-19 | Execute the reviewed Milestone 2.5 scope and stop for independent review | User explicitly authorized all-HOLD validation, gated low-risk promotion, adaptive review and reporting | Continue planning; include downstream functionality | Execution authorized; results pending independent review; Milestone 3 not authorized |
| D016 | 2026-10-19 | Preserve original nine receipts while separately rechecking new-manifest contextual eligibility | Exact source comparison does not establish complete evidence; strict context HOLD is required | Mutate original receipts; grandfather incomplete fragments | Implemented under approved strict HOLD requirements; seven original samples suspended only in new manifest |
| D017 | 2026-10-19 | Block C04 prose after expanded review found an implicit-context false clear | Cohort gating must contain systematic validation defects before any prose auto-promotion | Approve ten individually passing prose candidates; silently patch rules after review | Implemented fail-closed; future rule fix/fresh acceptance review required; code cohort separately qualified |
| D018 | 2026-10-19 | Linear acquisition, parsing, normalization, QA and readiness stages; one authoritative outcome per source/stage/attempt; one eligibility engine and one readiness gate | Keep ownership, fail-safe progression and diagnostics traceable; dashboard consumes results without business logic | Competing module statuses; UI-derived readiness; mandatory new orchestration framework | Explicitly approved architectural principle; production integration deferred |
| D019 | 2026-10-19 | Execute only isolated PDF-remediation Phase 1A completeness guard and prepare independent C01/C06 review batches; retain all historical records and decisions | Address five exposed terminal-hyphen residues before broader remediation; measure actual review effort | Full remediation; estimated review commitment for all sixteen sources; automatic content promotion | Execution approved; checkpoint results require review; user is independent reviewer with ChatGPT technical support; no further phase approved |
| D020 | 2026-10-19 | Execute Phase 1B only: versioned experimental hybrid PDF corrections and validation; freeze fresh source examples before adapter changes and implementation before scoring | Apply independently reviewed findings while testing generalization and preserving original evidence | Production integration; tuning against scored acceptance; changing historical labels or eligibility | Explicit user authorization; Phase 1A complete; Phase 1B implemented for review, with unresolved defects; no production adoption or next phase approved |
| D021 | 2026-10-19 | Formally close Phase1D; freeze hybrid-reconciliation-4-phase1d-v1 for its demonstrated experimental PDF scope; authorize read-only EXT-01 scoping only | Six scoped independent review observations and preserved automated provenance support a bounded experimental baseline; carry unresolved obligations forward without another general PDF cycle | B: extra verification before a narrower freeze; C: reject freeze for a confirmed critical included-scope defect; neither required by reviewed scope | Explicitly approved Recommendation A; all exclusions/HOLD preserved; no production adoption, source readiness, promotion or EXT-01 implementation. See [freeze scope](pdf-experimental-freeze.md) |
| D022 | 2026-10-19 | Execute bounded EXT-01 isolated foundation and one owned plain-text adapter demonstration; freeze candidate before registration | Demonstrate extensibility through existing parser, normalization, span, QA and stage contracts without invalidating the frozen PDF dependencies | Registry-only patch; relabel test input as HTML; general schema/eligibility redesign; production migration | Explicit user execution approval supersedes D021 read-only EXT-01 limit only; implemented for review. Candidate core unchanged after registration; no production adoption, new-format eligibility, source readiness, further parser work or downstream approval |

| D023 | 2026-10-22 | Authorize bounded automatic HTML complete-unit qualification across all eleven frozen sources through the sole shared QA owner and decision function; keep PDF/MDX policies unchanged | Admit objectively source-supported textual units without requiring manual votes for every Section; retain ambiguous/specialized content HOLD | Blanket technical-PASS promotion; another twelve-passage-only sample; separate eligibility engine | Explicit owner execution authorization; implementation/publication completed for review, no independent visual/semantic certification or downstream execution. See [HTML admission](html-automatic-admission.md) |
| D024 | 2026-10-22 | Remediate the exact 140 textual HTML HOLD Sections with source-bound additive context overlays and a fingerprinted opt-in successor; preserve the 78 unsupported Sections and all 239 earlier admissions | Recover complete textual context and correct narrow evidence/API false positives without reparsing sources or requiring individual manual votes | Blanket HOLD promotion; treating hidden H1 as visible content; global math-rule waiver; rewriting immutable observations | Explicit owner execution authorization; 102 additional Sections published through existing shared QA, implementation for review. No independent human fidelity claim, source readiness or downstream authorization. See [context remediation](html-context-remediation.md) |
| D025 | 2026-10-22 | Reassess all 457 HTML Sections for maximum useful source text; permit scope-bound standard/illustrative references with mandatory limitations through existing QA | Preserve useful captured text without confusing unavailable visuals or unexecuted examples with extraction corruption; retain material ambiguity HOLD | Automatic whole-source approval; retaining every specialized element HOLD; silently repairing publisher content; new eligibility engine | Explicit owner execution authorization; 426 Sections published for review, including 85 new admissions. Prior 341 and all history preserved; no downstream or source-readiness authorization. See [text recovery](html-text-recovery.md) |

| D026 | 2026-10-22 | Integrate the final C04 complete-unit policy and publish all defensibly eligible Markdown scope through existing shared QA and make_decisions; preserve HTML/PDF support | Finish the 158-Section source audit with 114 new bounded decisions while preserving forty historical approvals, four exclusions and warning-bearing source-defect/metric projections | Leave staged candidates unpublished; overwrite HTML/PDF code; qualify defective examples as executable or scores as verified facts; create a separate decision engine | Explicit owner execution/publication authorization; final successor combined-markdown-qa-1.1 implemented and published for review. No source-readiness or downstream authorization. See [Markdown QA](markdown-qa.md) |

| D027 | 2026-10-22 | Admit the exact C10 weighting table as illustrative source evidence with mandatory QA ambiguity disclosure and separate source-bound RRF context; add a publication-bound consumption contract | Make faithful useful source content available without treating publisher truth certification as a universal ingestion gate; preserve integrity and context restrictions | Leave the faithful table HOLD solely for score interpretation; invent a scoring-stage explanation; merge all related text; create another QA engine or fact-checking service | Explicit owner implementation/publication authorization; implemented for review, no independent mathematical/runtime correctness or downstream authorization. See [consumption contract](qa-consumption.md) |

BGE-small and Chroma remain provisional pending evaluation. Streamlit is the bootstrap UI direction, with implementation deferred. Exact source inclusion/rights, chunking policy, freshness and generation model/credits remain open. Milestone 1 acceptance approves the scaffold; unresolved downstream choices remain open.

| D028 | 2026-10-22 | Execute source-bound full four-PDF text recovery, scope-qualified STANDARD/ILLUSTRATIVE admission and explicit publication through existing shared QA; preserve completed HTML/Markdown and historical PDF scope | Maximize defensible source knowledge without making publisher certification a universal gate; retain material extraction/structure uncertainties HOLD | Keep the 19-Section-only policy; blanket source approval; mutate canonical text; introduce another QA authority | Explicit owner implementation/publication authorization; implementation and compatibility successor delivered for review. No whole-source readiness or downstream authorization. See [PDF text qualification](pdf-text-recovery.md) |


## M3 final acceptance

| ID | Date | Decision | Rationale | Alternatives considered | Status / authority |
|---|---|---|---|---|---|
| D029 | 2026-10-23 | Formally accept and close M3, including qualified content chunking, C14 scope correction and the full 553-unit / 992-chunk explicit release | Source-bound complete units, immutable publication selection and verified lineage provide the accepted foundation for embedding work without a new admission authority | Flatten QA envelopes; index unrestricted source-defective code; guess boundaries or offsets; alias changed PDF identities; silently switch historical defaults | **OWNER_ACCEPTED / CLOSED** by explicit owner instruction. Accepted M3 manifest `f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c`; selectors and obligations in [M3-to-M4 handoff](M3_TO_M4_HANDOFF.md). 384 total BGE default, four selective 512 limits, complete-parent rehydration, mandatory source qualifications and honest citation precision retained. M4 **NOT STARTED / NOT AUTHORIZED**; no weights, embeddings or downstream execution approved. |


## M4 provisional embedding baseline

| ID | Date | Decision | Rationale | Alternatives considered | Status / authority |
|---|---|---|---|---|---|
| D030 | 2026-10-23 | Execute M4 using BAAI/bge-small-en-v1.5 as the provisional embedding baseline against the accepted 992-chunk M3 catalog; pin weights/tokenizer/runtime/pooling/normalization and preserve input/qualification bindings | Small local English baseline, accepted tokenizer compatibility and auditable CPU operation; no retrieval-quality winner claimed | Additional models now; hosted embedding API; defer all vector generation; mutate upstream chunks | Explicitly approved M4-only direction in the owner’s embedding-model decision; implementation results pending owner acceptance. Comparative Recall@K/MRR deferred to M9; M5 and later remain unapproved. |

## D031 — Coordinated opt-in durable consumers and isolated strict ingestion

- **Decision:** Implement H2/H3 as one coordinated, explicitly selected evidence/publication/lineage migration and a reproducible isolated ingestion image. Preserve the original reader tree and historical selectors; enforce explicit release/output in the actual strict shared APIs. Reuse saved numerical vectors only after a complete authorized source/input/token/model/scope bijection.
- **Rationale:** Remove inappropriate workspace dependencies and the stale ingestion fallback without weakening QA, rewriting historical fingerprints or recalculating unchanged embeddings.
- **Alternatives:** An in-place shared-source edit expands cross-format compatibility impact; a launcher alone leaves the low-level fallback intact; copying evidence without a new binding contract leaves old runtime dependencies active.
- **Status:** Architectural direction and bounded implementation explicitly OWNER_APPROVED; candidate engineering results and default cutover require separate owner acceptance. H4/H5 and M5 remain unauthorized.
- **Date:** 2026-10-25.
- **Implementation:** [Dedicated H2/H3 contract and opt-in commands](H2_H3_DURABLE_SUCCESSORS.md). Source admissions, normalized records, approved token budgets and mathematical/visual qualifications remain unchanged.

## D032 — H2/H3 owner acceptance and bounded H4 inspection alignment

- **Decision:** Accept H2/H3 as technically complete and closed. Authorize H4 only: explicit historical, C01, pre-migration and durable inspection modes in the existing Streamlit application, with coherent native readers, live parent qualifications, isolated session/cache identities and read-only embedding metadata.
- **Rationale:** Make the accepted durable 553-unit / 992-chunk / 992-vector bindings inspectable without changing historical defaults or introducing a second evidence authority.
- **Alternatives:** Global default cutover, changed-ID aliases, arbitrary selector mixing, a second dashboard or new QA/publication identities; none authorized.
- **Status:** H2/H3 **OWNER_ACCEPTED / CLOSED** by explicit owner instruction. H4 execution authorized; its implementation acceptance remains pending. No global cutover, H5, M5 or M4 owner acceptance is implied.
- **Date:** 2026-10-25.
- **Contract:** [Explicit operational inspection modes](OPERATIONAL_SELECTION_CONTRACT.md). Original releases and source qualifications remain unchanged.

## D033 — H4 owner acceptance and bounded H5 operational closure

- **Decision:** Accept H4 as OWNER_ACCEPTED / CLOSED and execute H5 only: source-only privacy/tracking proposal, current operating guide, canonical debt reconciliation, fresh full regression plus explicit durable verification, preservation and M4-to-M5 readiness handoff.
- **Rationale:** Establish an accurate supported operating path and reviewable source-control boundary while preserving the accepted H0–H4 releases, numerical vectors, native QA authority and historical replay.
- **Alternatives:** Switch historical defaults, commit the untracked implementation immediately, put private recovery/data/models into Git, accept M4 automatically, or begin M5; none are authorized.
- **Status:** H4 **OWNER_ACCEPTED / CLOSED** by explicit project-owner instruction. The owner reports successful manual browser inspection; agent evidence is separately identified. H5 implementation/verification authorized, result acceptance pending. M4 acceptance, M5, Git staging/commit/merge/push, default cutover and public distribution remain separate decisions.
- **Date:** 2026-10-25.
- **Contract:** [Current operations](current-operations.md). The private H5 owner receipt binds exact H4 candidate/component and delivery hashes; it is not a cryptographic signature.

## D034 — H5 and durable M4 owner acceptance; source-only checkpoint preparation

- **Decision:** Record H5 and M4 as OWNER_ACCEPTED / CLOSED. Accept the verified durable 553-unit / 992-chunk / 992 × 384-vector engineering baseline and unchanged numerical reuse. Revalidate the exact source-only tracking inventory, apply only the valid narrow H5 ignore amendment, verify recovery/integrity, and prepare the M5 input handoff.
- **Rationale:** Close accepted engineering milestones while establishing a reviewable source-control boundary without including private corpus, QA payloads, models, vectors, archives or recovery data in Git.
- **Alternatives:** Treat readiness as a completed Git checkpoint, commit immediately, certify retrieval quality, switch global defaults or begin M5; none are authorized.
- **Status:** Explicit project-owner acceptance and bounded preparation authorization. SH-08 RESOLVED; SH-09 remains OPEN until an actual separately authorized Git checkpoint is verified. STOP before staging/commit. M5 NOT STARTED / NOT AUTHORIZED. BGE retrieval comparison remains at M9; no production-readiness or publisher certification.
- **Date:** 2026-10-25 (America/Los_Angeles).
- **Bindings:** [Current operations](current-operations.md) and [M4 baseline](LOCAL_EMBEDDINGS.md). Private owner receipts in the existing milestone tracker bind exact accepted release, model and H5 delivery hashes; they are neither digital signatures nor identity attestations. Historical publications/defaults remain unchanged.

## D035 — Bounded M5 local numerical storage

- **Decision:** Execute M5.0–M5.8 only using all 992 accepted durable Chunk IDs and saved vectors. Isolate ChromaDB in a fifth locked environment, with explicit hash-qualified selection and metadata-only index inspection. Retain the Unified/native parent readers as the sole evidence gateway.
- **Rationale:** Add persistent numerical storage without changing accepted model behavior, locks, source admission, upstream release identities or historical defaults. Reassess deferred findings against measured M5 behavior without claiming their broader causes resolved.
- **Alternatives:** Modify the accepted embedding/dashboard environments, embed source/parent payloads in the database, introduce a second admission authority, or rewrite legacy APIs; these were not selected. The required stop checkpoint applies if upstream-bound changes become necessary.
- **Status:** M5 execution OWNER_AUTHORIZED. Isolated implementation and exact ChromaDB dependency choice are engineering candidates pending project-owner result acceptance. No M6 authorization, retrieval-quality claim, Git action or public-distribution approval.
- **Date:** 2026-10-25.
- **Contract:** [M5 persistent index](M5_PERSISTENT_INDEX.md). The private M5 design/verification packet records exact locks, bindings, performance, debt qualifications and preservation.

## D036 — M5 owner acceptance and bounded post-M5 assessment

Date: 2026-10-25. Decision: accept `m5-chroma-1.1`, explicitly selected by `config/vector-index-m5-v1-1.json`, as M5 OWNER_ACCEPTED / CLOSED. Rationale: saved-vector identity, restart, logical reconstruction, regression and qualification-boundary evidence accepted by the project owner. Alternatives: leave M5 pending or broaden acceptance to retrieval quality; neither is the owner decision. Status: OWNER_APPROVED. Historical development 1.0 remains unchanged.

Authorize root-cause feasibility, source-only checkpoint and independent-recovery proposals plus bounded read-only checks only. The eight broad findings stay DEFERRED until their own closure evidence exists. No remediation, global default changes, Git staging/commit/push, private backup transfer/restore, or M6 implementation is authorized. See [M5 operating contract](M5_PERSISTENT_INDEX.md) and the canonical working tracker for exact receipts.

## Pre-M6 bounded operational scope

| ID | Date | Decision | Rationale | Alternatives considered | Status / authority |
|---|---|---|---|---|---|
| D037 | 2026-10-25 | Authorize additive explicit M0–M5 operational preflight, bounded local coexistence measurement, source-only checkpoint proposal and read-only recovery availability inspection; retain SH-01/06/11/17 in canonical future backlog | Reduce current selector/runtime risks without changing accepted release identities or starting BM25 | Rewrite legacy APIs; migrate fingerprints; install runtimes; transfer backups; stage code; none authorized | Explicit owner implementation authorization. Technical results pending separate owner acceptance. No M6, Git staging/commit or private transfer/restore approval. See [preflight contract](PRE_M6_OPERATIONS.md). |

## D038 — M6 source-bound local lexical candidate indexing

- **Decision:** Execute M6 BM25 only for the exact 992 accepted durable M5 Chunk IDs. Reuse the unchanged source-only chunk-consumption and complete-parent contracts; isolate rank-bm25 0.2.2 / NumPy 2.2.6 in a sixth locked environment. Use an explicit hash-qualified opt-in selector, deterministic lexical policy and immutable JSON index.
- **Rationale:** Establish a reproducible lexical candidate foundation without modifying accepted source/QA/catalog/model/vector/index identities or the five runtime locks. Candidate search confers no evidence authorization.
- **Alternatives:** Modify the Chroma/embedding environment, write a custom scorer, flatten verified parent/QA envelopes, or implement hybrid search; these are not selected. The optional dashboard addition is deferred to preserve existing shared UI.
- **Status:** Explicit owner execution authorization; technical implementation results require separate owner acceptance. M7–M11, Git operations, backup transfer, model inference, QA changes and default cutover are unauthorized. All eight Post-M11 findings remain deferred.
- **Date:** 2026-10-25, project decision date (America/Los_Angeles).
- **Contract:** [M6 BM25 index](M6_BM25_INDEX.md); private evidence in the existing canonical milestone tracker.


## D039 — M6 acceptance and bounded M7 candidate retrieval

- **Decision:** Record M6 as OWNER_ACCEPTED / CLOSED and implement M7 only: vector-only query retrieval with the accepted pinned BGE runtime, unchanged M6 BM25 and one-based Reciprocal Rank Fusion; add a small panel to the existing Streamlit dashboard.
- **Rationale:** Deliver a functional local three-mode candidate experience while preserving the exact 992-record source/QA/chunk/model/vector/index chain and the existing complete-parent evidence gateway.
- **Alternatives:** Merge the six environments, rebuild indexes, change document instructions, average incompatible raw scores, add another evidence viewer, or implement M8/generation; none are selected. Existing runtimes support the query-only policy without upstream changes.
- **Status:** M6 engineering acceptance and M7 execution explicitly OWNER_APPROVED. M7 implementation results require separate owner acceptance; retrieval relevance and hybrid superiority remain unmeasured until M9. No M8–M11, Git, backup, global-default or QA changes authorized.
- **Date:** 2026-10-25, project date (America/Los_Angeles).
- **Contract:** [M7 candidate retrieval](M7_HYBRID_RETRIEVAL.md). The private M6 receipt binds the exact accepted selector/manifest and preserves historical reports. All eight canonical Post-M11 debt findings remain deferred.

## D040 — M7 owner acceptance and bounded M8 evidence composition

- **Date:** October 25, 2026.
- **Status:** M7 OWNER_ACCEPTED / CLOSED; M8 implementation authorized, result acceptance pending.
- **Decision:** Accept the explicitly selected M7 vector/BM25/RRF engineering baseline and implement M8 only through existing live complete-parent gateways. Keep source content, context, QA observations, qualifications and citations distinct; deduplicate exact parents and apply whole-parent token budgets. M9–M11 require separate approval.
- **Rationale:** Candidate IDs and index membership cannot authorize evidence. Existing native QA and verified consumers already enforce the source restrictions M8 must retain.
- **Alternatives:** Detached search text, raw normalized fallbacks, independent eligibility checks, implicit release switching and partial-parent truncation are rejected. BGE token measurement is configurable independently of a future LLM context window.
- **Evidence:** Canonical tracker references the M7 owner receipt and M8 implementation/verification workstream. Historical M7 reports and accepted releases remain unchanged. See [M8 contract](M8_VERIFIED_EVIDENCE.md).


## Post-M9 architectural direction — October 26, 2026

The project owner explicitly supplied “Post-M9 Architectural Decisions and Next-Step Alignment.” These decisions approve planning direction, not M9 acceptance or successor implementation. Accepted engineering evidence, measured results and future proposals remain distinct. The canonical tracker records the exact private instruction SHA-256; original M9 reports and publications remain immutable.

### D041 — Recommend BM25 provisionally for subsequent experiments

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Recommend BM25 provisionally for subsequent experiments: top-K 10, candidate depth 50; retain vector and hybrid choices.
- **Rationale:** BM25 leads MRR and 32K completeness in the source-anchored M9 set; hybrid ties Recall@10. The small benchmark may favor lexical matching.
- **Alternatives:** Declare a universal winner or change accepted M7 defaults; neither is approved.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.

### D042 — Evidence budget and answer quality

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Treat 32K BGE tokens as the highest-completeness tested evidence budget; select the eventual operating budget through controlled M10 answer experiments.
- **Rationale:** A larger evidence envelope is not proof of better answers. Assess faithfulness, completeness, citations, tokens and cost with consistent questions, model and prompts.
- **Alternatives:** Assume 64K/100K is better or equate BGE counts to an unselected LLM context window.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.

### D043 — Ten-case failure diagnosis before remediation

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Require a separately authorized per-question diagnosis of the 10 incomplete BM25 cases at 32K before choosing remediation.
- **Rationale:** Retrieval misses, oversized parents, budget competition and combined causes need different remedies. Record required groups, ranks, parent costs and exact omission reasons.
- **Alternatives:** Assume all ten need more than 32K; run diagnostics under this documentation instruction.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.

### D044 — Proposed pre-generation quality gate

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Include a lightweight deterministic pre-generation PASS / RETRY / ABSTAIN gate in proposed M10, reusing M8 verification.
- **Rationale:** Integrity, compatibility, complete parents, mandatory context, citations, deduplication, budget and explicit omissions can be checked. Runtime support signals and configured minimum evidence cannot guarantee semantic sufficiency. RETRY needs an explicit bounded recovery path.
- **Alternatives:** Create a second evidence authority, run the offline benchmark on each request, or use benchmark labels as a runtime oracle.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.

### D045 — Proposed post-generation quality validation

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Plan a separate post-generation validation stage: deterministic citation/structure checks plus explicitly distinguished semantic review.
- **Rationale:** Faithfulness, claim support, disclosure, completeness, relevance, unsupported claims and appropriate abstention require answer-level assessment; deterministic checks alone cannot guarantee semantic correctness.
- **Alternatives:** Treat valid evidence or syntactically valid citations as proof that generated claims are supported.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.

### D046 — Compact verified evidence investigation

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Investigate a separately versioned compact verified LLM-facing representation before M10 integration; retain immutable native audit evidence.
- **Rationale:** Q21 costs about 91K–97K assembled tokens; its 84,064-token native envelope contains 3,294 source-text tokens. C16 envelopes exceed 700K largely from QA attachments. Preserve complete authorized source/context, citations, qualifications and warnings, and revalidate against authoritative M8 evidence immediately before consumption.
- **Alternatives:** Truncate protected parents, strip mandatory warnings, implement compaction now, or narrow source scope without separate upstream authorization.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.

### D047 — Offline evaluation versus runtime enforcement

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Separate offline evaluation from proposed per-request quality gates.
- **Rationale:** The runtime proposal is question → M7 retrieval → M8 verified assembly → pre-generation gate → M10 prompt/generation → post-generation gate → cited answer or abstention. Offline experiments measure this path; they do not execute on every request.
- **Alternatives:** Make the full benchmark a runtime requirement or present known-positive labels as ordinarily available.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.

### D048 — Beginner-focused evaluation planning

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Decision:** Plan a separately versioned beginner-focused 10–15-question M10 answer-quality/user-acceptance set.
- **Rationale:** General questions about RAG, embeddings, vector stores, chunking, hybrid search and evaluation test a different experience from the source-anchored benchmark.
- **Alternatives:** Modify benchmark-v1, create new questions/labels now, or claim human approval of future labels.
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY, from the explicit post-M9 instruction. Documentation registered; implementation/evaluation execution is not authorized.


## D049 — M9 owner acceptance and bounded BM25 diagnosis

- **Date:** 2026-10-26.
- **Decision:** Record M9 OWNER_ACCEPTED / CLOSED against result selector SHA-256 `f3420b4645ac8b37819a37750d1d9a33e74b7d1e828f7711eef14e573d868ece`, manifest `8a2dba7fc4def81eef74e76b168a5de4473a7ee9cae3bf64cec10dce339e0fad` and benchmark `17f1c6594ff7e435b3f0da636165c4daf105f9a768f13bac80742eb33640065d`. Authorize saved-record analysis of the ten incomplete BM25 32K cases, implementing the investigation direction in D043.
- **Rationale:** Distinguish retrieval misses, evidence size and context competition before choosing changes.
- **Alternatives:** Rerun evaluation, tune retrieval, enlarge budgets or compact evidence immediately; none is authorized.
- **Status / authority:** Explicit project-owner acceptance and read-only diagnosis authorization. Consolidated receipt: `data/evals/m9/approvals/m9-results-v1.json`; no identity attestation or individual signatures. Acceptance covers the completed, limited evaluation, not optimal relevance or answer quality.
- **Boundaries:** Preserve sealed benchmark/results/reports, D041–D048 and accepted defaults. Optional chunk-size experiment remains pending. Stop for owner review before remediation, compact implementation, runtime gates or M10.


## D050 — Hybrid candidate discovery and relevance reranking

- **Date:** 2026-10-26 (America/Los_Angeles).
- **Status / authority:** OWNER_APPROVED_ARCHITECTURAL_DIRECTION_ONLY. The explicit owner instruction “ADR: Hybrid Candidate Discovery and Relevance Reranking” authorizes documentation registration only. Experiment execution, model selection/acquisition and implementation require separate approval. M0–M9 remain OWNER_ACCEPTED / CLOSED; M10–M11 remain unauthorized.
- **Decision:** Introduce a bounded experimental relevance-ranking workstream before changing M8 evidence selection. Compare existing RRF (constant 60) with a locally executable cross-encoder, selected and pinned only under a separately authorized experiment. The cross-encoder is a proposed candidate, not an accepted component or assumed winner. Retain the RRF baseline even if a cross-encoder is provisionally selected.
- **Rationale:** Accepted BM25 equivalence-aware Recall@10 is 82.1%, with complete evidence for 16/26 answerable questions at 32K. The ten-case diagnosis found five retrieval-incomplete cases and five oversized required-parent cases; Q04 also has context-selection competition. A controlled comparison must distinguish discovery/ranking failures from evidence-budget infeasibility before refining M8. Reranking cannot by itself establish that oversized complete parents fit.
- **Alternatives considered:** Retain RRF without comparison; rerank BM25-only candidates; compare different candidate pools; change M8 selection or enlarge budgets immediately. The selected direction compares rankers on an identical hybrid-discovered pool while preserving accepted evidence behavior and defaults.

### Proposed candidate-only experiment

Question → BM25 top 50 + vector top 50 → union by exact qualified Chunk ID → deduplicate while retaining both original ranks and native scores → RRF or cross-encoder ranking on the **identical per-question pool** → evaluation against reviewed known-positive relevance labels. Preserve source/release identity, candidate provenance and deterministic tie-breaking. This candidate-only path creates no new source authorization. No pool construction or retrieval is executed by this ADR.

Create a separately versioned 15-question experimental dataset only after execution authorization: the exact ten M9 cases **Q04, Q05, Q09, Q10, Q11, Q13, Q16, Q21, Q23 and Q25**, reusing their approved labels unchanged, plus five realistic beginner questions covering RAG architecture, embeddings, chunking, hybrid retrieval and evaluation. The five new questions and proposed known-positive evidence labels require explicit project-owner review **before scored execution**. Preserve benchmark-v1; source-equivalent alternatives and required-group semantics remain intact. Unjudged chunks are not automatically irrelevant. These five experimental questions are distinct from D048's planned M10 answer-quality set; no questions or labels are created now.

Measure equivalence-aware Recall@5/@10/@20, MRR@10, required-parent/evidence-group coverage, multi-evidence completeness, candidate-discovery recall before reranking, ranking stability/differences, reranking latency and resource cost. Both rankers use the same discovered pool per question. Success means improved or defensibly equivalent known-positive coverage, particularly on the five retrieval-incomplete cases, with acceptable measured local resource/latency overhead. A 15-question experiment cannot establish universal superiority. Do not claim improved 32K evidence inclusion without a separately authorized, actual M8 assembly and validation experiment.

### Sequence and boundaries

**ADR registration → bounded experiment authorization → five-question ground-truth review → controlled ranking comparison → owner decision → subsequent separately authorized M8 refinement.** D050 updates the next-step ordering; D041's provisional BM25 recommendation and accepted M7 defaults remain unchanged. D046 compact-evidence planning remains a separate future direction, not execution authority.

The ranking experiment stops at ranked candidate Chunk IDs. Verified-parent grouping/relevance aggregation, complete-parent token-cost assessment, budget-aware selection, context assembly optimization and the pre-generation PASS / RETRY / ABSTAIN gate remain future separately authorized work. Existing M8 and its complete-parent, citation, qualification and atomic-budget contracts remain accepted and unchanged.

Do not implement the union/reranking pipeline, install dependencies, select or download a model, run retrieval/inference/experiments, regenerate embeddings, modify M7 defaults/M8/M10, alter source/QA authority, published evidence or token budgets, or stage/commit/push Git changes under this ADR. Preserve frozen M9 evaluation/diagnostic artifacts, accepted selectors and historical publications. Stop for separate execution authorization.


## D051 — Retain RRF and close the ranking comparison

- **Date:** October 26, 2026 (America/Los_Angeles).
- **Status:** OWNER_ACCEPTED / CLOSED, explicit project-owner decision.
- **Decision:** Retain RRF(k=60) as the default ranking method for the Week 2 POC. Do not adopt MiniLM into active retrieval. Preserve the versioned experiment, acquired assets and windowing adapter.
- **Rationale:** On identical pools for 15 frozen questions, MiniLM modestly improves top-10 completeness but regresses at other cutoffs and adds substantial CPU latency. RRF offers the selected quality/performance/complexity trade-off for this bounded POC.
- **Alternatives:** Adopt pinned MiniLM plus windows, or retain both as active ranking choices; neither is selected. BM25-only and vector-only modes remain available. No runtime configuration changes occur.
- **Record:** [Versioned ADR D051 v1.0](adr/D051-rrf-ranking-decision-v1.md), including methodology, measured results, known failures, limitations and reconsideration criteria.
- **Bindings:** Accepted experiment manifest SHA-256 `d4147705c4c648e29ef8a806a5e77345925b0d2d4827d94edd79bdee5dc057d9`. Additive owner receipt `data/evals/ranking/approvals/phase3-owner-closure-v1.json`, SHA-256 `a2954316547574ffd5fcd44875a2f563242ac1c21344123fd0c11b2fccc453d7`. No identity or digital-signature attestation.
- **Boundaries:** No universal cross-encoder conclusion or M8 budget-success claim. Oversized M8 parent envelopes remain unresolved. Accepted M0–M9 and M7/M8 implementations/configurations remain unchanged. STOP for separate authorization before any next workstream. This closes the later authorized D050 experiment; D050's original registration-time restrictions remain historical.

## D052 — Semantic grounding as the primary post-generation validation criterion

- **Date:** October 29, 2026 (America/Los_Angeles).
- **Status:** Accepted architectural direction; technical implementation and semantic-evaluation coverage require separate verification and owner review.
- **Decision:** Strict citation/source integrity, presentation-tolerant quotation fidelity, independently assessed semantic grounding and completeness, and material qualifications/conflicts determine answer quality. Unresolved essential assessment yields REVIEW_REQUIRED.
- **Rationale:** Q04's valid citations failed raw formatting checks; that does not establish factual error. Authentic citations and string similarity also do not establish semantic support.
- **Alternatives:** Keep raw exact matching as the overall gate; force PDF-format copying; broad fuzzy matching. Select bounded fidelity plus independent evidence-aware assessment.
- **Record:** [D052 v1.0](adr/D052-semantic-grounding-validation-v2.md), [implementation contract](ANSWER_QUALITY_VALIDATION_V2.md). Original Q04/Q05 artifacts and verdicts remain immutable. No new provider calls or generation are authorized.

## D053 — Local authenticated human-review workflow

- **Date:** October 29, 2026 (America/Los_Angeles).
- **Status:** Owner-authorized implementation; technical review pending, real enrollment/approval not executed.
- **Decision:** Local OS-operator enrollment, passphrase-protected signing keys and separately confirmed, exact hash-bound decisions through existing HumanReview and v2 evaluation.
- **Rationale:** Supply the missing authenticated reviewer/artifact trust without an unnecessary identity service or invented owner identity.
- **Alternatives:** Name-only approval; external identity provider; manual external hash configuration only.
- **Record:** [D053](adr/D053-local-human-review-workflow.md), [owner instructions](HUMAN_REVIEW_WORKFLOW.md). No generation/API spending authority is conferred.

## D054 — Lightweight local owner review for the Week 2 POC

- **Date:** October 29, 2026 (America/Los_Angeles).
- **Status:** Owner-authorized implementation, technical review pending; Q04 approval not executed.
- **Decision:** Localhost-only `LOCAL_POC_REVIEW`, explicit owner label/confirmation and `OWNER_APPROVED_POC` attestation; unchanged signed mode remains optional.
- **Rationale:** Keep educational POC review simple while clearly distinguishing unsigned attestation from authenticated validation.
- **Alternatives:** Mandatory signing for all reviews; mislabeling an unsigned approval as authenticated HUMAN_REVIEW.
- **Record:** [D054](adr/D054-local-poc-review.md). Strict source/citation checks and D052 validation remain unchanged; no generation permission is granted.

## D055 — Single-turn Bot with a shared native backend and operational trace

- **Date:** November 1, 2026 (America/Los_Angeles).
- **Status:** Owner-approved direction and implementation scope; offline implementation awaiting owner review. No live Bot execution authorized.
- **Decision:** Use the existing services/native runner from both the Streamlit Bot and backend CLI. Keep chat single-turn and uncached; retain private immutable Bot question/execution records and project them across operational dashboards. Exclude unlabeled Bot questions from the frozen offline benchmark.
- **Rationale:** Enable repeatable backend simulation and traceability without creating another retriever, generator, database or chat-history service.
- **Alternatives:** UI-only execution; modifying frozen benchmark membership; a separate Bot generation implementation; discarding diagnostic records with chat display state.
- **Record:** [Runtime modes, storage, trust and execution boundary](RAG_BOT_RUNTIME.md). Live consent, provider preflight and Bot spending limits remain a separate owner checkpoint.

## D055 — Simple localhost Bot consent and persistent spending controls

- **Date:** 2026-11-01 (America/Los_Angeles).
- **Decision:** [Local chat Send consent](adr/D055-local-chat-send-consent.md), with fixed $0.03 per question and owner-selected $1.00 persistent total Bot ceiling.
- **Rationale:** Normal POC chat should reuse native safeguards without requiring a policy migration and two approval forms for every question.
- **Alternatives:** Keep exact-question-only activation; remove native consent/budget safeguards; create another runner.
- **Status / authority:** Owner approved scoped implementation and $1.00 Bot budget configuration; offline implementation verification and separate real activation approval remain distinct checkpoints. No provider execution authorized by this decision.

### D055 amendment — Default Chat Send consent

- **Date:** 2026-11-02 (America/Los_Angeles).
- **Decision:** Normal Chat no longer requires a separate enablement step; exact Send authorizes one submitted question within the existing $0.03/question and persistent $1.00 Bot cap.
- **Rationale:** Deliver the expected type → Send → answer or clear stop reason while preserving native safeguards.
- **Alternatives:** UI-only concealment, repeated enablement, or relaxed integrity/budget controls; rejected.
- **Status:** Owner-approved bounded implementation and offline verification; no live test executed by this change.
- **Record:** [D055 amendment and historical decision](adr/D055-local-chat-send-consent.md). Old controls remain immutable; developer modes are optional and cannot submit through the main composer.
