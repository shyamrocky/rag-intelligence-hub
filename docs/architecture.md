# Architecture and requirement reconciliation

## Current bounded direction — answer-quality validation (October 29, 2026)

[D052](adr/D052-semantic-grounding-validation-v2.md) accepts semantic grounding,
completeness, strict citations and material disclosures as the primary answer-quality
criteria, with bounded presentation-tolerant quotation diagnostics. Implementation
and offline verification are authorized; independent semantic acceptance remains
pending. Original Q04/Q05 verdicts and M0–M9 contracts remain unchanged. No provider
calls, generation, retrieval changes or M11 execution are authorized.


## Current owner decision — Phase 3 closed (October 26, 2026)

[D051 v1.0](adr/D051-rrf-ranking-decision-v1.md) records **OWNER_ACCEPTED / CLOSED**
for the completed ranking comparison. Retain RRF(k=60) as the Week 2 POC default;
MiniLM, its assets and windowing adapter remain versioned experimental artifacts.
The existing M7 selector, RRF configuration and all accepted M0–M9 artifacts remain
unchanged. Oversized M8 evidence envelopes remain unresolved. No M8 refinement,
new experiment, M10/M11 or Git action is authorized. Stop for separate instruction.
Earlier dated descriptions below retain their registration/delivery-time scope;
D051 and its additive owner receipt record the current closure.

## Post-M9 direction and M10 readiness

Date: October 26, 2026. Architectural direction D041–D048 and D050 is owner approved. D050 registers a documentation-only ranking-comparison direction; no experiment is authorized. Under D049, M0–M9 are **OWNER_ACCEPTED / CLOSED**, and the bounded ten-case saved-record BM25 diagnosis is technically complete for owner review. Compact evidence, runtime gates, remediation and M10/M11 remain **proposed, not authorized execution**. See [diagnostic findings](M9_BM25_DIAGNOSTIC.md). The canonical working tracker is `workspace/rag-implementation/v1/MILESTONE_TRACKER.json`.

The accepted engineering path remains source → shared QA publication → Unified Layer → M0/M1 → M2 → M3 → M4 → M5/M6 → M7 → M8. Measured M9 equivalence-aware Recall@10 / MRR is BM25 82.1% / 0.731, vector 69.2% / 0.581 and hybrid 82.1% / 0.707. Complete required evidence at 32K is 16/26, 11/26 and 15/26 respectively. These are small, source-anchored known-positive results, not universal relevance or answer-quality guarantees. Recommend BM25 top-K 10 / depth 50 provisionally for later experiments; preserve accepted M7 defaults and selectable vector/hybrid alternatives.

The proposed request path is:

**Question → M7 retrieval/ranking → M8 verified evidence assembly → pre-generation gate → M10 prompt and generation → post-generation validation → cited answer or abstention.**

The pre-generation gate must reuse live M8 verification for release/source compatibility, authorized complete parents, mandatory context and qualifications, citation validity, parent deduplication, token budgets, explicit omissions and configured minimum-evidence/support signals. PASS means configured checks pass; it does not certify semantic answer sufficiency. RETRY requires a documented bounded recovery path; ABSTAIN covers unavailable or insufficient support under the configured policy. Ordinary requests cannot consult benchmark known-positive labels. This gate is a consumption check, not another admission authority.

Post-generation validation separately checks citations/structure deterministically and assesses faithfulness, claim support, qualification disclosure, unsupported claims, relevance, completeness and abstention through explicitly identified semantic review or evaluation. No claim of guaranteed semantic correctness is approved. Full offline evaluations compare configurations during development; they are not run for every request.

