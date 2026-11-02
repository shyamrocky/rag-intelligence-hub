# Unified Verified-Consumption Layer v1 — verification

Status: **implemented and technically verified; pending project-owner review**. Ingestion acceptance and QA decisions are unchanged. Scope/design and public usage: [UNIFIED_CONSUMPTION_LAYER_DESIGN.md](UNIFIED_CONSUMPTION_LAYER_DESIGN.md).

## Actual reconciliation

| Format | Documents | Canonical Sections | Admitted | Excluded | HOLD | Verified units |
|---|---:|---:|---:|---:|---:|---:|
| HTML | 11 | 457 | 427 | 30 | 0 | 155 |
| Markdown | 1 | 158 | 154 | 4 | 0 | 86 |
| PDF | 4 | 2,425 | 1,991 | 76 | 358 | 309 |
| Total | 16 | 3,040 | 2,572 | 110 | 358 | 550 |

All admitted Sections have verified unit memberships. All 110 excluded and 358 HOLD Sections are catalog-addressable without evidence access. The index contains **3,727 role-bearing membership edges**, preserves many-to-many links and never counts shared Sections twice. These units are not retrieval chunks.

Both directions are exposed: `catalog.get_section(section_id)` returns linked unit IDs/roles; `catalog.get_unit_sections(unit_id)` returns exact Section IDs/roles. Context-only, supporting headings, approved projections, native approval dependencies and required linked context remain distinguishable. No Section ID can be used as an evidence-unit handle.

## Newly executed verification

**944 unique tests PASS: 69 new focused tests + 875 applicable existing regressions. Zero final failures or skips.**

The new tests cover every Section/unit membership in both directions, exact counts, all 550 consumable units, citations/publication identity, C10 table/RRF/QA distinction, four restricted Markdown projections, context-only access restrictions, filters/pagination, detached response mutation, missing/foreign graph members, duplicate/colliding identities, historical/unknown selectors, source/publication/component corruption, timestamp/symlink replacement, rehashed altered units, stripped warnings/context, and expired-but-readable PDF content. The 550-unit validation loop explicitly prohibits per-lookup native loader/shared-QA re-execution; the immutable lookup implementation has no parser call.

Full existing regressions use the unchanged accepted prospective runner and test QA identity under `workspace/pdf-residual-recovery/v1/`, whose **60 foundation and 29 QA identity fingerprints were checked and remain exact**. The new test plugin selects that existing test harness in-process only; it changes no production entrypoint or default release.

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked pytest -q tests/test_unified_consumption.py

PYTHONPATH=workspace/unified-consumption/v1 \
RAG_TEST_QA_RELEASE=workspace/pdf-residual-recovery/v1/qa-regression-identity.json \
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked pytest -q -p regression_plugin \
  --ignore=tests/test_local_corpus.py --ignore=tests/test_validation_local.py \
  --ignore=tests/test_unified_consumption.py \
  -k 'not test_shared_guards_policy_and_contracts_are_reused'

UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked ruff check .
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked rag-hub smoke
```

Focused suite: **69 PASS in 168.38 seconds**, five PyMuPDF SWIG deprecation warnings. Existing suite: **875 PASS in 395.24 seconds**, one obsolete predecessor-byte assertion deselected as in the accepted baseline. Two legacy files that perform private historical acquisition/reparse/admission execution were intentionally uncollected; they are outside this read-only integration scope. The existing PDF compatibility controls are included. Tests are freshly executed, not reused historical scores.

Lint PASS. Scaffold smoke PASS (`pipeline_implemented=false` remains expected); no RAG-quality claim follows from that result. No dependency or lockfile changes.

Development logs retain an initial interrupted run that selected the historical default combined QA identity and correctly failed its obsolete maintained-byte fingerprint, plus a development snapshot invalidated when new implementation files changed during execution. Neither was treated as passing qualification. Final tests use explicit accepted selections/current test harness without weakening contracts or changing existing tests.

## Reproducibility and resources

Two independent processes called the unchanged native readers through the unified layer. Catalog bytes, complete consumer outputs, summary, membership-index digest and binding count match exactly, at the same expiration status. Each build verifies **408 bound files**. Clock-only PDF expiration warnings refresh at access without changing canonical catalog identity; a stale warning-stripped payload fails serialization.

| Measurement | Build 1 | Build 2 |
|---|---:|---:|
| Full verified load | 27.234 s | 27.552 s |
| Peak process RSS, including native verification | 1,901,297,664 bytes | 2,125,725,696 bytes |
| Evidence lookup mean, 100 lookups | 68.655 ms | 66.356 ms |
| Evidence lookup p95, 100 lookups | 83.752 ms | 80.254 ms |

Warm filesystem; other regression processes overlapped. These are adapter measurements, not isolated/cold throughput, source-quality metrics or retrieval benchmarks. Native source/publication replay dominates construction cost. Lookup checks filesystem leases and uses immutable in-memory payloads; it does not redo source-wide QA.

The complete optional catalog serialization is **26,768,862 bytes**, predominantly rich native unit metadata/citations and qualification metadata. It is generated on demand and is not duplicated as a persisted corpus. The persisted **50,848-byte** inspection-only manifest binds that serialization, all source/component dependencies and the relationship graph. No full source text export, evidence database or new cache import authority was created.

Private artifact: `data/validation/corpus-qa/unified-consumption-v1/CATALOG_SNAPSHOT_MANIFEST.json`.

- Manifest SHA-256: `db77bb5b34a4dde4b7ab6d17b72e3522e5a378d77e3316dd9b6c027200235218`.
- Catalog SHA-256: `a5927251ad00827659b56503c04584f668368cc06165cea029a72dd0c0fd33ab`.
- Bidirectional relationship SHA-256: `5de90b8ebe03aab4dce3fdb674e66ed67a31d905f36fbb934822e5efd644f34d`.

The manifest is an inspection/reproduction artifact, never a publication, active registry or accepted input to the evidence gateway.

## Preservation, files and limits

All **798 pre-existing source/test/config/doc/data files are unchanged**, including native loaders, canonical Sections, snapshots, policies and publications. All **15 sealed final-ingestion closure files remain byte-identical**. Git HEAD/index unchanged; no staging, commit, merge or push. Private output paths remain Git-ignored. Existing historical replay tests pass through their original interfaces. The original 40/1,634 ledger, PDF historical approvals/expiration safeguards, HTML C10 restrictions and Markdown qualifications remain intact.

Created maintained files:

- `src/rag_hub/unified_models.py`
- `src/rag_hub/unified_bindings.py`
- `src/rag_hub/unified_adapters.py`
- `src/rag_hub/unified_consumption.py`
- `tests/test_unified_consumption.py`
- `docs/UNIFIED_CONSUMPTION_LAYER_DESIGN.md`
- `docs/UNIFIED_CONSUMPTION_LAYER_VERIFICATION.md`

Created private inspection manifest under `data/validation/corpus-qa/unified-consumption-v1/`; execution/replay/preservation logs, request copies, benchmark/plugin helpers and delivery inventory under `workspace/unified-consumption/v1/`. The two canonical workspace context/progress records are updated with this checkpoint. No pre-existing maintained implementation file was edited.

Unexpected contract differences are documented in the design: Markdown's typed/restricted envelopes, C05's extra approval dependencies, and separately reviewed PDF heading evidence. No native contract was changed to hide them. Integrity leases assume trusted local Python code and ordinary filesystem semantics; this is not a hostile-process or privileged-filesystem security boundary. Private accepted artifacts are required to construct the verified corpus.

**Concrete blockers: none.** No additional owner review or mathematical certification is claimed. Stop here for project-owner review. Dashboard, chunking, embeddings, indexing, retrieval, reranking, generation and further admission changes require separate authorization.
