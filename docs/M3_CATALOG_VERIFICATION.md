# M3 verification and local handoff

M3 is implemented and technically verified, pending project-owner acceptance. M2 is owner-accepted for C01. Both accepted 256/384 M2 outputs remain unchanged; **384 total BGE tokens is provisional, not a retrieval-quality winner**. No embeddings, vector/lexical indexes, retrieval or generation were implemented.

## Actual results

| Format | Documents | Accounted verified units | Units with chunks | Derived chunks |
|---|---:|---:|---:|---:|
| HTML | 11 | 155 | 154 | 317 |
| Markdown | 1 | 86 | 82 | 204 |
| PDF | 4 | 309 | 305 | 372 |
| Total | 16 | 550 | 541 | 893 |

C01 retains **88 chunks / 61 units / 277 unique admitted Sections**, matching the accepted M2 384 source partitions. Its 65,872 approved display codepoints sum per-unit fields, including existing shared-source occurrences. No additional within-unit overlap is introduced. All 68 bibliography entries remain entry-aligned; short tables, mathematical references and captions retain their accepted boundaries.

Across the corpus, 524 units are fully chunked, 17 partially blocked, five blocked and four protected Markdown units explicitly non-indexable. All 550 units reconcile. Their 2,572 admitted parent Sections and 3,727 published membership links retain their original roles. The full 3,040-Section catalog, 110 exclusions and 358 QA HOLD remain unchanged.

**Coverage is complete accounting, not complete chunk emission:** 382,185 of 476,769 authorized indexable display characters were emitted (80.16%); 94,584 remain in explicit unresolved intervals. This denominator excludes four native warning-bearing projections that expose no independent indexable field under M0. Shared source and repeated context are not unique-source coverage.

The 22 exception fields comprise:

- 13 oversized atomic elements: ten C16 code blocks, one C08 table, one C02 table and one C06 code example.
- Six C13 source heading fields that are not independent chunks; their native membership roles remain unchanged.
- One C07 unknown native structure.
- Two C02/C14 bibliographies without verified reference-entry boundary witnesses.

These are **chunking exceptions, not new QA HOLD or parsing-failure decisions**. All complete parent units remain available under their existing gateway restrictions. Nothing was silently truncated or dropped. No upstream contract or new admission authority was introduced.

There are 192 chunks with hash-verified original-source slices and 701 with exact authorized display intervals plus parent citations. No finer raw offsets are guessed. Five tokenizer unknown occurrences retain original characters and diagnostics, including C01's affiliation stars. The preserved M2 256 output still contains its explicitly documented partial-raw-lineage abstract slices; the 384 catalog keeps that abstract intact.

## Selected durable artifacts

- C01: `data/chunking/m3-c01-v2/`, explicitly selected by `config/retrieval-chunks-c01-v2.json`.
- Full corpus: `data/chunking/m3-corpus-v2/`, explicitly selected by `config/retrieval-chunks-v2.json`.
- Each contains `chunks.jsonl`, `unit-outcomes.json`, `COVERAGE.json`, and `manifest.json`.
- All-format preparation evidence: `data/preparation/m3-full-v1/prepared-inputs.jsonl`.
- Detailed reports, exact hashes, exception IDs, tests and inventories: `workspace/rag-implementation/v1/m3/`.

The selected full manifest SHA-256 is `d3aec5237a145e7b5f033f385aea5428edbda98c3cd7f7cde3cc25d5ae81a211`.

All three payloads reproduce byte-for-byte in independent processes. A relocated replay manifest intentionally contains different output path references; its configuration, component bindings, source scope and payload hashes match. IDs are stable within a pinned publication/configuration. C01-only and full-corpus configurations have different component fingerprints, hence different version-qualified IDs, while their C01 source partitions and lineage match exactly.

Earlier v1 M3 artifacts are retained development evidence. The initial full inspector exceeded its 180-second AppTest cold-load limit because it repeated Section lease checks per membership. The selected v2 constructor uses checked metadata pages and authoritative unit membership queries; live source and catalog leases remain enforced. Exact old component copies match the v1 fingerprints. No frozen M2 or ingestion artifact was overwritten.

## Verification actually executed

