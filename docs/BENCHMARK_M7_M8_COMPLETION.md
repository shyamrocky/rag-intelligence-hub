# Expanded benchmark M7/M8 completion

This bounded local experiment fills only missing RRF Top-30 / M8 128,000 BGE-token
measurements. The expanded reference benchmark, original M9 records, frozen15/22
and all existing dashboard implementations remain unchanged.

The source-free measurement package is `data/evals/benchmark-completion/v1/`.
`MANIFEST.json` binds completed data; `REVIEW_MANIFEST.json` additionally binds the
report, implementation, focused tests and preservation receipts. Neither receipt
is reusable evidence authorization. Complete publisher evidence packages are
reconstructed by the unchanged public M8 service and remain ephemeral.

## Read-only dashboard

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/master_dashboard/coverage.py --server.address 127.0.0.1 --server.port 8512 --server.headless true --browser.gatherUsageStats false
```

This versioned successor reuses the expanded dashboard layout/navigation and exact
Candidate–Parent Explorer. Changes are limited to loading the new measured target
configuration, its provenance and explicit unsupported/no-measurement states.
`apps/master_dashboard/expanded.py` and `app.py` remain historical replay entries.
Refresh verifies manifests and reads receipts; it never retrieves, assembles,
prepares prompts, evaluates answers or contacts providers.

Every measurement retains question identity, source/index binding, native/ranking
provenance, candidate/package identity, token accounting and measurement origin.
The original15 measurements are reused after exact candidate/policy/native-parent
compatibility checks. Missing native results use accepted local M7 search and fuse;
missing M8 results use unchanged `EvidenceService.assemble`.

Direct discovery scores keep the original M9 overlap semantics separate from the
later strict OR/joint-AND witness semantics. Parent-group coverage and complete
verified-parent delivery are reported separately. Unsupported controls have no
positive recall denominator. Unlabeled candidates are unknown; retrieval precision
and nDCG are unavailable. No semantic answer quality is measured here.

## Reproduction and review boundary

Private helpers and commands are documented in the experiment's `REPORT.md` and
`REPRODUCIBILITY.md`. Replaying immutable files/scoring does not require retrieval.
An explicit newly authorized, separately versioned run is required to repeat local
queries or assembly; existing results must not be overwritten.

Before a future generation request: obtain separate owner authorization, freshly
revalidate M8 evidence, assemble the current prompt and qualify exact generator
input tokens, context/output reserve/safety margin and current cost. Historical
BGE budgets or Q05 token counts cannot qualify another request. Q05's prior paid
request remains consumed; all generation/post-generation results are unchanged.

No production defaults, ranking algorithm, source authority, parent atomicity,
labels, prompt/schema, model/pricing, dependencies or Git state change here.
Stop for owner review; this experiment does not authorize generation or adoption.
