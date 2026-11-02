# Canonical RAG Intelligence Hub Master Dashboard

October 28, 2026. Owner-authorized launch/navigation consolidation, pending review.

## One launch command

Run from the project root using the existing locked dashboard environment:

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/master_dashboard/canonical.py --server.address 127.0.0.1 --server.port 8514 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8514>. No installation, credentials or provider connection
is required. Required private sealed data must already be present locally.
The explicit port8514 in this command is the single supported default local port;
no global Streamlit/server configuration or production defaults are changed.

## Why the launcher is canonical.py

`apps/master_dashboard/app.py` is historically hash-bound by the original dashboard
implementation manifest. Its SHA-256 is
`bbf9ac8876c5d25e2649f96fa93225f3cbf5c129153ac7b91a6f4aa60d4e7cc2`.
The owner's explicit protected-entry fallback therefore applies: preserve app.py
byte-identically and designate **apps/master_dashboard/canonical.py** as the single
canonical launcher. It delegates directly to the already implemented
`tools.preflight_suite.ui.main`. It contains no duplicate dashboard, adapter,
pipeline implementation, routing framework or database.

The launcher reuses the existing navigation and views:

| Destination | Existing component | Scope |
|---|---|---|
| Master Dashboard | preflight_home.py | Reconciled benchmark, project and preflight overview |
| Candidate–Parent Explorer | explorer.py | Exact sealed explorer and candidate/parent navigation |
| End-to-End Quality & Telemetry | preflight_quality.py | M7/M8 telemetry, offline M9 comparisons, generation, post-generation and preflight history |
| RAG Preflight Suite | preflight_suite.py | Local-check/model-preflight receipts, run history, cost/readiness, stage/module transparency and documented CLI |

Cohort filters, shared question selection, historical comparisons, Q05's real
answer/usage/cost/qualification caveat, all33 preflight results and changed-dependency
historical observations are provided by those existing components unchanged.
M9 remains offline evaluation, not a runtime stage. Qualification is technical
request compatibility, not semantic sufficiency or generation authorization.

## Read-only boundary

Refresh and navigation only discover and validate sealed artifacts. They never
retrieve, assemble M8 evidence, prepare prompts, run the preflight suite, read API
credentials, invoke providers, generate answers or evaluate generated answers.
Existing safe artifact references and source-content restrictions remain in force.
No execution controls are added. The CLI examples inside the preflight view are
instructions for separately authorized work, not actions triggered by the dashboard.

## Historical entry points and documentation

The following remain byte-identical and available for reproducibility:

- app.py: original15-question Master Dashboard.
- expanded.py:34-question reconciliation view at its delivery checkpoint.
- coverage.py: completed M7/M8 measurement view.
- preflight.py: original preflight-suite integration entry.

Their sealed reports, old documentation and historical port examples remain
unchanged. They describe past checkpoints; they are not alternative current launch
instructions. Use only the canonical command above for normal operation.
No accepted source bindings, experiments, prompt/schema/model/pricing, production
retrieval settings or Git/recovery state are changed by consolidation.

## Verification and review

New Streamlit AppTest checks exercise the canonical entry's real pages, selectors,
filters, all33 local/model preflight records, Q05 telemetry and the exact explorer.
Pipeline/provider/network methods are forbidden during these tests, including an
explicit dashboard refresh. Historical entry points remain covered by their
existing regression tests. Scaffold checks are separate from RAG quality evaluation.

Actual commands, results, preservation hashes and browser availability are in the
private versioned review packet under `data/evals/canonical-dashboard/v1/`.
Stop for owner review. No API execution, benchmark generation, production cutover
or subsequent milestone acceptance is implied.
