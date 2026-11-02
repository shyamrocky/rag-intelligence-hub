## H4 current explicit inspection modes — October 25, 2026

**Forward status — October 25, 2026:** H4 is now OWNER_ACCEPTED / CLOSED. The four-mode implementation is preserved; H5 adds operational documentation only. See [current dashboard operation](current-operations.md#dashboard). Historical implementation/delivery status below is not a new approval boundary.

H2/H3 are owner accepted. H4 is technically verified, pending owner acceptance: 1,388unique tests in the full H1 gate, including 48 dashboard controls (17 actual AppTest nodes). Historical 550/893, C01 catalog 61/88, pre-migration 553/992 and durable 553/992 remain separate explicitly selectable stacks. The durable mode is the current operational candidate; historical defaults remain unchanged. No real browser was available; verification uses actual Streamlit AppTest and local server startup, without screenshots. See [operational selection contract](OPERATIONAL_SELECTION_CONTRACT.md) for current launch, cache and qualification rules. The report below retains its earlier historical scope.

# Ingestion Pipeline Dashboard v1

Local read-only inspection of the accepted [unified consumption layer](UNIFIED_CONSUMPTION_LAYER_DESIGN.md).
The project owner accepted that layer and authorized this dashboard on October 22, 2026.
The [ingestion freeze](ingestion-poc-freeze.md), native readers, admissions and original publications remain unchanged.
Dashboard delivery awaits owner review; it does not authorize downstream RAG work.

## Launch

From the repository root, using Python 3.12 and uv:

```sh
uv sync --project apps/ingestion_dashboard --locked
uv run --project apps/ingestion_dashboard --locked streamlit run apps/ingestion_dashboard/app.py
```

Open `http://127.0.0.1:8501`. The private accepted corpus/evidence must be present.
A public checkout without those files displays a diagnostic, not fabricated corpus data.
No API keys or model downloads are required. Streamlit usage telemetry is disabled and the server binds to loopback.
Stop with Ctrl-C. Do not expose this private inspection application as a public service.

The dashboard has a small separate uv project/lock under `apps/ingestion_dashboard/`.
This is necessary because the accepted unified baseline binds the **root** project/lock hashes.
Adding Streamlit to those files fails the accepted integrity guard. Both root files remain exact.
The application environment installs the existing package editable from the repository, plus Streamlit;
it introduces no separate backend. Streamlit is Apache-2.0; existing corpus/PyMuPDF licensing boundaries remain.

## Components

| File | Responsibility |
|---|---|
| `apps/ingestion_dashboard/app.py` | Single entrypoint; derives the repository root from its location |
| `src/rag_hub/dashboard_ui.py` | Native Streamlit views, navigation, optional provenance expanders, resource cache |
| `src/rag_hub/dashboard_data.py` | Thin read-only catalog/evidence queries and allowlisted inspection metadata |
| `.streamlit/config.toml` | Light theme, loopback address and telemetry setting |
| `tests/test_ingestion_dashboard.py` | Actual public-contract and Streamlit interaction controls |

There is no dashboard admission logic, source-readiness determination, parser, database or new publication.
The only normal corpus entrypoint is `load_verified_corpus`. Native readers are not imported by dashboard code.
The descriptive freeze remains INSPECTION_ONLY, not an authorization ledger.

## Views

**Pipeline Overview:** Acquisition → Classification → Parsing → Recovery & Assembly → QA Validation → QA Publication → Unified Layer.
These are navigation cards describing existing frozen work, not new stage executions or invented success statuses.
Normalization is represented within parsing/recovery for presentation; its underlying ownership is unchanged.
The admission bar distinguishes admitted/excluded/HOLD, with exact format totals and inherited PDF issue categories.

**How Sections Become Verified Units:** the Recovery & Assembly visualization sits between parsing and QA in the displayed chain.
An explicitly illustrative S01–S04 → U001 example teaches the process without corpus IDs or approval claims.
Actual mode selects an existing document/unit and obtains every edge from `catalog.get_unit_sections`.
Native structural type, role, native role, locator, context-only and scope restrictions remain visible.
Buttons navigate Section → Unit → all related Sections. Duplicate roles are retained; unique Sections are counted once.
Published source-content structure and required-context references are shown when present.
Otherwise the UI says: “Verified membership established by the accepted QA publication; original assembly rationale not separately recorded.”
Source positions alone never establish a claim that geometry or paragraph continuity created a relationship.

**Document Explorer:** sortable document inventory, format/publisher/ID-title search and QA filters;
source/snapshot, parsing and QA tabs; searchable, paginated Section inventory. Document selection opens details.

**Section & Unit Inspector:** exact-ID lookup and reverse links. Every Section is visible as inspection metadata.
Only a verified, publication-qualified Unit ID opens content. Context-only Sections require their complete unit.
HOLD/excluded Sections have reasons/citations but no raw source preview or evidence membership.
Unit view preserves mandatory restrictions, source content, required context, QA observations, citations and publication identity.
No chatbot, retrieval chunks, embeddings or generation are present.

## Inspection versus evidence

Catalog information is labeled **INSPECTION_ONLY**. Evidence is labeled **VERIFIED_CONSUMER_EVIDENCE**.
Supplementary structural typing uses canonical artifact references already hash-bound by the accepted corpus.
Each record's document ID and actual raw-source SHA must match its catalog document.
Only `block_type`/native classification and provenance references are retained; source text and historical status fields are dropped.
Nested QA issue evidence can contain raw source trees/text; the UI therefore allowlists observation fields and omits those payloads.
Supplementary metadata never changes catalog status or memberships.

PDF component receipts record `maintained-pymupdf`, adapter/dependency versions and original block parser versions.
They do not prove Docling/MinerU selection for an individual Section; that limitation is explicit.
HTML/Markdown canonical records lack a separate parser-execution receipt in this selected inspection path;
the UI displays “Not available in the frozen evidence.” Normalization versions, where recorded, are labeled accordingly.
Historical comparisons and optional model workstreams are not relabeled as selected corpus outputs.

Content comes exclusively from `evidence.get_verified_unit`, checked through the native validated serialization contract.
The UI renders the authorized `llm_context` fields and citations/publication metadata; opaque native/audit fields remain inaccessible.
Restricted Markdown renders its exact native warning-bearing `consumable_text`, never alternative raw segments.
Tables use explicit native rows/headers when rectangular and unambiguous; other structures remain faithfully visible as structured data.
No cell associations or formula repairs are inferred for display. Source strings use literal text rendering rather than executable HTML or remote images.
HTML C10's scoring ambiguity remains a QA observation with linked RRF context, not a publisher claim/error certification.
PDF scope restrictions, heading safeguards, attribution and live expiration warnings are retained.

## Caching and failure handling

`st.cache_resource` retains one `DashboardData` per repository root. An `RLock` serializes access across local sessions.
The accepted unified snapshot remains immutable and checks its filesystem leases on every public access.
Supplementary inspection inputs also retain bound-file leases. No detached evidence, full catalog export or inspection JSON is cached as authority.
The public binding manifest is generated once at construction to authenticate supplementary metadata.
Widget interactions query catalog pages rather than exporting the full catalog again.

Any changed binding invalidates access. The UI shows a diagnostic and offers **Rebuild verified snapshot**;
that clears the resource and calls the original verifier. It does not silently repair files or bypass a failed hash.
PDF expiration is refreshed on each evidence access; valid but expired approved content remains readable with its user-visible warning.
Integrity failures remain blocking. Unknown IDs have a safe user-facing error.

## Decision

ID: DASH-01. Date: October 22, 2026. Status: owner-authorized implementation, delivered for review.
Decision: one native Streamlit application over the accepted catalog/evidence gateway, with an isolated dependency environment.
Rationale: expose ingestion quality and exact published relationships while preserving frozen contract hashes and QA ownership.
Alternatives: change root dependencies/unified bindings; reconstruct catalogs from native readers; add a backend or graph framework.
Those changes are unnecessary for this bounded inspection milestone.

Verification, actual performance and limitations: [INGESTION_DASHBOARD_VERIFICATION.md](INGESTION_DASHBOARD_VERIFICATION.md).
API basis: [Streamlit resource caching](https://docs.streamlit.io/develop/concepts/architecture/caching),
[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest),
and [dataframe](https://docs.streamlit.io/develop/api-reference/data/st.dataframe).
