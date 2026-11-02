# M5 persistent numerical index

M5 is OWNER_ACCEPTED / CLOSED by explicit project-owner instruction (D036), for the explicitly selected local engineering scope. It stores saved vectors and identity metadata; it does not authorize source evidence, embed queries, run semantic retrieval, or establish retrieval quality. M6 remains unauthorized.

The candidate contains all 992 accepted durable Chunk IDs, using the existing 384-dimensional float32 matrix. The accepted QA/Unified/M3/M4 selectors, model behavior and numerical bytes are unchanged. Four accepted environments retain their locks; a fifth isolated project is `tools/indexing/` (Python 3.12, ChromaDB 1.5.9, NumPy 2.2.6, complete transitive lock). This project intentionally does not import the application or execute embedding models. The existing embedding interpreter performed the live parent/input validation separately.

## Exact selection and inspection

Run from the repository root:

```sh
uv run --locked --offline --project tools/indexing python tools/indexing/m5_index.py inspect \
  --root . --selector config/vector-index-m5-v1-1.json \
  --selector-sha256 3ee50fc59ee126f0473332a7ca7d40ed35fd4b88baf3254cfd3b19a19d52503b
```

Optional `--document C01` filters metadata. Optional `--chunk-id <exact-qualified-ID>` performs exact-ID lookup. These do not run vector similarity search. Omitted selector/hash, wrong releases, missing records, altered vectors, unexpected metadata, documents or URIs fail closed.

Collection: `m5-7f94dadda7dc17b1305b720f6f574a0f435cea27a23879b3`.

Manifest: `data/indexes/m5-chroma-v1/7f94dadda7dc17b1305b720f6f574a0f435cea27a23879b33f41bd61f5b7ebb4/manifest.json`, SHA-256 `dbf55af00ed148854fbe8a59a075ec09e1bdaf33b58ddb3c5bd07d6d1dc6d063`.

The explicit selector pins that manifest. Its identity binds the accepted selectors, catalog/model/matrix/input records, complete durable file bindings, M5 implementation/lock/runtime, scalar schema, record inventory, dimension and L2 index configuration. L2 is used to retain exact normalized float32 values; no retrieval-quality preference is claimed. Logical records/manifests reproduce exactly; SQLite/HNSW UUIDs and physical bytes need not.

Metadata includes document/format, qualified Unit/Embedding references, row index, source-input/token/vector/qualification/publication/membership/catalog/model hashes, classification and mandatory complete-parent flag. Chroma stores no source text, complete parents, document payloads or URIs. It contains no independently indexed context-only Sections. No raw normalized fallback exists.

For evidence, use the unchanged accepted `EmbeddingArtifacts.open_bound_chunk(chunk_id)` in the embedding runtime, or the existing durable Chunk Inspector. The complete live parent, context, citations, QA observations, qualifications and informational PDF-expiration warnings must travel together. Numerical lookup is not an evidence authorization.

## Dashboard

```sh
uv run --locked --offline --project apps/ingestion_dashboard streamlit run apps/ingestion_dashboard/app.py
```

Select the durable operational release, open **M5 · Persistent local ChromaDB index**, and submit **Verify selected M5 index**. The panel invokes a fresh isolated worker, reports counts/disk/model/manifest/document filters and exact-ID metadata, and links to the existing authorized-parent inspector. All four previous inspection modes and the historical default remain. Database payloads never replace verified evidence. No M5 text/result authorization cache is retained.

## Operation and recovery limits

Existing installed M5 dependencies support offline startup. Reconstructing this fifth environment uses `uv sync --locked --offline --project tools/indexing` only with a complete compatible package cache. Package installation used public registries; index execution disables telemetry, uses no embedding function and denies Python network operations. This audit denial is not kernel isolation or proof about arbitrary native code. No local server, external service, API key or model download is needed.

Builds use an exclusive lock, unselected staging directory, complete checks, close/reopen, atomic version-directory rename and exclusive selector publication. Published collections are immutable through the supported interface. Repeat build validates an identical existing selection; it never upserts. Failed staging remains for review and is never resumed silently. The application reader is read-only, although Chroma may maintain internal database bookkeeping when opened.

Qualified local scope: one writer, at most two concurrently tested metadata readers, same host. The new environment is approximately 343 MiB; the full version directory is approximately 7.5 MiB. Fresh worker checks take approximately 1.1 seconds, around 0.36 GiB peak RSS; a build peaked around 0.52 GiB. The existing full parent gateway remains substantially larger. Measurements are not service SLAs or cross-platform qualification.

Rollback by leaving the M5 opt-in selector unused and using the accepted M0–M4 readers. No historical selector/default was changed. Retain private index inputs/manifests, the fifth lock/cache, source checkpoint, H0 and post-H0 private evidence for recovery. Current-state off-device restoration is still unverified. No Git staging or commit is authorized here.

## Verification and qualifications

Private execution reports and exact results are under `workspace/rag-implementation/v1/m5-chroma-v1/`. The design report precedes implementation; final exit report distinguishes fresh gates from historical results. The 16-document pilot, full index, exact float32 association, fresh-process restart, deterministic logical reconstruction, repeat build, corruption and authorization controls are separate checks. New M5 suites live outside the unchanged H1 test inventory and run separately:

```sh
uv run --locked --offline --project tools/indexing pytest tools/indexing/tests/test_m5_index.py
uv run --locked --offline --project apps/ingestion_dashboard pytest tools/indexing/tests/test_dashboard_panel.py
```

Chroma emits upstream `legacy embedding function config` deprecation warnings even with the explicitly disabled function. They are recorded rather than suppressed; any future upgrade requires a new isolated qualification and index version. Declared dependency license metadata and license-file hashes are inventoried privately; they do not resolve project/corpus distribution rights or constitute legal clearance. All eight broad deferred findings retain evidence-based scope; avoiding historical behavior is not permanent historical remediation.

The initial M5 development candidate used schema 1.0. A disposable negative control exposed Python boolean/integer metadata equality; schema 1.1 compares canonical serialized metadata types and adds a regression. Its opt-in selector above supersedes only that development candidate. Original development data, reports and source snapshots remain available for separate-root replay; no accepted M0–M4 release changed.
