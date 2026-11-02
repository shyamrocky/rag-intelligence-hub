# Explicit dashboard release selection — H4

**Forward status — October 25, 2026:** H4 is OWNER_ACCEPTED / CLOSED by the project owner, including owner-reported manual browser inspection. H5 operational closure is authorized; no global defaults are switched. M4 remains pending acceptance and M5 unauthorized. See [current operations](current-operations.md). Implementation-era status statements below remain historical.

H2/H3 are owner accepted and closed. H4 adds read-only inspection choices; its implementation requires separate owner acceptance. It does not switch the historical default, publish QA, regenerate chunks or embeddings, or authorize H5/M5. The Unified Verified-Consumption Layer and its native publications remain authoritative.

Run from the project root using the existing locked dashboard environment:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline --project apps/ingestion_dashboard streamlit run apps/ingestion_dashboard/app.py
```

The sidebar **Operational release** selects a fixed compatible stack. No newest-file discovery, arbitrary selector paths or changed-ID aliases are supported.

| Mode | Native composition | Catalog selector | Catalog units / chunks |
|---|---|---|---|
| Historical full corpus | Original `load_verified_corpus` | `config/retrieval-chunks-v2.json` | 550 / 893 |
| C01 pilot | Original historical composition | `config/retrieval-chunks-c01-v2.json` | 61 / 88 |
| Accepted pre-migration full corpus | `load_c14_verified_corpus` | `config/retrieval-chunks-m3-c14-scope-v2.json` | 553 / 992 |
| Durable full corpus — current operational candidate | `load_durable_corpus` | `config/retrieval-chunks-m3-durable-v1.json` | 553 / 992 |

The C01 catalog is scoped to C01; its compatible ingestion corpus still contains the historical 550 units. Other modes expose their whole selected corpus. The first mode remains the historical default. Durable selection is explicit opt-in, rather than global default adoption.

The allowlist in `src/rag_hub/operational_selection.py` pins exact selector and manifest hashes. The native composition verifies its own QA/publication bindings. `ChunkCatalog` serves historical modes; `QualifiedChunkCatalog` serves both 992-chunk modes. Exact upstream-file equality is checked before loading; unsupported pairings fail rather than falling back. A missing or modified selector/manifest fails before cache access. Native leases continue checking required sources and witnesses on every query.

## Identity and session isolation

The cache key includes the selected mode, release, exact selector/manifest identities, upstream bindings and component fingerprints. One active corpus and catalog cache entry bounds retained snapshots. Native filesystem leases remain attached; cached source text is never an independent authorization. The verified binding map is captured once during construction, avoiding full catalog serialization on warm interactions.

Changing releases clears selected Document, Section, Unit and Chunk IDs, relationship selections, filters carrying lineage IDs, and pagination. Even common IDs must be chosen again. Previous rendered evidence is not retained in session state. IDs copied across releases receive ordinary unknown-ID rejection when they do not belong to the selected catalog. No reconciliation map is used as an alias mechanism.

**Rebuild verified snapshot** clears corpus, catalog and embedding-metadata caches and runs the native loaders again. It cannot repair altered artifacts or revive an invalid lease. Restoring the accepted files is necessary before reconstruction; no raw-source fallback exists.

## Qualified content display

The inspector opens and validates each chunk through the selected catalog before showing its search slice. Mandatory limitations, QA observations and live expiration warnings appear before source content. The complete authorized parent and required context are displayed alongside the slice. Supporting Sections retain all membership roles and scope limitations; published parent membership is not falsely claimed as exact character allocation.

Restricted C04 projections retain their complete-unit requirements. Source-defective code is attributed source material, not verified executable guidance. C06 prompts, C10 scoring observations and RRF context, C14 bibliography/appendices, and C16 examples retain their existing qualifications. Four approved selective 512-token exceptions remain visible through recorded token/configuration metadata. No new content is admitted. QA observations are labeled as our findings, distinct from publisher statements.

## Embedding metadata

The durable mode offers a separate read-only metadata check in the ordinary dashboard environment. It pins the accepted opt-in M4 manifest and catalog, hashes its artifact files and configuration bindings, and compares all 992 record IDs, order, parent bindings and chunk hashes against the selected catalog. It displays the model name/revision, dimensions, count and manifest identity. It does not import Torch, Transformers or Sentence Transformers, instantiate a model, decode vector arrays, or execute inference. Reading bytes for integrity hashing is distinct from numerical/model loading.

This view is `INSPECTION_ONLY_HASH_BOUND_METADATA`. It does not replace the numerical M4 reader or certify model quality. M4 owner acceptance remains pending. For actual numerical validation use the existing embedding environment and explicit successor described in [H2/H3](H2_H3_DURABLE_SUCCESSORS.md).

## Preservation and rollback

Only unbound dashboard/integration files and new H4 helpers/tests/docs are changed. The native QA, Unified Layer, chunk and embedding readers, accepted selectors and publication payloads remain unchanged. Dashboard edits were checked against 557 protected binding paths before implementation. There is no upstream identity migration.

To inspect history, select the historical mode. To roll back H4 implementation, restore only its recorded dashboard/documentation delta in a separate verified root; do not overwrite native publications or use Git clean/reset. H0 and accepted H1/H2/H3 records remain available. See the private H4 exit report for verification, performance, exact file inventory and H5 handoff.