| Order | Proposed action | Decision / authorization checkpoint |
|---|---|---|
| 1 | Review and accept the completed M9 result packet | Completed under D049; consolidated exact-identity owner receipt recorded |
| 2 | Diagnose the 10 incomplete BM25 cases at 32K | Completed read-only under D049; five retrieval misses, five oversized required parents, one overlapping selection case; stop for owner review |
| 3 | Register hybrid discovery / relevance-ranking ADR D050 | Complete, documentation only; existing RRF and M7 defaults unchanged |
| 4 | Authorize bounded ranking experiment, then review five new beginner questions and known-positive labels | Separate execution authorization; explicit label approval before scored execution |
| 5 | Compare RRF (60) and a separately selected/pinned local cross-encoder on the same BM25 top-50 / vector top-50 union | Ranked candidate IDs only; compare discovery/ranking metrics, stability, latency and resources; stop for owner decision |
| 6 | Refine M8 only after ranking review; assess compact evidence as separately scoped | Separate approval for parent grouping, token-cost assessment, budget-aware selection, context optimization, compact representation or runtime gate |
| 7 | Select one generation LLM and its tokenizer/context configuration; implement M10 with both gates | Explicit M10 implementation authorization; model, prompt contract and token allocation remain unselected |
| 8 | Compare answer quality and evidence budgets under fixed conditions | Separate M10 protocol approval; plan D048's distinct 10–15-question beginner answer-quality set with explicit label review |
| 9 | Deliver the end-to-end M11 demonstration | Separate M11 authorization |

D050's proposed experiment uses exactly the ten diagnosed M9 questions plus five separately reviewed realistic beginner queries. Preserve the ten approved labels and frozen benchmark-v1; no new questions are created by registration. Both rankers must receive the identical exact-ID union, retaining original ranks, native scores, release identity and deterministic tie-breaking. Evaluate equivalence-aware Recall@5/@10/@20, MRR@10, parent/group coverage, multi-evidence completeness and candidate-discovery recall before reranking, alongside stability and local cost. Unjudged candidates remain unjudged. A cross-encoder is unselected and uninstalled; neither superiority nor improved 32K M8 inclusion is established. See [D050](decisions.md#d050--hybrid-candidate-discovery-and-relevance-reranking).

The 32K BGE scenario is the highest-completeness budget tested, not a chosen LLM allocation. A 64K/100K budget might fit more parents but does not establish better answers. Distinguish retrieval misses from evidence-assembly failures before selecting remedies.

Compact-evidence investigation should preserve complete authorized source content, context, citations, qualifications and warnings while separating redundant prompt serialization from retained audit records. Q21's assembled cost is approximately 91K–97K; its native bibliography parent is 84,064 tokens with 3,294 source-text tokens. Several C16 parents exceed 700K, largely from repeated QA audit attachments. Native evidence remains independently accessible, and any proposed compact view must be revalidated against authoritative M8 immediately before consumption. A narrower source projection needs separate upstream authorization. No compaction, truncation or waiver of complete-parent restrictions is authorized here.

The approved 29-question benchmark, measured results, exact selectors and sealed M9 handoff stay unchanged. The optional 256-versus-384 retrieval experiment remains pending separate authorization. All eight deferred findings remain in the canonical Post-M11 backlog; source-control/current-recovery follow-ups remain separately tracked. The original planning update did not authorize execution; D049 subsequently authorized and completed only the saved-record diagnosis. No new benchmark, runtime gate, generation, compact implementation, artifact regeneration, default change or Git/backup action is authorized. Read [M9 evaluation](M9_RETRIEVAL_EVALUATION.md), [safe reproduction guidance](M9_REPRODUCIBILITY.md) and [the decision log](decisions.md).

**Forward status — October 25, 2026:** H0–H5 and M0–M4 are OWNER_ACCEPTED / CLOSED under D034. The accepted durable composition preserves 553 units, 992 chunks and 992 vectors through explicit selectors; historical defaults remain unchanged. M4 is a provisional BGE engineering baseline, not a retrieval-quality winner. Source-only Git staging/commit and M5 require separate authorization. See [current operations](current-operations.md). Earlier checkpoints below retain their historical identities and delivery-time status.

## Accepted M0–M3 architecture — October 23, 2026

M0–M3 are owner accepted. The accepted explicit M3 release has **553 verified units and 992 chunks across 16 documents**. Its selector is `config/retrieval-chunks-m3-c14-scope-v2.json`; the original 550-unit ingestion freeze and dashboard defaults remain historical, unchanged selections. Use [the accepted catalog contract](RETRIEVAL_CHUNK_CATALOG.md) and [M3-to-M4 handoff](M3_TO_M4_HANDOFF.md) for current downstream bindings. M4 execution is now authorized under D030, with implementation pending owner acceptance; no vector database or retrieval is authorized. See [local embeddings](LOCAL_EMBEDDINGS.md). Earlier checkpoint descriptions below retain their historical scopes.

