> **M8 delivery — October 26, 2026:** M7 is OWNER_ACCEPTED / CLOSED. M8 reconstruction is technically verified with1490 fresh unique passing tests; result acceptance is PENDING. Use the explicit M8 configuration and [evidence API guide](M8_VERIFIED_EVIDENCE.md). No M9–M11 authorization or global default change. Earlier checkpoints below retain their historical status.

> **M8 checkpoint — October 25, 2026:** M7 is now OWNER_ACCEPTED / CLOSED. M8 verified evidence reconstruction is authorized and under verification; its results require separate acceptance. See [M8 source/context and budget contract](M8_VERIFIED_EVIDENCE.md). M9–M11 remain unauthorized. Earlier status entries are historical.

## M7 retrieval — current checkpoint

M0–M6 are OWNER_ACCEPTED / CLOSED. M7 three-mode local candidate retrieval is technically verified; results await owner acceptance. Use [M7 retrieval](M7_HYBRID_RETRIEVAL.md) for the explicit selector, API and Streamlit panel. All six accepted runtime locks, QA publications, 553 parents, 992 chunks/vectors and both original indexes remain unchanged. M8–M11, Git operations and recovery transfers remain unauthorized. Earlier checkpoint labels below retain their historical context.

## M6 bounded implementation — current checkpoint

M0–M5 and Pre-M6 are project-owner accepted. M6 local BM25 is now explicitly authorized and undergoing technical verification; result acceptance remains pending. The five accepted environments and operational profile remain unchanged. An additional isolated `tools/lexical` environment and opt-in keyword selector are documented in [M6 BM25](M6_BM25_INDEX.md). No new default, QA authority, vector query, hybrid retrieval or generation is introduced. M7 remains unauthorized. Earlier status statements below preserve their checkpoint context.

# Current local operations

**Current owner decision — October 25, 2026:** M0–M5 and H0–H5 are OWNER_ACCEPTED / CLOSED. M5 uses explicit `config/vector-index-m5-v1-1.json` (`m5-chroma-1.1`); its fifth isolated runtime is `tools/indexing/`. SH-09 is resolved by the verified local checkpoint. The current M5 source delta is not committed. All eight broad deferred findings remain deferred. M6, new remediation, global-default cutover, Git actions and backup transfer/restore require separate approval. Earlier status labels below are historical checkpoints, not current authorization.

**M5 candidate update — October 25, 2026:** SH-09 is resolved by verified local checkpoint `753d6ea078968fb704f22f0bf62c57f18c964a1b`. M5.0–M5.8 are now explicitly authorized. The isolated persistent-index candidate and fifth locked runtime are documented in [M5 numerical index](M5_PERSISTENT_INDEX.md); result acceptance remains pending. Existing four environments, historical defaults and the accepted M0–M4 release identities stay unchanged. M6 and later work remain unauthorized. Earlier closure-time statements below retain their historical scope.

H0–H5 and M0–M4 are project-owner accepted and closed as of October 25, 2026 (D034). M4 acceptance covers the verified durable embedding successor and engineering integrity only; retrieval evaluation remains deferred to M9. SH-09 remains OPEN pending an authorized source-only Git checkpoint. M5 is NOT STARTED / NOT AUTHORIZED. This guide is the forward operational entrypoint. Earlier milestone reports remain historical evidence, including their delivery-time status labels.

The supported durable inspection composition has **16 documents, 3,040 canonical Sections, 553 verified consumer units, 992 chunks and 992 × 384 saved vectors**. Admissions remain 2,572 ADMITTED, 110 EXCLUDED and 358 HOLD. Source-display coverage is 99.9814% within authorized content; 89 heading-context characters remain parent-only and there are no unresolved chunking intervals. These are ingestion and artifact-integrity facts, not retrieval-quality results or whole-source fidelity certification.

## Environment and private prerequisites

