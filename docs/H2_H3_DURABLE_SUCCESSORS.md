# H2/H3 opt-in durable ingestion successors

**Forward status — October 25, 2026:** H2/H3 and H4 are now OWNER_ACCEPTED / CLOSED. The supported durable consumers and strict ingestion remain explicit opt-in paths; no global default activation occurred. H5 is authorized for operational closure only; M4 acceptance and M5 authorization remain separate. See [current operations](current-operations.md). Delivery-time acceptance labels below are retained as historical context.

Engineering candidate implemented under the owner's October 25, 2026 compatibility approval. **Owner acceptance and default cutover remain separate decisions.** Existing publications, default consumers, shared QA implementation, source observations and saved numerical vectors are preserved.

The same shared QA owner publishes the PDF successor. A new explicit composition reuses native HTML, Markdown and PDF verifiers and the existing Unified contracts. Preparation and accepted chunkers replay the existing source boundaries; a vector reuse producer verifies a bijection against live original and new parents. No downstream retrieval or new admission authority is introduced.

## Explicit read-only selection

From the repository root, use the existing locked embedding environment when loading vector artifacts:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline --project tools/embeddings python
```

```python
from pathlib import Path
from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.embedding_artifacts import EmbeddingArtifacts

root = Path.cwd()
corpus = load_durable_corpus(root)
catalog = QualifiedChunkCatalog(
    root, corpus, selector="config/retrieval-chunks-m3-durable-v1.json"
)
vectors = EmbeddingArtifacts(
    root, catalog, selector="config/embedding-artifacts-m4-durable-v1.json"
)
```

The corpus contains 553 verified consumer units and 3,040 canonical Sections; the catalog and vector inventory contain 992 rows. There are 3,727 Section-to-Unit membership links. Effective admissions remain 2,572 ADMITTED, 110 EXCLUDED and 358 HOLD.

`vectors.get_vector(chunk_id)` returns numbers and bindings only. Authorized content requires `vectors.open_bound_chunk(chunk_id)`, including its complete verified parent, qualifications, required context, citations and publication identity. Raw normalized records, working reports and reconciliation maps are not alternative evidence gateways. Old IDs are not aliases for changed publication-qualified identities.

Five opt-in selectors are supplied:

- `config/pdf-durable-admission-publication-v1.json`
- `config/unified-durable-selection-v1.json`
- `config/retrieval-chunks-m3-durable-v1.json`
- `config/embedding-artifacts-m4-durable-v1.json`
- `config/ingestion-strict-v1.json`

No active-publication registry or latest-version fallback is added. Original selectors and loaders remain available and unchanged.

## Durable storage and lineage

Fifty source/QA/structure evidence roles are retained in durable project storage, with two existing witnesses reused. Thirty-eight build, working, synthetic-test and bulk-inventory roles become archive-only for the new runtime. All originals remain at their original locations for historical replay. Exact source-to-destination hashes are in `data/validation/provenance/durable-consumer-v1/EVIDENCE_MIGRATION.json`.

New PDF QA publications are under `data/validation/pdf/durable-consumer-v1/`. The explicit composition descriptor is `data/validation/provenance/durable-consumer-v1/BINDINGS.json`. Preparation, M1/M2 verification and consolidated chunk artifacts are under `data/chunking/m3-durable-v1/`. Unit and Chunk reconciliation maps are bound in its manifest. The numerical-reuse proof and new records/inputs are under `data/embeddings/m4-durable-v1/`; its manifest references the exact original saved matrix rather than duplicating or recalculating it.

All 553 logical scopes and 992 source intervals are preserved. Publication-qualified handles change for 312 PDF parents. There are 471 changed Chunk IDs and matching changed Embedding IDs, with 521 retained. The tokenizer/model/encoding configuration and source/token/vector bytes do not change. The 384-token default and four approved selective 512-token exceptions remain in force.

Source coverage is unchanged, with 89 heading-context characters accounted separately and zero unresolved chunk intervals. Coverage remains scoped to already authorized source display, not all PDF content. The catalog retains predecessor-generation inspection metrics; the current migration is recorded in `summary.durable_packaging` and the bound ID maps. Do not interpret predecessor-generation fields as current ID-change counts.

## Isolated strict ingestion

The strict image is under `releases/ingestion/strict-v1/root/`, reproducibly derived from canonical source and `tools/ingestion/successors/strict-v1/explicit-release.patch`. Only `shared/pipeline.py` changes application semantics. Its actual `verify_foundation` and `execute` APIs reject omitted/empty release selection, and `execute` also requires explicit output. Assigning historical `HOME` cannot restore fallback.

The launcher verifies the selected build, actual foundation digest, image fingerprints and worker fingerprint before invoking a fresh root-consistent process. The worker uses a fresh bytecode-cache prefix and source-only package import, avoiding stale image bytecode. Legacy current-root ingestion and dashboard defaults are unchanged; they are not the new strict route.

An explicit C06 execution example, for the qualified candidate scope:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline python tools/ingestion/run.py \
  --root . \
  --selector config/ingestion-strict-v1.json \
  --source-manifest releases/ingestion/strict-v1/root/data/ingestion/strict-v1/sources/C06.json \
  --release releases/ingestion/strict-v1/root/data/ingestion/strict-v1 \
  --output releases/ingestion/strict-v1/root/data/ingestion/strict-v1/explicit-run
```

An execution completes without granting content admission or source readiness. Real four-PDF qualification preserves original extracted observations; new execution QA remains partial/HOLD. Mathematical incompleteness stays FAIL/HOLD, including the reviewed C06 case. A failed execution emits stage evidence and a nonzero launcher exit. Unsupported formats do not fall back to another adapter.

The image retains the existing structural evidence and frozen PDF input copies needed for isolated qualification. Its build recipe requires the exact private frozen classification inputs recorded in the private build manifest; these remain recoverable through H0/originals. This is a build-time reconstruction requirement, not an active workspace dependency of the selected runtime. Virtual environments are not assumed portable.

## Verification and boundaries

The private H2/H3 exit report records exact selector/manifest hashes, complete file inventory, actual test receipts, deterministic rebuild, original-data preservation and rollback. Mandatory context and warning stripping, source/publication/implementation corruption, stale IDs and incompatible vector/catalog pairing must fail closed.

The host rejected nested kernel sandbox creation during this work. Denied-workspace/original-evidence checks therefore use Python audit hooks with positive denial controls on the actual workflows. They establish the tested trusted application paths; they are not claimed as a new kernel security boundary or cross-host qualification.

H0 remains a sealed pre-H1 recovery baseline. Keep the accepted H1 delta and new H2/H3 artifacts separately; do not overwrite H0. Rollback uses the unchanged original root and explicit original selectors in a fresh process. Invalidated integrity leases must be reconstructed through verified loaders.

No default activation, original-file deletion, H4/H5, M5, corpus embedding regeneration, retrieval-quality claim or Git operation is part of this checkpoint.
