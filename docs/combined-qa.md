> Current HTML admission successor: see [automatic HTML qualification](html-automatic-admission.md).
> The predecessor results below are preserved historical scope; current opt-in publications do not rewrite them.

# Combined PDF and HTML QA successor

`config/combined-qa-successor.json` selects `combined-scoped-qa-1.0` explicitly.
It composes the existing PDF scoped extension with HTML QA v2. It is an engineering
integration, not content approval or ingestion readiness. Accepted Level 1.3 and
PDF-only manifests remain unchanged historical identities; their old fingerprints
must not be used to describe this new combined implementation. Application/parser
default dispatch is unchanged.

`shared.qa.assess` remains the sole QA owner. Its separate, default-None trusted
arguments are `pdf_prose_admission`, `pdf_replay` and `html_evidence`. The existing
`validation_reviews.make_decisions` remains the only content-decision function.
HTML checks enrich the existing ValidationResult; technical PASS cannot promote
content. Missing HTML evidence remains HOLD, violated evidence fails closed, and
source-wide independent fidelity remains manual-required. PDF authorization,
whole-parent safeguards, context projections and attribution remain intact.

Only three implementation files changed in this composition:
`content_validation.py`, `shared/qa.py`, and the PDF review module's release
validator. The HTML-owned modules were reused byte-for-byte. PDF decision models,
policy, decision engine, corpus and owner-approval bindings were not changed.
The release validator reuses the existing fingerprint mechanism with a fixed
combined component set, including the HTML implementation and source configuration.

Offline verification evaluated all 457 persisted HTML Sections through the shared
owner: 388 technical PASS, 69 technical HOLD, zero technical FAIL; all 457 remain
eligibility HOLD. Four-PDF validation results and all 1,674 legacy results are
unchanged. C04 still exposes its existing 40 eligible / 118 HOLD records; the full
historical ledger remains 40 eligible / 1,634 HOLD. No parser, content admission,
source-readiness gate, chunker, embedder or indexer ran.

The combined preparation for the eight pending PDF passages is
`data/validation/qa-integration/pdf-html-v1/pdf-handoff-preparation.json`.
It references the same pending consolidated record and source bindings while
selecting the combined release. Its publications list remains empty. Existing
PDF-only handoff artifacts are preserved as predecessor evidence. Content approval
and separately authorized QA publication remain required before any exposure.

Required reusable implementation remains in `src/rag_hub/`; durable non-promoting
QA verification artifacts live under `data/validation/qa-integration/pdf-html-v1/`.
The original `data/validation/html/v2/` delivery is preserved unchanged. New
artifacts identify their combined release rather than retroactively rescoring or
rewriting earlier results. No new eligibility store or readiness engine exists.

For the combined test selection, set
`RAG_TEST_QA_RELEASE=config/combined-qa-successor.json`. This affects test fixtures,
not application defaults. Run the PDF, HTML and C04 tests with the locked uv
commands. Private parser-reexecution and historical admission-publication tests
remain outside this integration checkpoint. The earlier exact predecessor model
hash assertion remains intact and is deliberately excluded for successor tests;
legacy model schema and behavioral checks still pass.

The current integration has no implementation blocker. Pending owner approvals
are content/execution boundaries, not a reason to repeat parser engineering.