**Immutable source → ingestion/parsing and normalization → QA approval/publication → Unified Verified-Consumption Layer → M0 preparation contract → M1 preparation/profiling → M2 structure-aware chunking → M3 catalog and lineage.**

Shared QA (`shared.qa.assess` / `validation_reviews.make_decisions`) issues the authoritative native decisions and immutable publications. The Unified Layer is the sole downstream admission/qualification gateway: it validates those published scopes, not new eligibility rules. Preparation, chunkers, catalogs and the dashboard cannot approve content. Source text, required source context and supporting headings, QA observations, qualifications, memberships/spans and publication/citation bindings remain distinct. Qualified source illustrations may be searchable within their approved projections; source defects, warnings and consumption restrictions remain mandatory.

M3 identities bind exact source slices, configuration and publication-qualified parents. Both graph directions preserve many-to-many Section membership roles without implying that context-only material is independently retrievable. Complete-parent rehydration through the supported reader is mandatory. Exact source slices are distinguished from display projections with parent-level citations. The 384-token default includes headings and special tokens; only four accepted selective exceptions use a 512-token limit (actual 385/474/485/507). No truncation is allowed. C14's 47-entry bibliography and Appendices A/B/C have separate published scopes; no new visual or mathematical certification is implied. See decision D029.


## Approved PDF checkpoint — 2026-10-19

Phase1D is formally closed. `hybrid-reconciliation-4-phase1d-v1` is frozen for its [demonstrated experimental PDF scope](pdf-experimental-freeze.md) under D021. Source-level readiness, production adoption and eligibility promotion are not granted. All excluded/uncertain evidence remains HOLD. D022 subsequently authorizes the bounded isolated EXT-01 foundation and test-only extension proof. That candidate is implemented for review; production adoption and additional parser work remain unapproved.

## EXT-01 isolated candidate — implemented for review

The frozen candidate adds trusted in-process parser registration with explicit format dispatch. Legacy source/registry version0.1 remains unchanged; minimal version0.2 subclasses admit named formats, while registration separately controls executable support. Existing ParsedBlock, Section, normalization, span guard, quality models and decision function remain in use. No new eligibility or readiness engine is introduced.

One shared candidate execution function owns stage publication for existing PDF/MDX wrappers and the test-only extension. Format adapters supply blocks, declared source-backed parents and an independent fidelity contribution. Generic conformance checks exact original spans, complete member coverage, heading resolution and declared reading order; it does not infer PDF paragraph correctness. QA retains source fidelity, structure and contextual dependence separately. The unchanged quality-1.0 engine retains new-format HOLD.

The candidate foundation and reused dependencies were fingerprinted before adding the owned plain-text adapter. Original production files and the103-file PDF freeze remain untouched. UTF-8 LF/CRLF/Unicode fixtures demonstrate shared-path conformance only. Synthetic heading/code line declarations do not establish general document understanding. Acquisition verifies existing owned local bytes; no new corpus source is acquired. QA remains partial for qualification, and the readiness gate is not executed. Production adoption requires separate approval.

## Approved ingestion ownership — 2026-10-19

The authoritative logical progression is **Acquisition → Parsing → Normalization → Quality Assurance → Ingestion Readiness Gate**. Parsing and normalization remain separate stages even when a diagram groups them visually. Reuse existing pipeline functions and models; stage ownership does not require a new service or orchestration framework.

Each source and execution attempt has exactly one published outcome per stage, owned by one stage-level component. Internal adapters/checks supply evidence rather than competing statuses. Every outcome identifies the source snapshot/hash, owner/version, contributing components, artifacts, checks, issues, provenance and actual execution timing. Missing, failed or unresolved required evidence prevents a successful stage outcome. Failed/blocked rows remain visible. Internal parallel work does not change logical progression.

