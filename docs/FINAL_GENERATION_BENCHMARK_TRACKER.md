# Final Generation Benchmark Tracker

The canonical Streamlit dashboard includes a read-only **Final Generation Benchmark
Tracker** at <http://127.0.0.1:8514/final-generation-benchmark-tracker>, linked from
the Master Dashboard at <http://127.0.0.1:8514/> and the sidebar. The existing launch
command and port are unchanged.

The page reuses the verified completion/attempt readers, original rollout plans,
seven qualified batch plans and existing review records. It shows one selected
result per question, with stage/cohort filters, original question text, model
declaration, contract acceptance, recorded validation, separate source-bound
reassessment, owner-review state, findings, cost, tokens, API latency and raw-capture
availability. Source-free CSV/JSON exports include the table metadata, never raw
provider bodies or publisher passages.

Batch totals include all attempts, including Q18's separately authorized recovery
and Q05's earlier failed request. Missing usage/cost stays unavailable. API latency
excludes local M8 reconstruction and review preparation. Measured-use estimated API
cost is not invoice spending or an API balance; conservative reservations are separate.

Historical verdicts are not overwritten. A versioned reassessment must bind the same
question, response, request and M8 package before being shown. Self-sealed assessments
cannot confer authenticated semantic acceptance. Local POC approvals are displayed
only for their exact response identity. Rejected responses remain untrusted diagnostic
items; their model status does not imply contract acceptance. Raw-output access and
actual review decisions remain in Generation Runner → Human Review.

Refresh, filtering, exports and navigation perform no retrieval, M8 assembly,
prompt preparation, model qualification, generation, review submission or provider
calls. No execution buttons are added. Historical navigation and the Explorer remain.
The additive review-only trust successor preserves archived UI implementations and
old sealed results. Its permitted generation question set is empty; it cannot be
used to authorize paid execution.