Run commands from the project root with Python **3.12** (`>=3.12,<3.13`) and `uv`. H5 uses uv 0.13.0 on the existing macOS arm64 host; no minimum older uv version or other platform is qualified. Four independent locks/environments are intentional:

| Project / interpreter | Purpose |
|---|---|
| `.` / `.venv/bin/python` | Shared ingestion, native QA, unified readers, lean tests and scaffold CLI |
| `apps/ingestion_dashboard` / its `.venv/bin/python` | Streamlit inspection and AppTests |
| `tools/chunking` / its `.venv/bin/python` | Pinned tokenizer and LangChain splitters; M2/M3 tests |
| `tools/embeddings` / its `.venv/bin/python` | Numerical M4 artifact reader and pinned embedding runtime |

Use the matching environment. Root does not supply the numerical M4 dependencies; dashboard NumPy is not the qualified embedding runtime. Do not merge locks or upgrade them to fix an interpreter-selection error.

For environment construction, `uv sync --locked --offline --project <project>` requires an already populated compatible wheel/build cache. The demonstrated recovery route reconstructs the four copied environments and base Python using the private H0 controls; it does not prove a clean offline installation from an empty cache. Do not copy virtual environments and assume their shebangs, editable paths or base-interpreter symlinks are portable. Online installation, model downloads and dependency changes need separate authorization. The existing environments need no synchronization for the checks below.

Private prerequisites include the exact immutable source snapshots; native QA releases and publications; parsed/normalized source evidence; durable provenance witnesses; original and successor M0–M4 artifacts; tokenizer/model assets; and the strict ingestion image. A Git checkout alone cannot load this corpus. Keep the original historical workspace witnesses and archives for historical readers, replay and build reconstruction. The accepted durable **consumer** has zero active workspace bindings; this does not mean historical evidence or build inputs may be deleted.

All read-only commands below use existing local artifacts. Keep Hugging Face and Transformers offline when using embedding-environment tools:

```sh
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
```

If the default uv cache is inaccessible, set a separate `UV_CACHE_DIR` to an owner-writable temporary directory. No provider credentials are needed. `.env.example` is placeholders only, not an active environment loader.

## Explicit forward releases

Select the complete compatible stack; do not infer authority from filenames, timestamps or the newest file. H5 rechecks each descriptor against the accepted H2/H3 identity receipt and its target hash.

| Role | Explicit selector | Bound manifest / foundation SHA-256 |
|---|---|---|
| PDF QA | `config/pdf-durable-admission-publication-v1.json` | `9aff3640a48a47893d462c8be9a13398ffd8d642c6e1c5d7e589e94b597bf207` |
| Unified composition | `config/unified-durable-selection-v1.json` | `3270233cf14f7f9f1b2295d4db4468e7b3725ef3a50761dc247f6987f4e35cb7` |
| M3 catalog | `config/retrieval-chunks-m3-durable-v1.json` | `49e254767e3aa4f5b0724cf95ec3ab0d5787d49d74d6bacf5420dc04486dd57c` |
| M4 vectors | `config/embedding-artifacts-m4-durable-v1.json` | `9b304b4b8be9eb4aa3af22ea3d5fd2625a9b097951564077369943ee239c6ac6` |
| Strict ingestion | `config/ingestion-strict-v1.json` | Foundation `f264acf42b4fd64ab226d4fbcd51e22a852c7c6726b72a1db2f89513e84a24d6` |

The PDF QA release SHA is `d8b280b183c5ac009b6d31c656545081b537b304676cb65e742e5e7719206300`. Strict build SHA is `393da26bb944bbec8f1f6c48278fce6b6dd21e7e58c97e90d02bd754189fffe9`. No global default or active-publication registry was changed. See [durable successor contracts](H2_H3_DURABLE_SUCCESSORS.md) and [operational selection contract](OPERATIONAL_SELECTION_CONTRACT.md).

## Ingestion execution and admission