**1,123 unique controls passed:** 969 upstream + 114 chunking/catalog (including 44 unchanged M2 controls) + 40 Streamlit/dashboard. Checkpoint and development runs are overlapping evidence, not extra passing tests.

Tests check all 550 source inputs, exact interval partitions, token budgets, valid parents and lineage; live source views across all 16 documents; C10 RRF context/observations; protected Markdown restrictions; expired-but-readable PDF warnings; bidirectional memberships; forged source/publication/parent identities; duplicated/orphan IDs; out-of-range spans; post-load file mutation; context/qualification stripping; unknown IDs; and real Streamlit navigation. Synthetic kernel controls are explicitly machine-authored engineering cases, not new human acceptance evidence.

Root lint, scaffold smoke and root/tooling/dashboard lock checks passed. The scaffold smoke remains a scaffold check, not RAG quality evaluation. Existing PyMuPDF deprecation warnings remain. There were no new final skips or failures.

The upstream command retains the established exclusion of two legacy private acquisition/reparse/admission test files and one obsolete predecessor-byte assertion. Its existing test-only clock plugin seeds two historical expiry-crossing fixtures before expiration. Production clocks, publication windows and test assertions are unchanged. Current M3 tests run without that plugin and verify real expired-but-readable content with its warning.

Exactly 1,008 captured upstream/M2 fingerprints remained unchanged. The sole authorized existing-file change is additive navigation in `dashboard_ui.py`; its before-copy matches the captured original SHA-256. QA/source/publication/unified/preparation/chunker contracts and dependency locks remain unchanged. No staging, commit, merge or push occurred.

A direct listening-server smoke attempt was sandbox-blocked at `socket.bind` (`PermissionError`); no live HTTP/browser verification or screenshots are claimed. The actual Streamlit AppTest rendering/navigation suite passed. Run the command below in the local terminal for browser inspection.

## Reader performance

One measured process: accepted corpus load 27.18 s; full chunk-index construction 21.38 s; warm metadata median 0.040 s. Opening and validating complete C01/C04/C10 views took 1.51–1.57 s. Peak process RSS was about 1.81 GiB. The catalog and original verified corpus are cached together for UI reuse; detached evidence is not cached as authorization. Filesystem cache and concurrent verification affect these local timings. They are not retrieval/model benchmarks.

## Run and inspect

Use the [catalog contract and API](RETRIEVAL_CHUNK_CATALOG.md). From the repository root:

```sh
uv run --project apps/ingestion_dashboard --locked streamlit run apps/ingestion_dashboard/app.py
```

Choose **Chunk Inspector**. Select the explicit full-corpus or C01 catalog, filter by document/Unit/Section, then open a Chunk ID. Parent and Section links navigate both ways. The slice is inspection-only; its unchanged verified parent supplies mandatory context, warnings, qualifications and citations. The existing ingestion views remain available. No chunking or QA work executes on widget interactions.

Offline rebuild/replay, with private frozen corpus, tokenizer assets and passed Checkpoint A evidence present:

```sh
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false \
  uv run --project tools/chunking --locked python tools/chunking/build_catalog.py \
  --document C01 --output data/chunking/m3-c01-v2
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false \
  uv run --project tools/chunking --locked python tools/chunking/build_corpus_catalog.py
```

Existing identical outputs are accepted; differing outputs fail rather than overwrite. For a separate replay use `--output workspace/rag-implementation/v1/m3/another-replay`. No downloads occur.

Focused checks:

```sh
uv run --project tools/chunking --locked pytest -q tools/chunking/tests/test_chunk_catalog.py tools/chunking/tests/test_corpus_chunking.py tools/chunking/tests/test_structure_chunking.py
uv run --project apps/ingestion_dashboard --locked pytest -q tests/test_ingestion_dashboard.py tests/test_chunk_dashboard.py
uv run --locked ruff check .
uv run --locked rag-hub smoke
```

The exact release-aware upstream regression command and collected node IDs are retained in the private workstream's logs and `TEST_ACCOUNTING.json`. Use `UV_CACHE_DIR=/private/tmp/rag-uv-cache` if the default cache is restricted.

Review M3's source coverage, lineage precision and explicit exceptions before choosing the next milestone. M4 and any further remediation require separate owner authorization.