| Stage owner | Responsibility |
|---|---|
| Acquisition | Consolidate authorized source acquisition, immutable bytes, identity and provenance |
| Parsing | Consolidate format adapters and their diagnostics into one parsing outcome |
| Normalization | Consolidate mechanical transformations and source accounting |
| Quality Assurance | Independently retain source-fidelity and structural assessments; consolidate both without concealing disagreement |
| Ingestion Readiness Gate | Sole publisher of source readiness (ready, conditional or blocked), based on authoritative upstream evidence and the existing authoritative quality/eligibility policy |

Only the quality/eligibility decision engine determines content eligibility; only the readiness gate determines source readiness. The future Admin Dashboard consumes standardized execution/stage/gate records and provides drill-down. It never reconstructs statuses or repeats eligibility/readiness business logic. Historical planning snapshots are not authoritative gate executions.

Phase 1A is the first checkpoint in one versioned PDF-remediation workstream. Its isolated guard supplies completeness evidence to a single experimental QA checkpoint owner. Other stages and the readiness gate are explicitly not executed in this attempt; historical inputs are referenced, not relabeled as new successful executions. Full QA remains partial while fidelity/structure review is pending. No production orchestration, eligibility policy, parser, schema or dashboard change is authorized. The experimental reporting contract is documented in [stage-results.md](stage-results.md).

Milestone 1 supplies contracts, not a working RAG application. The supplied nine-page Academy handout governs course requirements. Milestone 1 is formally accepted. Milestone 2 local ingestion through G0–G2 is authorized and implemented pending review. No chunking or downstream RAG implementation is authorized in this milestone.

Academy Part 1 asks for a one-liner and concise decisions covering audience/use case, corpus, ingestion/cleaning/freshness, chunking/embedding and retrieval. Faithfulness, latency and insufficient-evidence behavior must be explicit. Part 2 selects the build track. The project uses Python with LangChain and LangGraph where state adds value. A deterministic workflow satisfies the project direction; autonomous agents and hosted infrastructure are deferred.

Academy submission requires a Google Doc covering overview, datasets, prompts/instructions, iterations and learnings; a live demonstration video of at most five minutes including AI coding tool use; and GitHub code/workflow assets. The suggested use-case evaluation counts are examples, not mandatory counts for this custom use case. The chatbot UI is an Academy bonus but part of this project's intended product.

The handout mentions Nebius credits, which do not establish OpenAI API eligibility. Its chunk-size/vector-dimension advice is heuristic: actual tokenizer limits and evaluation must govern chunk budgets. Hybrid/reranking is advice; measure the dense and lexical baseline before adding it.

## Current stack direction

Per the bootstrap: Python/LangChain with LangGraph only when state adds value; local-first deterministic execution; initial C01/C04/C06 inputs expanding toward 16 eligible candidates. Local `BAAI/bge-small-en-v1.5` and persistent Chroma remain provisional until evaluated. Streamlit is the intended UI. OpenAI GPT API is the agreed generation-provider direction; exact model and API-credit eligibility remain open. GitHub is intended source control; Git is initialized locally on `main`, with no commit or remote. No AWS/Azure/GCP or dedicated hosted infrastructure is planned. Streamlit Community Cloud is optional future work.

## Components and learning purpose

| Boundary | Contract | Academy learning connection |
|---|---|---|
| Acquisition/parsing | SourceManifest → local bytes → ParsedBlock | Know the corpus, provenance and cleaning risks |
| Normalization/quality | blocks → Section, approved or HOLD | Preserve evidence before retrieval |
| Chunking | approved sections → Chunk with source spans | Compare fixed and structural boundaries |
| Embedding/index | approved chunks → versioned index | Separate representation from storage |
| Retrieval | query + snapshot → ranked Evidence | Measure passage coverage at top five |
| Generation | query + evidence → Answer/abstention | Faithfulness, citations and fallback |
| Evaluation | reviewed DEV/HELD cases → measured report | Reproducible quality and latency |
| UI | retriever + generator → conversational surface | Demonstrate cited answers and limitations |

