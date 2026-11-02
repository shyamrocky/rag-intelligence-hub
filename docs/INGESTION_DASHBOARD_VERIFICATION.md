## H4 current explicit inspection modes — October 25, 2026

**Forward status — October 25, 2026:** The owner has accepted H4 and reports successful manual inspection of the durable Pipeline Overview and Chunk Inspector. That owner observation is separate from the agent AppTest/server evidence below; no H5 agent browser screenshots are claimed. See [current operations](current-operations.md). H5 verification will be reported separately without rewriting frozen H4 results.

H2/H3 are owner accepted. H4 is technically verified, pending owner acceptance: 1,388unique tests in the full H1 gate, including 48 dashboard controls (17 actual AppTest nodes). Historical 550/893, C01 catalog 61/88, pre-migration 553/992 and durable 553/992 remain separate explicitly selectable stacks. The durable mode is the current operational candidate; historical defaults remain unchanged. No real browser was available; verification uses actual Streamlit AppTest and local server startup, without screenshots. See [operational selection contract](OPERATIONAL_SELECTION_CONTRACT.md) for current launch, cache and qualification rules. The report below retains its earlier historical scope.

# Ingestion Dashboard v1 — verification

Implemented for project-owner review. Launch and architecture: [dashboard design](INGESTION_DASHBOARD_DESIGN.md).
The accepted unified layer and all ingestion publications remain unchanged.

## Corpus reconciliation

| Format | Documents | Sections | Admitted | Excluded | HOLD | Verified units |
|---|---:|---:|---:|---:|---:|---:|
| HTML | 11 | 457 | 427 | 30 | 0 | 155 |
| Markdown | 1 | 158 | 154 | 4 | 0 | 86 |
| PDF | 4 | 2,425 | 1,991 | 76 | 358 | 309 |
| Total | 16 | 3,040 | 2,572 | 110 | 358 | 550 |

The existing index supplies **3,727 role-bearing membership links**. Sections shared by units are counted once.
PDF document counts reconcile to C01 406/277/19/110/61; C02 453/393/22/38/50;
C06 1,095/1,028/34/33/128; C14 471/293/1/177/70 (Sections/admitted/excluded/HOLD/units).
The displayed inherited HOLD categories are 156 visual/series, 101 structural/context, 54 math/attachment,
45 table/diagram and 2 extraction defects. These are not new dashboard diagnoses.

## Verification execution

**980 unique tests PASS: 36 dashboard-focused controls and 944 existing regressions (including all 69 unified-layer contract tests). Zero final failures/skips.**

Dashboard suite: 61.20 seconds. Existing suite: 530.18 seconds. The focused suite reported five PyMuPDF SWIG deprecation warnings; no final test errors. Root Ruff, scaffold smoke and both lock checks PASS.
Private execution evidence lives under `workspace/ingestion-dashboard/v1/` and is not an admission authority.

The dashboard controls exercise the real accepted private corpus/public contracts. They cover exact counts,
all member roles for a selected actual unit, reverse many-to-many links, illustrative-versus-actual separation,
context-only memberships, metadata-only HOLD/excluded access, publication provenance, C10 table/RRF qualifications,
four restricted Markdown projections, PDF restricted scopes, expiration warnings, tampering, invalid leases,
pagination/search, and safe unknown-ID handling. Streamlit AppTest exercises startup, warm reruns, document →
Section → Unit navigation, actual relationship nodes, C10 table rendering and restricted projection display.
Critical evidence validation is not replaced by mocked admission.

The combined regression run uses the **unchanged accepted prospective test harness**, as in the unified baseline:

```sh
uv run --project apps/ingestion_dashboard --locked pytest -q tests/test_ingestion_dashboard.py

PYTHONPATH=workspace/unified-consumption/v1 \
RAG_TEST_QA_RELEASE=workspace/pdf-residual-recovery/v1/qa-regression-identity.json \
uv run --project apps/ingestion_dashboard --locked pytest -q -p regression_plugin \
  --ignore=tests/test_local_corpus.py --ignore=tests/test_validation_local.py \
  --ignore=tests/test_ingestion_dashboard.py \
  -k 'not test_shared_guards_policy_and_contracts_are_reused'

uv run --locked ruff check .
uv run --locked rag-hub smoke
uv lock --check --offline
uv lock --project apps/ingestion_dashboard --check --offline
```

Two legacy private acquisition/reparse/admission test files are deliberately uncollected; one obsolete exact-byte
predecessor assertion remains deselected, matching the accepted baseline. No original tests/contracts are weakened.
Scaffold smoke is not a RAG-quality evaluation. Model inference, acquisition and downstream RAG are not run.

The server starts with the documented entrypoint. Local `/_stcore/health` and `/` both return HTTP 200;
the HTML response contains the Streamlit application shell. Streamlit AppTest, not that shell alone,
verifies executed application views. The available computer-use tool reported no available browser/native
pipe, so **no browser visual inspection or screenshots are claimed**.

## Measured performance

One fresh AppTest process with the actual native verifier; warm filesystem, potentially overlapping regression work.
These are server-side inspection timings, not browser paint/network latency, retrieval latency or RAG-quality metrics.

| Operation | Measurement |
|---|---:|
| Initial application plus verified corpus | 27.34 s |
| Verified resource construction | 26.81 s |
| Warm overview rerender, three interactions | 0.122–0.143 s |
| Document Explorer navigation | 0.282 s |
| C06 selection after PDF filter | 0.368 s |
| Section metadata lookup, 10 samples, mean/max | 58.8 / 59.3 ms |
| Validated C10 unit lookup, 10 samples, mean/max | 116.7 / 127.2 ms |
| Section Inspector render | 0.125 s |
| C10 Unit Inspector render, including member links | 0.943 s |
| Peak process RSS, including native verification | 2,112,503,808 bytes (about 1.97 GiB) |

The resource cache preserves the original filesystem leases; warm interactions do not execute native loaders,
QA assessment, parsing or full catalog export. Qualifications are not cached as detached evidence.
The separate local Streamlit environment occupies approximately 416 MiB; no models are installed.

## Preservation and limitations

The before/after inventory verifies all **808 pre-existing source/test/config/doc/data and root dependency files**
byte-identical, including accepted sources/canonical data, QA records, native readers and unified implementation.
All 38 sealed unified delivery files and 15 sealed ingestion-freeze files remain exact. Git HEAD/index are unchanged;
no staging, commit, merge or push. Private logs, receipt and memory records remain ignored.

An initial root Streamlit dependency attempt was correctly rejected by the existing root project/lock fingerprint guard.
Both root files were restored to their original exact hashes. The isolated dashboard project is the final solution;
no accepted fingerprint was relaxed. One development test incorrectly assumed the first C02 unit contained a shared
Section; it was corrected to select an actually shared Section and verify every reverse link. Development logs are retained.

Parser details remain limited to frozen provenance actually exposed/referenced: PyMuPDF's receipt and original block versions
are available; per-Section Docling/MinerU selection is not established by that receipt. HTML/Markdown parser execution
versions are not invented from normalization metadata. Unknown assembly rationale is explicitly unavailable.
Literal source rendering favors fidelity and safe inspection over publisher-perfect formatting. Complex table structures
remain structured data when a simple exact native row/header display is unsuitable. No full mathematical/visual fidelity
or whole-source readiness is implied by dashboard visibility. No authoritative status, membership or source text is inferred
by the visualization. No downstream implementation is authorized by this delivery.
