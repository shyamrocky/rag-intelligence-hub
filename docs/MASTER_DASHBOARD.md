# Master Dashboard and question-level quality telemetry

October 28, 2026. Bounded M10 implementation, pending owner review. No production
cutover, additional generation, semantic evaluator or M11 work is authorized.

Launch from the project root using the **existing dashboard locked environment**:

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/master_dashboard/app.py --server.address 127.0.0.1 --server.port 8512 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8512>. No installation, key or provider connection is needed.
Required private sealed artifacts must already exist locally. Missing or changed
required bindings block display; there is no historical fallback. Keep the server
bound to localhost. No authentication/public hosting or remote publication is added.

## Navigation and reuse

The new experimental entry point has Master Dashboard, Candidate–Parent Explorer
and End-to-End Quality & Telemetry pages. The existing sealed explorer is HTML/JS,
not Streamlit. Its exact self-contained HTML is embedded unchanged in an iframe;
its native question selector, chunk journeys and source metadata remain intact.
No candidate browser is rebuilt. Source content remains in the original verified
Chunk Inspector, launched separately through the preserved ingestion dashboard:

```sh
PYTHONPATH=. apps/ingestion_dashboard/.venv/bin/python -m streamlit run apps/ingestion_dashboard/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

That original entry point, historical inspection modes and source readers are
unchanged. The master app adds no source payload endpoint. A provenance link opens
only registered relative-path/hash metadata, never arbitrary file contents.

## Data and measurement contract

`tools/quality_dashboard/adapter.py` reads the approved 15-question freeze and
22 mandatory groups, sealed candidate/ranking/selection results, actual M8 budget
measurements, historical prompt audits, generation results and post-validation
receipts. It reuses `tools.evaluation.results.load_results` to validate and display
the original M9 29-question evaluation **separately**, with its 26 answerable and
3 unsupported denominators. R01–R05 are not retrospectively added to that run.

The adapter imports no provider, model or live EvidenceService. Refresh rehashes
required manifests and payloads, external implementation bindings and current
accepted source/index/publication bindings. It performs no retrieval, ranking,
model/tokenizer loading, M8 assembly, inference or credential reads. Manifest
identity checks verify a recorded measurement; they are not source authorization
or owner acceptance. No database or competing publication register is created.

Metric records carry name, value, numerator/denominator where applicable, unit,
measurement status, experiment/version, calculation method and an artifact reference.
Artifact references resolve to project-relative names and SHA-256 hashes. Only
recognized measurement schemas are normalized. Missing values remain unavailable.
Source passages, full prompts, full parent packages, raw provider responses and
credentials are never served. Model answer text is displayed as inert text; quoted
publisher passages are represented by counts/hashes/offset receipts.

Statuses are MEASURED, REUSED_HISTORICAL, NOT_RUN, UNAVAILABLE, PENDING_REVIEW,
FAILED and INDETERMINATE. Historical M7/M8/M9 values are reused, not freshly measured
retrieval. The newly executed Q05 post-validation receipt is marked MEASURED where
appropriate; its applicability verdict is INDETERMINATE.

Important definitions:

- **Direct-witness discovery:** approved OR alternatives and joint-AND witnesses
  found in the selected chunks. Unlabeled candidates remain unknown.
- **Parent-location discovery:** a selected chunk leads to an approved supporting
  complete parent, even if that chunk does not contain the approved passage.
- **M8 delivery:** the complete authorized supporting parent was actually included.
  Native parent/qualification obligations are unchanged.
- **Retrieval-to-delivery loss:** parent-located groups minus delivered groups,
  using comparable parent-level semantics; never subtract direct discovery from
  parent delivery as though those were identical metrics.
- **Cited-Parent Utilization:** distinct cited included parents / supplied parents.
  It is descriptive context use, not precision or proof uncited context was waste.
- **Retrieval precision:** UNAVAILABLE — INSUFFICIENT RELEVANCE LABELS. Known-positive
  witnesses are not exhaustive negative judgments. nDCG remains NOT_MEASURED.
- **Cost:** recorded actual-usage-based ESTIMATED_API_COST, not invoice charges.
  Cache reads/writes are already part of inclusive input; reasoning is part of output.
  Unknown failed-attempt charges are excluded from known totals, not assigned zero.
- **Answer quality:** model-reported coverage/conflicts are declarations. Existing
  engineering review is shown with pending-owner status, not independent certification.

The funnel displays different units and denominators explicitly. NOT_RUN is not
an answer failure. BGE evidence budgets and generator tokens remain distinct.
The current v2.1 prompt has no qualified new generator count; historical v2's
86,200-token provider count is never reused for v2.1 context readiness.

## Automatic discovery and configuration isolation

On refresh, the adapter scans `data/evals/generation/*/MANIFEST.json` and
`data/evals/post-generation/*/MANIFEST.json`. It verifies complete file bindings,
recognizes supported schemas and deduplicates repeated response identities. It
prefers latest completed results per question while retaining failed/history entries.
Malformed/unsealed/incompatible artifacts are excluded with an availability warning.
It does not invoke their scripts or infer that a file being present is a measurement.

Existing one-question funded/failed schemas are supported. Future equivalent
same-pipeline generation records can use `quality-generation-experiment-1.0`:

```json
{
  "schema": "quality-generation-experiment-1.0",
  "status": "COMPLETED_SEALED",
  "question_id": "<frozen ID>",
  "dataset_freeze_manifest_sha256": "<exact accepted freeze>",
  "date": "<ISO timestamp or version>",
  "files": {"GENERATION_AUDIT.json": "<sha256>", "GENERATED_RESPONSE.json": "<sha256>"}
}
```

The audit must be the existing `generation-result-1.0`, with the exact compatible
M8 package identity, LIVE_M8_VALIDATED source status and valid measured usage.
Completed responses must satisfy the preserved schema2/authorized-included-ID
relationships. Audits and responses are original experiment records, not copied
numbers in application code. A different candidate list/M8 configuration is
explicitly incompatible with this fixed RRF-30/128K view; add a reviewed adapter
before displaying another configuration rather than silently joining it.
New semantic-review formats likewise require a qualified explicit adapter. No new
owner-approved score is inferred from a self-declared field.

## Deterministic post-generation validation

`tools/quality_dashboard/post_generation.py` exposes
`PostGenerationValidator(real_evidence_service).validate(response, package, m7_result,
question=original_question)`. It reuses:

- Accepted M7 parameter/query normalization and exact question binding.
- Real `QualificationValidator`, which calls public live M8 `.validate` and thus
  reassembles/compares source content, publications, citations and all obligations.
- Existing response2 Python schema, status/claim/coverage relationships and included
  authorized Unit-ID scope, including omitted/example-ID rejection.
- The exact sealed, source-only quotation inspector from the original Q05 experiment.
  This private workspace helper is a required bound dependency; a missing/changed
  helper fails closed. Its generation entry point is never executed.
- Native `citation_locators`, without upgrading display/parent-level precision.

Invalid source/question/package inputs raise integrity errors, never ordinary
retrieval misses. Fabricated quotations and absent citation locators fail mechanical
checks. A genuine unrelated quotation can pass substring matching; semantic
entailment, correctness and complete-answer quality remain pending independent review.
Qualification applicability ambiguity remains INDETERMINATE; no answer repair,
warning insertion, retry or semantic judge is implemented.

An explicit offline validation command, which refuses an existing output directory:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.quality_dashboard.validate_offline --output data/evals/post-generation/<new-version>
```

It reopens the already generated Q05 through M8 only, with all provider methods
patched to reject calls and networking disabled. It reads no credentials and parses
no gold labels for validation. It must not be run on dashboard refresh. Only the
separate owner-authorized offline task executes it.

The original development receipt `q05-v1` used the wrong field name `citations`
and reported a false missing-locator failure. It is preserved, explicitly superseded
by `q05-v2`, whose corrected native-field check passes. Neither record changes the
original source or funded response. The dashboard displays the later corrected
receipt. This is an adapter correction, not a newly discovered source defect.

## Review boundary

The bounded implementation makes retrieval → delivery → generation → deterministic
checks inspectable. It does not complete independent semantic answer evaluation,
resolve C03 disclosure applicability, qualify the changed v2.1 request for generation,
or authorize further inference. R03 selection loss, Q23/R04 assembly displacement,
large atomic parent costs and eight Post-M11 findings remain unchanged.

Review evidence is under `data/evals/quality-dashboard/implementation-v1/`.
Historical M0–M9, explorer, prompt/schema, locks and production defaults are preserved.
Stop for owner review; no automatic milestone acceptance is recorded.
