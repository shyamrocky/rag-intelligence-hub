# Pre-M6 local operational preflight

This additive inspection tool checks the owner-accepted M0–M5 durable composition.
It does not select a global default, publish a release, admit evidence, or authorize M6.
Native publication readers and the shared QA authority retain their existing responsibilities.

Run from the repository root, with the five existing locked environments installed:

```sh
UV_CACHE_DIR=/private/tmp/rag-m5-uv-cache PYTHONDONTWRITEBYTECODE=1 uv run --locked --offline --no-sync python tools/operations/check_selection.py --root . --profile config/operations-durable-m0-m5-v1.json --profile-sha256 c9c28c7d5b35b965c7044d3817e3063b1fe4b0d8705fcb73344527e1d004e4a4
```

The profile pins the existing PDF QA, Unified, M3, M4, M5 and strict-ingestion selectors;
all five dependency manifests/locks; and the existing verification entrypoints. It is an
inspection configuration, not a replacement publication or an admission ledger.
Missing, altered, foreign, mixed-release or unsupported-runtime inputs fail without fallback.
The accepted M5 export supplies its original hash-bound private dependency inventory.

The tool checks the existing macOS arm64 / Python 3.12.15 / uv 0.13.0 installation.
It inspects all installed distribution versions, editable source origins in four environments,
and isolation of the fifth numerical-store environment. Five offline lock checks do not install
or sync packages. The tool delegates to the original strict-selection verifier, durable
sample verifier and complete 992-record M5 inspector. The sample verifies all saved
input/token/vector bindings, but opens only one live complete parent. A PASS is not a
permanent authorization lease or a claim that every parent was freshly opened.

Original APIs, historical defaults and accepted runtime locks remain unchanged. New ingestion
must use the explicit strict runtime described in [current operations](current-operations.md).
The dashboard still has four inspection modes; select the durable mode explicitly. Never use
the legacy root ingestion HOME fallback for new work.

## Focused controls

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline --no-sync pytest -q tools/operations/tests
```

The resource harness is optional, explicit and macOS-specific. It runs two live Streamlit
AppTest sessions sharing the actual verified cache, interleaves their UI interactions,
opens a native qualified parent, and runs an independent M5 read loop concurrently.
It performs no query embedding, semantic search, model inference, publication or index build.
It writes only new private report files. Supply a new empty output directory beneath workspace:

```sh
mkdir -p workspace/operations-resource/new-run
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 apps/ingestion_dashboard/.venv/bin/python tools/operations/profile_local.py --root . --output workspace/operations-resource/new-run --worker dashboard
```

Do not run it alongside other heavy qualification jobs when collecting a local baseline.
Sampling reports self and descendant RSS, including transient inspector workers; RSS sums
can count shared pages more than once. AppTest is actual Streamlit execution, but does not
qualify browser transport, simultaneous browser requests, arbitrary users or long-running
production service behavior. A short coexistence run is not a memory-leak or capacity proof.
The first complete-parent display can be substantially slower than warm navigation.

## Recovery and rollback boundaries

A copied virtual environment is not portable. Preserve the private corpus, QA publications,
model/tokenizer assets, saved vectors, index, strict image, historical witnesses, exact source
and all five locked reconstruction inputs separately from Git. A locally readable iCloud copy
does not establish independent off-device recoverability or a current-state restore.

Rollback of this package requires no content regeneration: stop using the optional preflight
and resource harness, and continue using the unchanged explicit accepted native readers.
Retain all reports and original selectors. Do not reset/clean files, rewrite fingerprints,
replace publications or rebuild vectors to conceal a failure.

Private verification and proposed source-control/recovery inventories are in
`workspace/rag-implementation/v1/pre-m6-remediation-v1/`. They require project-owner review;
no source staging/commit, private transfer/restore or M6 execution follows automatically.