Use small Python Protocol interfaces to keep stages independently replaceable and testable. Pydantic validates initial boundary types without importing provider frameworks. Ingestion now validates source/block/normalized hashes, UTC capture values, locators and exact-section review receipts; it produces typed HOLD sidecars and immutable local snapshots/runs. Chunk-span/index/citation invariants remain future work. A declared approval field alone is never permission to index. See docs/ingestion.md for conservative parser and review limitations.

Treat source text as untrusted data. Preserve page/heading/code/tab context, exact snapshot provenance, and transformation logs. Ambiguous equations/tables remain HOLD; verified samples cannot approve adjacent unreviewed content. Future adapters must enforce these gates at chunking, indexing, retrieval and citation boundaries.

## Evidence limits

All supplied Markdown reports and the Academy handout were read. Child2 validated candidate pages and proposed section anchors. Child3/4 were web reconnaissance with blocked local downloads. Child5 records actual historical parsing of three uploaded files. Child6 verified five samples, not whole documents. Child7 compared 84 fixed versus 100 structural chunks on 31 partial records using six TF-IDF questions; neither strategy is an established winner. Document hits and marker co-location are not passage Recall@5.

The local kickoff package includes the five-record normalization JSONL and historical manifest. The original C01/C04/C06 bytes are now present under data/raw/ and match every historical hash/byte count. The Child7 script/31 records/chunks/results, curriculum alignment PDF and three original research comparison reports are still absent. Those missing inputs are not reconstructed or treated as acquired. Historical hashes require recomputation from actual input bytes.

Project targets only: claim faithfulness ≥95%, passage Recall@5 ≥90%, citation support ≥95%, appropriate abstention ≥90%, p95 response ≤10 seconds. Freeze human passage labels and overlap criteria; score union coverage across the top five, keep unanswerable cases out of recall denominators, and reserve HELD cases from tuning. No scaffold test establishes RAG quality.


## Reconciliation with kickoff documents

This table records alignment and discrepancies; it does not approve new design choices.

| Reference / topic | Current alignment or discrepancy | Resolution / status |
|---|---|---|
| Blueprint: audience, course track, submission | Learn / Explore / basic Decide; Python code-heavy track; cited deterministic workflow; Google Doc, ≤5-minute demo and GitHub | Aligned; full application/submission are future work |
| Blueprint vs later architecture review/bootstrap | Blueprint leaves provider/runtime/UI open; later documents specify local execution, GPT direction and Streamlit, with BGE/Chroma provisional | Preserve historical drafts; use later explicit project direction without claiming provisional choices approved |
| Architecture decisions: corpus | Sixteen candidates; start C01/C04/C06; no guaranteed final count | Original files verified; user authorized private local processing; redistribution remains uncleared |
| Architecture decisions: stack | Local BGE-small/Chroma candidates, intended Streamlit, GPT API provider; LangGraph only if useful | Aligned direction; no embedding/vector/generation/UI integration installed or implemented, no exact GPT model or embedding revision selected |
| Ingestion spec: module layout | Scaffold groups parsing in ingestion.py and separates embedding/retrieval/generation interfaces; spec suggests acquire.py, per-format parsers, embed_index.py and answer.py | acquire.py, parse_pdf.py, parse_markdown.py, normalize.py, quality.py and pipeline.py now implement independent local ingestion boundaries |
| Ingestion spec: schemas | The initial scaffold lacked complete source original URL/size/language fields, normalized hashes, review/bounding-box metadata, HOLD sidecars and UTC handling; G0–G2 ingestion now supplies these. Numerical table reconstruction and downstream validation remain incomplete | G0–G2 fields/hashes/sidecars and exact-section review now implemented; numerical reconstruction/OCR and chunk/index/answer invariants remain deferred. Not full spec conformance |
| Ingestion spec: scope/gates | Spec's overall ingestion Definition of Done includes chunks (G3); proposed Milestone 2 stops at normalized sections/HOLD (G0–G2) | Explicit proposed milestone boundary, not completion of the full ingestion specification. Chunk A/B and Q01/Q03 passage audit move to a separately approved stage |
| Ingestion spec: parsers/formats | PyMuPDF + markdown-it-py selected for authorized local ingestion; only PDF + Markdown/MDX needed for the initial snapshots | Parser/license/platform checks before selection. HTML remains required eventual capability; implementation deferred unless an approved HTML input is explicitly added |
| Blueprint/Child6/Child7: quality | Five sample approvals and lexical proxies do not establish whole-source accuracy, a winning splitter, or passage Recall@5 | Aligned; no RAG quality targets claimed achieved |
| Handout vs GPT-credit assumption | Handout names Nebius credits; architecture review conditions GPT on verified entitlement | Open account/model/budget question before generation; no paid calls or provider substitution implied |

