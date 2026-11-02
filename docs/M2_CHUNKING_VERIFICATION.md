# M2 verification and review handoff

M0/M1 are project-owner accepted. M2 is **implemented and technically verified, pending owner review**. No M3 catalog, embedding, index or retrieval implementation is included. The [implementation contract](STRUCTURE_AWARE_CHUNKING.md) describes the components, tokenizer pins, source/context separation and replay command.

## Selected final candidate

Implementation: `m2-structure-aware-1.1`. Private output: `data/chunking/m2-c01-v3/`. Earlier v1/v2 outputs are preserved development evidence and are not the final review baseline.

| Measurement | 256 total tokens | 384 total tokens |
|---|---:|---:|
| C01 verified units accounted | 61 | 61 |
| Pilot pieces | 114 | 88 |
| Units kept intact | 48 | 56 |
| Maximum actual input tokens | 255 | 382 |
| Source display coverage | 65,872 / 65,872 | 65,872 / 65,872 |
| Unresolved budget intervals | 0 | 0 |
| Bibliography pieces / complete entries | 35 / 68 | 22 / 68 |
| Whole tables / math references / captions | 4 / 2 / 10 | 4 / 2 / 10 |

Counts include actual BGE tokenization, the explicit source-heading prefix and two special tokens. All 277 unique admitted C01 Sections remain associated through their existing roles; 266 are body-associated and 11 context-only. Display coverage sums the 61 authorized unit fields and retains existing cross-unit sharing; it is not a count of unique PDF characters. No added within-unit chunk overlap occurs. All 61 source-content/context/qualification/membership/citation/publication records match M1 exactly; only clock-derived warning bindings refresh. No excluded/HOLD text was introduced as source evidence. The tokenizer's configured ceiling is512, not384; no model weights or embedding inference were needed.

The detailed unit/Section accounting, distributions, boundary decisions, issues and recommendations are in `workspace/rag-implementation/v1/m2/C01_CHUNKING_COMPARISON_REPORT.md`. The self-contained preview is `data/chunking/m2-c01-v3/C01_CHUNKING_REVIEW.html`.

## Actual test evidence

There are **1,049 unique passing controls across the final verification runs**:944 existing ingestion/QA/consumer/unified controls,25 M0/M1 controls,36 dashboard controls and44 M2 controls. Test node IDs and overlap accounting are recorded in `workspace/rag-implementation/v1/m2/TEST_ACCOUNTING.json`.

| Run | Actual result |
|---|---|
| Final M2 suite, real current clock | 44 passed in 122.88 seconds |
| Broad existing regressions, first run | 943 passed,1 expired-start fixture failure,1 inherited deselection in 569.30 seconds |
| M0/M1 first run | 24 passed,1 same expired-start fixture failure in 247.26 seconds |
| Targeted clock-stable retest of unchanged unified+M0/M1 modules | 94 passed in 454.58 seconds |
| Dashboard regressions | 36 passed in 83.90 seconds |
| Root Ruff / scaffold smoke | Passed; smoke is not RAG quality evaluation |
| New tooling lock consistency | Passed offline |
| Fresh-process replay | All 8 deterministic final files byte-identical |
| Original baseline fingerprints | All 901 unchanged |

The initial failures were historical test-fixture clock assumptions: a snapshot already loaded asEXPIRED cannot be changed back toVALID by rewinding only its display clock. The unchanged reader is correctly monotonic. The new test-only `tools/chunking/m2_clock_regression_plugin.py` seeds a pre-expiration initial clock **only for those two frozen regression modules**, before their fixtures load. All original assertions, files and gates remain unchanged. The new M2 suite does not load that plugin and explicitly verifies actual currentEXPIRED content remains readable with its original warning and restrictions.

The accepted one obsolete predecessor-byte assertion remains deselected; two legacy private acquisition/reparse/admission test files remain uncollected. These exclusions were not added for M2. Passing development/retest controls overlap and are not summed. Existing PyMuPDF binding deprecation warnings remain. No final M2 failures or skips are reported.

A heading-only packing defect found in development was corrected within the new chunker. Leading source members now remain with following prose when naive packing would isolate them. Frozen expectations and source annotations were not changed to force acceptance. Earlier development failures and outputs are retained. One development runner also correctly aborted when formatting changed its implementation fingerprint during execution; the final candidate's loaded component bindings remain stable.

## Checks exercised

