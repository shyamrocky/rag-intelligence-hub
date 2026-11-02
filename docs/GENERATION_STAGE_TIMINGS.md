# Generation Runner stage timings v1

Status: implemented for owner review, October 28, 2026. This is instrumentation,
not performance optimization or live-execution authorization.

The existing `tools.generation_runner` emits
`grounded-generation-stage-timings-1.0` in `questions/<ID>/STAGE_TIMINGS.json`.
The JSON shape is defined in `tools/generation_runner/stage-timings-v1.schema.json`;
the Python validator additionally verifies nesting, identities, exclusive-time
arithmetic and reconciliation to elapsed time. The existing run manifest binds
the receipt. No historical result is rewritten or assigned inferred timings.

## Boundaries

Each question starts a `time.perf_counter_ns()` clock immediately upon entering
its execution loop. Elapsed milliseconds end after result persistence and a
per-question `QUESTION_RESULT_MANIFEST.json` seal. This includes local validation
receipt writes, file hashing, cost-admission markers within the existing adapter,
final source checks, and incidental question overhead. It excludes shared plan
construction, service initialization, timing-receipt serialization/publication,
and shared final run-manifest hashing/publication. These exclusions are explicit:
a receipt cannot include the completed duration of publishing its own final bytes.
This is question execution latency, not CLI startup-to-exit latency.

| Stage | Actual measured boundary |
|---|---|
| SAVED_INPUT_VERIFICATION | Existing binding verification, saved M7 envelope read, and preparation helper's existing `validate_candidates` call. No retrieval. |
| M8_EVIDENCE_ASSEMBLY | Each existing public `EvidenceService.assemble` call, including reconstruction required by subsequent validation. Source checks inside assembly are inseparable from this boundary. |
| M8_SOURCE_VALIDATION | Existing public `EvidenceService.validate` calls. Inclusive spans contain their nested reassemblies; exclusive duration is additional comparison/validation overhead. |
| PROMPT_ASSEMBLY | Existing `prepare` and `validate_preparation` calls. Nested M8 work is separated by exclusive accounting. |
| MODEL_PREFLIGHT | Existing `GenerationService.dry_run`, called once by `generate`; includes local context/cost qualification. Nested validation and metadata/count calls are separately observable. |
| MODEL_METADATA | Existing adapter `verify_model` call. MOCK measures local fixture execution, not model access. |
| MODEL_TOKEN_COUNT | Existing adapter `count` call. MOCK replays sealed token observations; this duration is not new provider counting. |
| LLM_GENERATION | Existing adapter `invoke`, including its existing cost/attempt safeguards. MOCK is `MOCK_ADAPTER_DURATION`; future LIVE is local request duration, not pure server inference time. |
| POST_GENERATION_VALIDATION | Existing deterministic validator call; nested M8 validation is separated. |
| ARTIFACT_PERSISTENCE | Existing local-audit/result writes, plus additive per-question result hashing/sealing. |
| REQUEST_BINDING_AND_POLICY | Existing request recipe construction, exact equivalence and transfer-policy checks. |
| GENERATION_SERVICE_OVERHEAD | Local work in `generate` outside nested measured operations, including response parsing and pricing. |
| FINAL_SOURCE_CHECK | Existing final `EvidenceService.check`. |

Observers delegate exactly once with the same arguments, return value and
exceptions, then restore the original bound method. They persist no arguments,
source passages, exception messages or credentials. They are serial scopes;
parallel question execution is not introduced. The preparation helper's imported
candidate validator is observed temporarily and restored; accepted helper files
are unchanged. No source validation is skipped or added.

## Reading the numbers

The table's `duration_ms` is **exclusive** stage time. Each nested interval is
subtracted from its immediate parent. Summing exclusive stage totals plus
`unattributed_overhead_ms` reproduces end-to-end elapsed time. Do not sum inclusive
spans: they intentionally overlap. Nested spans show initial reconstruction and
later reconstruction inside M8 validation separately. The slowest-stage share
uses exclusive time divided by total question elapsed time.

`MEASURED` means observed execution, not a successful semantic/validation verdict.
`FAILED` retains elapsed partial observations and an error stage without exception
text. `SKIPPED` has null duration, never fabricated zero. Historical absence is
`NOT_MEASURED`. MOCK metadata/count observations are `REUSED_HISTORICAL`, while
their local replay durations are newly measured. All mock usage/cost remains
synthetic. A handled provider failure may leave a failed inner span even though
the outer service returns normally.

Existing usage `latency_ms` is preserved independently. The current OpenAI adapter
measures local HTTP-call duration; it does not expose a separate provider-reported
inference duration. `provider_reported_latency_ms` remains null / `UNAVAILABLE`.
An existing mock latency of zero is synthetic and is not substituted for measured
mock-adapter duration. No additional calls are made to obtain timing data.

If result persistence fails, the runner attempts to publish the partial timing
receipt once, then propagates the original failure. If storage itself cannot save
the receipt, observations cannot be durably recovered; no success is fabricated.
Unsealed failures remain unavailable to the dashboard. No retry is added.

## Dashboard and safety

The canonical Master Dashboard remains `apps/master_dashboard/canonical.py`,
port 8514. The runner page displays selected-run timings; Quality & Telemetry
shows the latest question-level runner observation with its mode/run identity,
separate from real generation metrics. Historical absence remains explicit.
On `/quality`, the breakdown appears **inside Retrieval Pipeline Telemetry**, below
the shared question selector. The page title and benchmark overview remain first.
The read-only `latency_ui` adapter reuses the exact historical layout function in
an isolated rendering namespace and composes only its pipeline renderer. It does
not copy the layout, patch module globals or change the hash-bound historical UI.
If the selected question
has no measurements, a shortcut selects a question with sealed timings and clears
incompatible display filters. This is navigation only and executes no pipeline work.
Technical Details contains nested spans, hashes, project-relative provenance and
a source-free timing-receipt download. Refresh, selection and download cannot
execute the runner, M8, prompt assembly or provider calls. Tampered or unsealed
timing records fail closed.

Future LIVE uses the same timer scopes but retains exact owner authorization,
single-use authorization, durable attempt markers, one request per question,
no retries/fallback and unchanged cost/context/source guards. Instrumentation
changes implementation fingerprints, so any future authorization must bind the
then-current implementation. This task creates or consumes no live authorization.

The existing one-question command is unchanged:

```sh
PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner mock --question M9-Q01 --per-question-cap 0.03 --aggregate-cap 1.00
```

The owner authorized one invocation for this task. Documentation is not repeat
execution permission. No full benchmark, paid generation, model change or stage
optimization is authorized.
