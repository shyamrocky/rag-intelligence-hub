# M0/M1 delivery verification

Status: implemented and technically verified; **pending project-owner review**. M2 has not started. The owner-authorized direction and data contract are documented in [CHUNK_PREPARATION_CONTRACT.md](CHUNK_PREPARATION_CONTRACT.md).

## Delivered behavior

Three additive modules provide the closed versioned input schema, live-gateway preparation/validation, and read-only descriptive profiling. No existing source, QA, unified, dashboard, dependency or chunker file changed. All 61 C01 units produce complete deterministic preparation records, preserving source/context/QA separation, exact native source fields, membership roles and publication bindings. Full-format contract controls also represent all 550 existing native units without changing their authority.

Four restricted Markdown renderings are retained as protected, warning-bearing projections with no independent source-text candidate. This preserves their native constraints without pretending M0/M1 has solved their later embedding projection policy. HTML C10 context and QA observations, PDF limited spans and historical expiration warnings remain bound.

Durable private outputs are under `data/preparation/chunk-input-v1/C01/`. Detailed results, preview, logs and the authoritative M0–M11 working tracker are referenced in the contract. The profiling report is `workspace/rag-implementation/v1/m0-m1/C01_PROFILING_REPORT.md`.

## Actual checks executed

| Verification | Result |
|---|---|
| New M0/M1 focused tests | 25 passed in 228.06 seconds |
| Applicable existing ingestion/QA/consumer/unified regressions | 944 passed, 1 deselected in 551.02 seconds |
| Dashboard/AppTest regressions | 36 passed in 93.44 seconds |
| Root Ruff | Passed |
| Root scaffold smoke | Passed; this is not RAG answer-quality evaluation |
| Fresh-process C01 records and profile replay | Byte-identical for both files |
| Existing baseline fingerprints | All 863 unchanged |
| Git HEAD / index | Unchanged; empty index; no staging, commit, merge or push |
| Privacy | Preparation data and workspace evidence remain Git-ignored |

**1,005 unique passing tests**: 25 + 944 + 36. An earlier 24-pass development run overlaps the final suite and is not added. The focused and dashboard suites emit five existing PyMuPDF binding deprecation warnings each. No final test failures or skips were reported.

The existing prospective QA test runner was reused without modification. One obsolete predecessor byte-identity assertion remains deselected as in the accepted baseline. Two legacy private acquisition/reparse/admission test files are intentionally uncollected; this milestone does not execute those workflows. No new exclusion was introduced to make the implementation pass.

Commands from the repository root:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked pytest -q tests/test_chunk_preparation.py

PYTHONPATH=workspace/unified-consumption/v1 \
RAG_TEST_QA_RELEASE=workspace/pdf-residual-recovery/v1/qa-regression-identity.json \
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked pytest -q -p regression_plugin \
  --ignore=tests/test_local_corpus.py --ignore=tests/test_validation_local.py \
  --ignore=tests/test_ingestion_dashboard.py --ignore=tests/test_chunk_preparation.py \
  -k 'not test_shared_guards_policy_and_contracts_are_reused'

UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --project apps/ingestion_dashboard --locked pytest -q tests/test_ingestion_dashboard.py
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked ruff check .
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked rag-hub smoke
```

Focused controls exercise the actual public evidence gateway, not a mocked admission authority: all 61 C01 units and all 277 admitted Sections; all three native formats; exact native source and context preservation; table/math/identifier payload equality; context-only, HOLD/excluded and forged-ID rejection; warning/context/qualification/publication stripping; nested mutable-field tampering; protected Markdown projections; unique-span accounting; append-only output behavior; and simulated expiration crossing. Expired content retains the same source payload with an added required warning. A stale prepared view must be refreshed through the gateway; no renewed owner approval is needed for unchanged published content.

## Fingerprints and performance

| Artifact | SHA-256 |
|---|---|
| C01 preparation JSONL | `2c6b956a3aab41006dbdce73001fb060d7cd6b232050b591667f07d920ee5b78` |
| C01 profile JSON | `6df462e10948cf7cd67071f3f983b0258ed9409439d1aca5a4a62e102ef85d95` |
| Preparation manifest | `cd1f992b2bb8b541593b37eacd1700f2ffaafc1ced507ce6039abb6e9747977e` |

One fresh build loaded the accepted corpus in 27.54 seconds and prepared C01 in 18.76 seconds. The complete build/validation/preview/manifest took 65.46 seconds with peak process RSS 2,185,216,000 bytes (about 2.04 GiB). Fresh-process replay took 72.17 seconds with peak RSS 2,006,351,872 bytes. These are local runs with warm filesystem/concurrent test activity, not isolated cold benchmarks or retrieval latency.

Reproduction applies to identical bound inputs, component versions and clock-derived warning state. Original source/publication identities are unchanged when a publication expires; the gateway refreshes the mandatory warning. Saved JSON is not a permanent evidence authorization.

## Profiling findings and limitations

- 61 units, 277 unique admitted Sections, 306 membership links, 20 shared Sections, 11 context-only Sections.
- 43 prose/section-text units, four tables, two existing mathematical references, ten captions, one bibliography and one document-citation unit; no C01 code unit.
- Median 96 lexical tokens per unit; P95 511; maximum 5,413 in the bibliography unit. Fifty units fit a 256 lexical screen; 56 fit 384.
- Eighteen units have existing scope-limited membership. Exact individual-Section source-token witnesses cover 254 of 266 body-associated Sections. Missing witnesses are disclosed rather than filled from unrestricted raw Sections.
- The lexical method is **not the BGE tokenizer**. Final model-token budgets, context reserves and split decisions remain unvalidated M2 work.

The profile makes no new extraction-quality, independent human-verification, retrieval-quality or scientific-correctness claim. All 550 units, 3,040 Sections, 2,572 admissions, 110 exclusions, 358 HOLD and 3,727 relationship links remain unchanged. All existing native qualifications and public contracts remain intact.

## Next approval checkpoint

Review the M0 contract, C01 preparation preview, dual-denominator profile and working milestone tracker. Acceptance of M0/M1 and explicit M2 authorization are the next owner decisions. Structure-aware splitting, model/tokenizer selection, indexing, retrieval and generation have not been implemented.