- Every original approved display character is covered once by a piece or an explicit unresolved interval. Actual C01 has no unresolved intervals; owned negative controls verify oversized atomic elements, oversized references and exhausted prefix budgets are retained as unresolved.
- Exact whole-string token checks include headings/special tokens; counting more than512 tokens does not silently truncate.
- All 68 bibliography boundaries agree with the pre-implementation source-marker record; numbered markers must be consecutive and align with hash-verified source-member starts.
- Four tables, two existing owner mathematical transcriptions and ten captions remain whole. No new table/math/figure interpretation is claimed.
- Original punctuation, numeric signs, identifiers, Unicode and whitespace remain exact source slices. Tokenizer decoding is never used to reconstruct text.
- Source content, required context, QA observations and qualifications remain distinct. Forged/rehashed text, stripped context/warnings, changed citations and wrong publication/Unit identities fail validation through the original gateway.
- Raw, HOLD, excluded and audit-only inputs have no fallback path. Context-only Sections do not gain independent evidence access.
- Source and publication integrity leases remain effective. The original authorization window is unchanged; expiration remains a warning rather than a content-integrity failure.

## Remaining limitations

The 256 configuration splits the original abstract into two exact approved display slices, with parent-level raw citations rather than newly invented partial raw offsets. The 384 configuration keeps it intact. Whole typed projections also legitimately use parent citation precision. Exact display coverage does not imply exact partial raw mapping everywhere.

Both configurations produce two BGE unknown tokens around author-affiliation stars in one front-matter/citation unit. Original text is retained. These are separate chunking diagnostics, not publisher claims, new parser failures or QA reclassifications. `REVIEW_CASES.json` records those cases plus the two256 abstract slices. No retrieval-quality winner is established; no new independent human approval was fabricated.

All source-scoped qualifications remain mandatory. Short child pieces still require the complete approved parent unit for evidence reconstruction; M2 does not declare them independently answerable. Large bibliography-parent reconstruction/context-budget behavior belongs to later milestones.

## Reproduction and resource evidence

Final manifest SHA-256:
`2d250b35727cbcd10e92573cb435a84d6dc777837e32949380867f9e555fa6c7`.

Final corpus load25.63 seconds; complete pilot131.32 seconds; peak RSS 2,184,232,960 bytes (~2.03 GiB). Separate replay load26.58 seconds; total93.64 seconds; peak RSS 2,096,087,040 bytes (~1.95 GiB). Filesystem caches and concurrent checks affect these measurements; they are not isolated cold benchmarks or retrieval latency.

Execution blocked socket connections and recorded zero attempts. No torch/Transformers/Sentence Transformers model module was loaded. The seven pinned tooling assets total1,038,973 bytes; the separate environment is about145 MiB. One-time authorized tokenizer/dependency acquisition is distinct from offline replay. The original root/dashboard lockfiles and environments are unchanged.

The preview has122 unit/configuration panels, no scripts and no external assets. Structural/self-contained checks passed. No visual browser verification or screenshots are claimed.

Commands used, from the repository root:

```sh
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false \
  uv run --project tools/chunking --locked pytest -q tools/chunking/tests/test_structure_chunking.py

PYTHONPATH=workspace/unified-consumption/v1 \
RAG_TEST_QA_RELEASE=workspace/pdf-residual-recovery/v1/qa-regression-identity.json \
  uv run --locked pytest -q -p regression_plugin \
  --ignore=tests/test_local_corpus.py --ignore=tests/test_validation_local.py \
  --ignore=tests/test_ingestion_dashboard.py --ignore=tests/test_chunk_preparation.py \
  -k 'not test_shared_guards_policy_and_contracts_are_reused'

PYTHONPATH=workspace/unified-consumption/v1:tools/chunking \
RAG_TEST_QA_RELEASE=workspace/pdf-residual-recovery/v1/qa-regression-identity.json \
  uv run --locked pytest -q -p regression_plugin -p m2_clock_regression_plugin \
  tests/test_unified_consumption.py tests/test_chunk_preparation.py

uv run --project apps/ingestion_dashboard --locked pytest -q tests/test_ingestion_dashboard.py
uv run --locked ruff check .
uv run --locked rag-hub smoke
uv lock --project tools/chunking --check --offline

HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false \
  uv run --project tools/chunking --locked python tools/chunking/run_c01.py
```

`UV_CACHE_DIR=/private/tmp/rag-uv-cache` was set for these executions. For a separate replay, add a new `--output` path; differing output cannot overwrite an existing candidate.

## Preservation and next decision

No existing implementation, source, normalized record, QA publication, eligibility decision, accepted unified contract, dashboard or M0/M1 artifact changed. The 901-file baseline and original Git HEAD/empty index match. Data, tokenizer assets and workspace evidence remain ignored; no staging, commit, merge or push occurred.

Review/accept M2 and separately authorize M3 if satisfied. The 384 configuration is the simpler proposed next catalog candidate because it produces88 pieces and fewer split/lineage-review cases; retain256 for future comparison. This recommendation concerns engineering simplicity, not measured retrieval accuracy. The single M0–M1 1 tracker remains authoritative for progress. All later milestones are unapproved.