The accepted **new execution path** is `tools/ingestion/run.py` with an explicit selector, source manifest, qualified release and output. It verifies the isolated image and worker, then invokes the strict low-level APIs in a fresh process. Missing/blank release or output fails; setting historical `HOME` cannot restore fallback. Source manifest, release and output must belong to the isolated runtime, and release must equal the selected foundation.

The [previously qualified C06 execution command](H2_H3_DURABLE_SUCCESSORS.md#isolated-strict-ingestion) is the supported example. Use a new output location inside that exact foundation for an authorized execution. H5 verifies selection, preflight and negative controls without running parsers or writing ingestion results. `python tools/ingestion/run.py --help` in the locked root environment describes the arguments; help or scaffold smoke alone does not qualify ingestion.

The current-root `shared.pipeline` retains its historical `HOME` behavior for fingerprint/replay compatibility. Omitted selection there is **not** the supported new-ingestion route. The legacy three-source `rag-hub ingest` flow and historical validation commands do not implement the current 16-document admission process. Old builders and generic defaults are not substitutes for the explicit forward composition. Do not set a process-global `HOME` or use a test-only foundation in operations.

Ingestion execution produces stage evidence; it grants no content eligibility. Only shared QA (`shared.qa.assess`, `validation_reviews.make_decisions`) publishes native admission decisions. The Unified Layer validates selected published decisions; it cannot create them. The demonstrated strict execution qualification covers the four frozen PDFs; it does not establish a new HTML/Markdown acquisition or parsing workflow. Unsupported formats must fail explicitly. New strict execution may complete while QA remains partial/HOLD, including mathematical incompleteness. H5 does not run admission.

## Read the QA / Unified / M3 / M4 chain

For corpus and catalog only, use the locked chunking environment. For the complete numerical example below, enter the embedding environment:

```sh
uv run --locked --offline --project tools/embeddings python
```

```python
from pathlib import Path
from rag_hub.durable_unified_selection import load_durable_corpus
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.embedding_artifacts import EmbeddingArtifacts

root = Path.cwd()
corpus = load_durable_corpus(root)
assert corpus.catalog.get_corpus_summary()["units"] == 553
catalog = QualifiedChunkCatalog(
    root, corpus, selector="config/retrieval-chunks-m3-durable-v1.json"
)
page = catalog.list_chunks(limit=1000)
assert len(page["items"]) == 992
artifacts = EmbeddingArtifacts(
    root, catalog, selector="config/embedding-artifacts-m4-durable-v1.json"
)
assert artifacts.vectors.shape == (992, 384)
chunk_id = page["items"][0]["chunk_id"]
vector, binding = artifacts.get_vector(chunk_id)  # numerical values and identity only
view = artifacts.open_bound_chunk(chunk_id)      # live complete authorized parent
assert catalog.validate_view(view)
artifacts.check()
```

The constructor validates saved file hashes, row order/IDs, finite normalized vectors, model/configuration binding and catalog identity. The separate full read-only verifier also recomputes all 992 saved input hashes and pinned tokenizer ID hashes, and opens every live parent binding. Neither route re-encodes the corpus.

Chunk IDs and parent identities are publication-qualified. Do not alias old changed IDs to new IDs. Section relationships are many-to-many with content, projection and context roles; context-only membership is not independent indexable evidence. Default maximum is 384 BGE tokens including headings and special tokens, with four accepted selective exceptions up to 512 (actual maximum 507).

Only live verified views authorize source use. Preserve source content, required context/supporting headings, QA observations and qualifications separately. Retain citations and their recorded precision; display projection offsets do not establish exact original PDF character coordinates. Restricted C04 projections cannot expose defective source code as executable advice. Preserve C10's RRF context and QA-authored scoring observation, C06 attribution, C14 bibliography/appendix scopes, mathematical/visual limitations and warning-bearing PDF expiration. Expiration is informational; altered hashes, missing context, forged scope and stripped mandatory qualifications remain blocking. Raw Sections, input JSONL, vector records, catalogs and issue registers are not unrestricted evidence fallbacks.

## M4 model and numerical limits

Model: `BAAI/bge-small-en-v1.5`, revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. Weights SHA-256 `3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad`; model configuration `config/m4-embedding-baseline-v1.json`, SHA `2444f602babc045234dba3258e89fa4a7ea26572fa748576c6df0509dc24e3de`. Tokenizer specification SHA `03d41df1a646ed13d41bd8b485c573864da5821109e57750135bf94f0dbde577`.

Encoding uses CPU float32, CLS pooling, L2 normalization, eager attention, one thread, batch size 16 and no document instruction. Runtime pins include Sentence Transformers 5.1.2, Transformers 4.57.1, torch 2.8.0, NumPy 2.2.6, safetensors 0.6.2 and tokenizers 0.22.2; the full nine-package map is in the configuration and embedding lock. The durable release reuses the original saved numerical matrix, SHA `d67f33d067c0589516151f4e9c87b2096848bad01036b7f9a20d98d4dcc84baa`, after accepted 992-record input/token/model/qualification bijection verification.

Do not run `tools/embeddings/verify_m4.py` as a read-only health check: it performs inference/replay and writes historical output locations. Acquisition, build, rebinding and generation scripts likewise are controlled producers, not everyday validators. H5 does not run them. Same-host engineering integrity does not establish cross-platform bitwise reproducibility or retrieval quality. BGE remains provisional; model comparisons/Recall@K/MRR belong to M9. M4 engineering acceptance is recorded under D034; M5 remains separately unauthorized.

## Dashboard

```sh
uv run --locked --offline --project apps/ingestion_dashboard streamlit run apps/ingestion_dashboard/app.py
```

The existing configuration binds localhost and disables Streamlit usage statistics. Use the sidebar **Operational release**:

| Mode | Catalog units / chunks |
|---|---:|
| Historical full corpus — unchanged default | 550 / 893 |
| C01 pilot — historical compatible ingestion corpus, C01-scoped catalog | 61 / 88 |
| Accepted pre-migration full corpus | 553 / 992 |
| Durable full corpus — current operational candidate | 553 / 992 |

The durable label remains the implemented UI text even though H4 is now owner accepted. Select it explicitly. Open **Chunk Inspector**, select a document/chunk, and inspect the complete parent, qualifications and Section links. Source evidence is verified before display. HOLD/excluded Sections expose permitted inspection metadata only.

Selection switches clear lineage-bearing state and filters; caches are keyed to exact release and component bindings. One live snapshot per resource cache avoids full corpus reconstruction per interaction. **Rebuild verified snapshot** clears corpus/catalog/embedding-metadata caches and re-enters native verification. It cannot repair tampering; restore exact accepted files and reconstruct in a fresh process after an integrity failure. Do not cache detached text as permanent authorization.

H4 measured approximately 45 seconds cold load/switch, 0.23–0.25 seconds warm rerender and 1.2–1.7 seconds chunk/parent rendering, with about 2.1 GiB peak process RSS. These are reused same-host observations, not H5 browser measurements or service SLAs. Multiple sessions, concurrent indexes and production deployment are unqualified. The owner reports successful manual inspection of the durable overview/Chunk Inspector; H5 does not claim agent browser screenshots.

## Regression and end-to-end verification

Use a **new** private output directory per run:

```sh
uv run --locked --offline python tools/regression/run.py --tier fast --output workspace/regression-verification/fast-NEW
uv run --locked --offline python tools/regression/run.py --tier focused --output workspace/regression-verification/focused-NEW
uv run --locked --offline python tools/regression/run.py --tier full --output workspace/regression-verification/full-NEW
```

The unchanged H1 coordinator pins the accepted **pre-migration** 553/992/992 artifact gate. Full also executes current durable reader/dashboard tests, historical replay, all chunking tests, M4 tests, four runtime/lock probes, lint and smoke. To fully qualify the selected **durable** artifact chain, additionally run:

```sh
uv run --locked --offline --project tools/embeddings python tools/hardening/verify_successor.py --root . --depth full
```

That existing verifier checks all 992 live durable bindings and protected qualifications while denying workspace reads and network access through Python audit hooks, with a positive denial control. This is trusted-path testing, not kernel isolation. Keep its output in a new private log. It does not import a recognition model or perform numerical inference. Together these two commands cover both original and successor artifacts without altering accepted H1 code or silently retargeting its identities.

`PASS_FAST` is preflight, with no pytest assertions. `PASS_FOCUSED` covers selected jobs only. Require `PASS_FULL`, complete inventory coverage and zero failures/errors/skips for the full gate. Count unique tests separately from cross-job overlaps; explicit job deselections must be covered elsewhere in the full inventory. A bare root `pytest` is a mixed historical/optional-environment invocation, not this supported gate. Scaffold `rag-hub smoke` is not RAG-quality validation. Full M4 tests use tiny pre-existing offline model controls, not corpus-vector regeneration. See [regression contracts](REGRESSION_VERIFICATION.md).

## Recovery, rollback and source control

The private owner-controlled H0 bundle is at `data/recovery/h0-v1/`: 40,166 entries, 4,820,165,373 logical bytes. Seal SHA `41731fed23b5b589dcac4a0bd87acbba462f4e03dbd1d94c2cb0efb1c153ca6f`; base manifest SHA `c994c7f5c87fe3d7594de47574dc6f0061b58f089ef8063c2946ebd906ccb026`. Verify the adjacent receipts, then follow its `ROLLBACK_INSTRUCTIONS.md` and `RUNTIME_RECONSTRUCTION.md` in a new root. Do not edit the sealed snapshot to include later work.

H0 predates H1–H4. Retain their exact source deltas, fingerprints and private delivery inventories separately, plus H5 documentation/acceptance records. A whole-root H0 restore alone does not restore the accepted H4 application. Original and durable reader rollback means choosing the matching explicit selectors and interpreter in a fresh verified process, not mixing Unit/Chunk/Embedding identities or applying isolated file overlays. Keep H1 replay fixtures, all 88 original workspace support files, 38 archived roles and strict private build inputs for their historical/build obligations; zero current consumer dependencies is not deletion authorization.

H0's original same-host isolated restore and numerical-byte preservation are recorded evidence. H5 rehashes the seal/bound recovery evidence and accepted releases; it does not repeat the 40,166-entry restore or qualify another OS/architecture. A same-disk bundle is not independent disaster recovery. No off-device or iCloud completion is established. Before relying on an independent copy, the owner must verify encryption/access, complete locally available bytes (not cloud placeholders), transferred manifest/seal hashes and an actual isolated restore including post-H0 deltas. File-provider upload indicators alone are insufficient.

The source-only tracking proposal and its exact hashes are in the private H5 readiness report. No staging/commit/remote action is authorized. Keep `data/`, `workspace/`, archives, strict release payloads, models, vectors and recovery bundles out of Git. Retain only safe source/configuration/test/docs/locks and the empty raw-data placeholder. Reconstruction requires both approved source control **and** separately preserved private artifacts; neither substitutes for the other. No source-control checkpoint, independent backup completion or public-distribution license clearance is claimed. Never use `git clean` or `git reset --hard` to recover this mostly untracked project.

## Next owner decisions

H5 and M4 are owner accepted under D034; retain their residual debt and qualifications. Any M5 design/runtime/index implementation requires explicit authorization. Global default cutover, source-only staging/commit, independent backup transfer, public distribution and platform migration remain separate decisions. No index, search, generation or production-service readiness follows from this closure.

## Additive pre-M6 operational preflight

The owner authorized an optional, explicit local preflight and bounded resource/recovery assessment. See [Pre-M6 operations](PRE_M6_OPERATIONS.md) for the exact pinned command and limitations. This does not change any native publication, accepted runtime, historical default, or M6 authorization. Engineering verification of this package remains pending separate owner acceptance.
