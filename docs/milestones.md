# Milestone review checkpoints

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

## Post-M9 owner direction — October 26, 2026

M0–M9 are **OWNER_ACCEPTED / CLOSED**. D049 records explicit M9 result acceptance and the technically completed, bounded saved-record ten-case BM25 diagnosis. See [diagnostic findings](M9_BM25_DIAGNOSTIC.md). M10–M11 remain **PLANNED_NOT_AUTHORIZED**. D041–D048 and D050 remain the architectural direction; compact evidence, runtime gates and remediation are not implemented or authorized.

Sequence: **M9 acceptance (complete) → ten-case diagnosis (technically complete) → ADR D050 registration (complete) → separate bounded ranking-experiment authorization → five-question ground-truth review → controlled same-pool RRF/cross-encoder comparison → owner decision → separately authorized M8 refinement → explicit M10 approval → separately approved M11 demonstration**. See [D050](decisions.md#d050--hybrid-candidate-discovery-and-relevance-reranking) and [readiness sequence](architecture.md#post-m9-direction-and-m10-readiness).

The planned 15-question experiment reuses the exact ten diagnosed M9 cases and unchanged approved labels, plus five new beginner questions requiring owner label review before scoring. Compare RRF constant 60 with a separately selected/pinned local cross-encoder using the identical union of BM25 top 50 and vector top 50 per question. Measure ranking/discovery coverage, MRR@10, group completeness, stability, latency and resource cost; stop at ranked candidate IDs. No questions, models, code or results are created by this documentation checkpoint. M8 budgeting/selection, compact evidence and runtime gates remain separate future authorizations.

Recommend BM25 top-K 10 / depth 50 provisionally; retain alternatives and accepted defaults. Treat 32K BGE as a tested completeness scenario, not the final model budget. Plan pre-generation integrity/preservation gates and separate post-generation semantic validation; neither runtime benchmark oracles nor deterministic guarantees of semantic sufficiency are permitted. Plan a separate beginner-focused set without altering benchmark-v1 or inventing approved labels. Keep the optional chunk-size experiment and all eight canonical Post-M11 findings pending.

The existing master tracker remains the sole milestone tracker: `workspace/rag-implementation/v1/MILESTONE_TRACKER.json` (with its Markdown view). Sealed reports, upstream contracts and publications remain unchanged. Historical forward-status paragraphs below retain their delivery-time scopes and are superseded by this dated checkpoint.

**Forward status — October 25, 2026:** H0–H5 and M0–M4 are OWNER_ACCEPTED / CLOSED. The durable 553-unit / 992-chunk / 992-vector successor is accepted for engineering integrity; retrieval-quality comparison remains at M9. SH-08 is resolved, SH-09 remains OPEN pending an authorized source-control checkpoint. M5 is NOT STARTED / NOT AUTHORIZED. The existing master tracker retains exact acceptance receipts and selector/model fingerprints. See [current operations](current-operations.md). Earlier entries below retain their historical scopes.

## Historical master-plan checkpoint — October 23, 2026

M0 (contract), M1 (preparation/profiling), M2 (C01 chunking comparison) and **M3 (catalog/lineage) are OWNER_ACCEPTED / CLOSED**. The M0–M11 master-plan IDs are distinct from older ingestion milestone numbers below. The single working tracker remains `workspace/rag-implementation/v1/MILESTONE_TRACKER.json`.

M3 accepts `config/retrieval-chunks-m3-c14-scope-v2.json`, manifest SHA-256 `f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c`, with the explicit C14 unified/PDF selections. All 553 verified units have 992 chunk representations; no unresolved chunking intervals remain in admitted source fields. The 358 source QA HOLD Sections remain unchanged. Default 384 BGE tokens, accepted selective maximum 512, actual maximum 507. Qualifications and full-parent obligations continue downstream.

**M4 is authorized for implementation only; results require owner acceptance.** [The M3-to-M4 handoff](M3_TO_M4_HANDOFF.md) specifies entry criteria and exact input bindings. The later explicit M4 decision authorizes pinned local BGE weights and embeddings only. ChromaDB, BM25, retrieval and generation remain unapproved. See [M4 implementation](LOCAL_EMBEDDINGS.md). No historical default selectors are switched. All remaining paragraphs/tables are historical execution checkpoints, not the current master-plan authorization gate.


Historical checkpoint (2026-10-19): **Phase1D is formally closed.** The user approved Recommendation A and froze `hybrid-reconciliation-4-phase1d-v1` for the [demonstrated experimental PDF scope](pdf-experimental-freeze.md), preserving all exclusions and HOLD obligations. This is not production adoption, whole-source readiness or content-promotion permission. The user subsequently approved bounded EXT-01 execution under D022. Its isolated foundation and test-only extension are implemented and verified, awaiting review; all later work requires separate approval.

Historical Phase1B checkpoint (2026-10-19): the user authorized **Phase 1B only**, with Phase 1A complete. Experimental PDF corrections and validation are implemented in the next version of the same private workstream. Fresh source references and implementation were frozen before scoring. Stop for review of actual per-source results, including missed targets and unresolved mathematical/structural evidence. Historical artifacts and 40 eligible / 1,634 HOLD decisions remain unchanged. Production integration, acquisition, further phases and Milestone 3 require separate approval.

Historical execution authorization (2026-10-19): **PDF remediation Phase 1A only**, the first checkpoint of one cohesive workstream. Implement the isolated source-span completeness guard, regress all five known terminal-hyphen cases, report unresolved residues, and prepare the C01/C06 independent review packet. Preserve production code and all historical artifacts/approvals. The user independently reviews batches of approximately 5–10 cases with ChatGPT technical support; actual review time and decisions remain pending until supplied. Stop after Phase 1A; no later phase, promotion, acquisition or Milestone 3 is authorized. This supersedes earlier statements that all remediation execution was unapproved.

Only Milestone 1 was authorized by the bootstrap prompt. Milestone 1 is formally accepted; Milestone 2 G0–G2 was explicitly authorized by the user.

Historical approval gate (superseded by later accepted checkpoints): Phase1D experimental freeze is accepted; EXT-01 implementation must stop for review before any additional parser checkpoint or production integration. The earlier Phase1B checkpoint below is historical. Earlier Milestone 2.5 is implemented with a blocked prose cohort; its independent review and remaining HOLD decisions are not superseded. Milestone 3 and downstream work remain unauthorized. No formal Milestone 2/2.5 acceptance is inferred from execution approval. See docs/content-validation.md and workspace/MILESTONE_2_5_RESULTS.md.

At every major milestone: explain scope, components, Academy learning objective and trade-offs; implement only authorized scope; run appropriate checks; update private progress records; present files changed, actual results, limitations and proposed next work; then stop for explicit approval. A proposed milestone is not authorization.

| Milestone | Scope / evidence at review | Status |
|---|---|---|
| 1 | Requirements reconciliation, repository/environment, contracts, smoke tests and documentation | Accepted by user |
| 2 | Permitted local C01/C04/C06 source validation/provenance, PDF/MDX parsing, normalization and HOLD review (G0–G2 only) | Implemented; awaiting review |
| 2.5 | Deterministic risk/validation checks for all 1665 HOLD sections; adaptive review; tightly controlled low-risk promotion; no medium-risk automatic promotion | Execution approved; implemented, awaiting independent review |
| EXT-01 | Isolated frozen extension foundation; owned local plain-text adapter through shared normalization/QA, failure paths and preservation evidence | Execution approved; implemented and verified, awaiting user review |
| 3 | Proposed controlled chunk comparison and passage-label audit | Not authorized; exact scope to approve |
| V1 corpus expansion | Required URL-based source acquisition and HTML parsing for remaining eligible sources; source access/use review, immutable bytes/hash/version provenance, semantic article structure and HOLD validation | Required capability; later milestone execution to approve |
| Later | Local embeddings/index, retrieval/evaluation, grounded generation, Streamlit and submission assets | Sequence/scope to approve incrementally |

Do not silently include later stages in Milestone 2. Keep quality targets separate from achieved results. Exact downstream milestone boundaries will be agreed as work proceeds.

Detailed authorized Milestone 2 scope, acceptance criteria and approval checkpoint: `workspace/MILESTONE_2_PLAN.md` (private draft). Chunking/G3 is outside this milestone; the engineering specification’s full ingestion Definition of Done is not reached at G2.


HTML and URL acquisition are required for the intended 16-source V1, not optional enhancements. Implement them before freezing/evaluating the expanded eligible corpus; exact milestone placement remains to be approved. No acquisition, HTML parser or new source download is part of Milestone 2.5.