Public documentation records implementation status; the supplied kickoff documents remain unchanged. Private proposal details and progress live under workspace/. Milestone 1 formal acceptance and Milestone 2 authorization are separate decisions.


Current G0–G2 implementation and limitations are documented in [ingestion.md](ingestion.md). The three raw inputs are verified, but only explicit sample sections have review receipts; most content remains HOLD. Milestone 3 must be separately authorized.


## Approved roadmap update — 2026-10-19

Milestone 2.5 execution was explicitly approved and is implemented pending independent review: deterministic classification/validation of all 1665 current HOLD sections, adaptive representative review and controlled low-risk automatic promotion. Medium-risk PDF content must not be automatically promoted in this milestone. Unverified equations, tables, layout anomalies and incomplete contextual evidence remain HOLD. Future PDF automatic-promotion criteria may be researched/documented without enabling that path. The versioned post-normalization validation stage is documented in docs/content-validation.md; its new manifest preserves ingestion artifacts/receipts and holds unresolved context.

URL-based source acquisition and HTML parsing are required capabilities for the intended 16-source V1. A later explicitly approved corpus-expansion milestone must implement controlled acquisition of permitted original publisher URLs, access/use checks, redirect/canonical URL and actual acquisition/version/hash provenance, immutable raw snapshots, format dispatch and semantic HTML extraction preserving headings, code, tables and source anchors. Acquired HTML must pass the same provenance/quality/HOLD gates. Public accessibility alone does not authorize redistribution. New formats/parser versions need new validation cohorts; existing PDF/MDX approvals do not automatically qualify HTML. These capabilities must precede the expanded corpus freeze/evaluation; they are not implemented in Milestone 2.5.


## Validation results and boundary

Milestone 2.5 checks all 1665 baseline HOLD sections and adds separate policy/rule/sample/review-bound decisions. Forty sections are eligible in the stricter new manifest: 38 low-risk automatic C04 code approvals and two retained original manual C04 code approvals. C04 prose is blocked by an implicit-context rule miss; PDFs are never automatically promoted. Original nine review receipts remain unchanged; seven samples are suspended for new-manifest eligibility because source fidelity did not establish complete context. Current eligible coverage is not balanced across three documents and is not a full-corpus quality clearance. No chunking or downstream feature was added. Details and future PDF eligibility criteria: docs/content-validation.md.

## Source-grounded consumption refinement — 2026-10-22

The explicitly authorized C10 successor distinguishes publisher SOURCE_CONTENT, ingestion QA_OBSERVATION and mandatory QUALIFICATION in a versioned consumer envelope. Source-fidelity verification is separate from independent publisher correctness; standard references are not truth certification. BLOCKING integrity/evidence failures prevent admission, while admitted illustrative evidence can carry mandatory WARNING limitations. Dashboard views consume the same externally selected authoritative publication as the handoff. Source-bound context relationships preserve original element boundaries and do not constitute chunking or a knowledge graph. See [QA consumption contract](qa-consumption.md). Existing Markdown/PDF policies and historical publications remain unchanged.

## Full PDF text qualification successor

The explicitly authorized four-PDF recovery uses source-bound overlays and the
existing shared QA/decision owners. The new opt-in publication can represent
complete heading-scope text, restricted projections, printed table associations,
caption-only material and previously owner-verified mathematical transcriptions.
Canonical parsing/normalization and historical publications remain immutable.
Read [PDF text qualification and verified consumption](pdf-text-recovery.md).
Source-fidelity qualification does not certify publisher conclusions or grant
whole-source readiness. No default-reader expansion or downstream execution is
implied. Completed HTML/Markdown contracts remain independently selectable.
