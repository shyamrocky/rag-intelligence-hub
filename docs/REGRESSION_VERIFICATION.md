# Regression verification

**Forward status — October 25, 2026:** H1–H4 are owner accepted. This contract and its original coordinator remain unchanged; the coordinator artifact gate pins the accepted pre-migration selection. For current durable end-to-end closure, run it together with the existing explicit durable verifier as described in [current verification commands](current-operations.md#regression-and-end-to-end-verification). H5 requires separate acceptance; M4/M5 boundaries remain unchanged.

H1 adds explicit **fast**, **focused** and **full** tiers to the existing coordinator. This is a verification tool, not a QA/admission authority. It preserves the accepted selectors, current 553-unit / 992-chunk / 992-vector stack and historical replay. H1 engineering results require owner acceptance before H2/H3. M4 acceptance remains pending; M5 is not authorized.

Run from the repository root with all four existing locked environments and required private evidence present. These commands check locks offline; they do not sync environments, download packages/models or regenerate embeddings. Each output directory must be new and beneath gitignored `workspace/`.

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked python tools/regression/run.py --tier fast --output workspace/regression-verification/fast-001
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked python tools/regression/run.py --tier focused --output workspace/regression-verification/focused-001
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked python tools/regression/run.py --tier full --output workspace/regression-verification/full-001
```

The writable cache setting handles installations where sandbox permissions prevent access to the user's default uv cache. It does not change project dependencies or the user's home directory. Omitted `--tier` defaults to full; a legacy `--job` selection means focused. Custom jobs cannot be labeled full or fast. Repeated job selections fail.

## Tiers and environments

| Tier | Scope | Meaning of success |
|---|---|---|
| fast | Four actual interpreter/package/source-origin probes; four offline locks; collection of all supported test trees; current artifact integrity, token/vector/lineage bindings and one live complete parent | Preflight only; zero test assertions executed, not full regression |
| focused | Same preflight and full test inventory, selected component jobs; default is the coordinator controls | Selected scope passed; omitted tests listed, never full regression |
| full | Same preflight, all current/historical/dashboard/chunking/M4 jobs, full current artifact reader, lint and smoke | Every discovered supported test executed successfully, with explicit overlap/deselection accounting |

Fast is an integrity preflight, not a subsecond health ping: it loads native publications and hashes existing model/artifact assets. Full opens all 992 chunks through their live parent evidence; this and real corpus regression tests are deliberately more expensive. Neither tier evaluates retrieval quality.

| Job | Locked environment | Scope |
|---|---|---|
| `current` | root `.venv` | Root tests except the two historical and eleven UI tests explicitly partitioned by the existing plugin |
| `historical` | root; archived child process | Original 37-component foundation integrity and byte-identical 195-review replay |
| `dashboard` | `apps/ingestion_dashboard/.venv` | Both existing dashboard test modules, including actual Streamlit AppTest controls |
| `chunking` | `tools/chunking/.venv` | All six existing M2/M3 test modules, including all 232 baseline cases |
| `m4` | `tools/embeddings/.venv` | Embedding-input tests and existing local embedding controls |
| `coordinator` | root | Focused H1 controls; also included once by the full current job |
| `m4-artifact-reader` | embedding | Explicit current stack; no embedding model construction or inference |
| `lint`, `smoke` | root | Ruff and scaffold smoke, not quality evaluation |

For example, `--tier focused --job chunking` selects the chunking job and current artifact preflight. Multiple distinct `--job` arguments are permitted only for focused execution. Full executes memory-heavy jobs serially.

The tiny existing M4 tests may instantiate the already acquired pinned model for owned offline controls. They do not re-encode the 992 corpus chunks, generate queries or publish artifacts. They run only when explicitly selecting the M4 job or the full tier. The artifact gate never performs inference.

## Test accounting and failures

The inventory is collected using the proper locked interpreter for each supported tree: `tests/`, `tools/chunking/tests/`, `tools/embeddings/tests/`. Frozen historical experimental suites outside these trees are not silently claimed as executed. Collection or missing private evidence fails closed; it is not a green reduced suite. Minimum baseline coverage is 1,024 root, 232 chunking and 15 embedding tests; added controls increase actual counts.

Each receipt distinguishes collected, selected, executed, call-executed, deselected, passed, failed, errored and skipped tests. Setup/teardown reports are retained. Marker-based job partitions produce explicit deselections; the full gate requires the union of executed IDs to equal the entire collected inventory. Any skip, missing outcome, failure, collection error or omitted required job prevents full success. Repeated IDs within a job and duplicate result records fail accounting. Deliberate cross-job repeats are reported separately from unique tests.

Reports contain `RUN.json`, `RESULTS.json`, `INVENTORY.json`, `SUMMARY.json`, command logs, per-job selection receipts, JUnit XML and artifact reports. `PASS_FAST` and `PASS_FOCUSED` cannot be interpreted as `PASS_FULL`. Missing evidence or failed preflight produces `BLOCKED_OR_FAILED` with observed counts and unrun commands. Verification implementation and test-source hashes are captured before execution and must remain unchanged through the run. Old output directories and their summaries remain historical; they are never refreshed to a new schema.

Inherited pytest filters/plugins and alternate test identities are cleared. Third-party pytest plugin autoload is disabled; the explicit project plugin remains selected. User-site imports and telemetry/tracing are disabled; Hugging Face/Transformers and uv run offline. Runtime probes check actual `sys.prefix`, Python 3.12, editable source origin and declared installed versions against each existing lock. The embedding reader also checks all nine pinned model-runtime versions.

## Current artifact gate

The same existing `tools/regression/check_m4_artifacts.py` now verifies the exact explicit unified, M3 and M4 selection fingerprints. It invokes unchanged public loaders and native source/QA validators. It checks:

- 553 units, 3,040 Sections, 3,727 membership relationships; 2,572 admitted / 110 excluded / 358 HOLD.
- Exact 992 Chunk IDs, input hashes, pinned tokenizer sequences, row identities and vector hashes.
- Chunk → Unit → Section roles, publication/membership/citation bindings and token budgets.
- No memberships/chunks for HOLD or excluded Sections.
- In full depth, all 992 live complete-parent/input bindings across all 553 units, all four protected Markdown parents, C10 context/QA observations and the exact frozen PDF expiration-warning scopes.

Qualifications are checked through authoritative native parent rehydration. The verification reports are not detached authorizations and cannot replace supported loaders. Historical defaults remain unchanged; the dashboard's 550-unit/893-chunk view is tested as historical, not silently switched to current.

## Historical and ingestion boundaries

The test plugin still verifies only its explicitly test-only QA identity and foundation:

- `workspace/pdf-residual-recovery/v1/qa-regression-identity.json`
- `workspace/pdf-residual-recovery/v1/regression-release/`

Its process-local `pipeline.HOME` override belongs only to tests. It does not repair the stale production default or qualify a production ingestion foundation. The existing two-module clock fixture is reused and restored; live expiration warnings remain live.

Historical replay retains the exact archived six-module validator (`c3509d64beca21a2d501d72ea5376a9612fc91ecb15900d923c66bb7525e8369`), unchanged original assertions, 195 reviews and original receipts. Replay writes only disposable copied fixtures. The current validator continues rejecting incompatible historical review bindings. No new human approval or source readiness follows.

The unconfigured bare root pytest command remains a documented mixed historical/environment scope, not the full supported gate. Use the coordinator for current/private verification. H1 does not change source acquisition, shared QA policy, production ingestion, workspace storage, default selectors, dashboard selections or accepted M0–M4 artifacts.

## Recovery and rollback

The sealed private H0 bundle remains at `data/recovery/h0-v1/`; consult its `ROLLBACK_INSTRUCTIONS.md` and `H0_RECOVERY_EXIT_REPORT.md`. H1 working evidence and exact pre-change tool/doc copies are in `workspace/rag-implementation/v1/h1-regression-verification-v1/`. Rollback changes only the authorized verification files or restores a whole verified H0 root; do not reset/clean untracked project files or rewrite historical fingerprints. Off-device backup and cross-host portability are not claimed by H1.
