# Current experimental prompt assembly

October 27, 2026. Owner-approved experimental default:
**grounded-generation-prompt-v2 + grounded-response-2.0**.
The seven-component anatomy and single short Atlas Search example are accepted
unchanged. This default is for new experimental preparations, not production.

Use the canonical entry point without a version override:

```python
from tools.pre_generation_gate.assembly import PromptAssemblyGate

gate = PromptAssemblyGate(evidence_service)
prepared = gate.prepare(original_question, m8_package, original_m7_result,
                        model_configuration=None)
```

The existing real, explicitly selected EvidenceService and original bound M7/M8
inputs are required. This entry point does not select retrieval settings, Top-K,
releases or an evidence budget. Top-30/128K is used only when explicitly supplied
by an authorized experimental caller. Production Top-10, RRF60 and M8 are unchanged.

No prior central selector or environment/config-file switch existed: callers chose
a versioned module directly. The new `assembly` module is the stable entry point
for all new work. It defaults to the approved v2 implementation and its paired
schema. Supplying schema 1.0 fails closed rather than falling back to prompt v1.
There is no automatic import rewrite of old sealed scripts or historical reports.

Explicit historical replay remains available:

```python
from tools.pre_generation_gate.assembly import HistoricalV1PromptAssemblyGate

historical = HistoricalV1PromptAssemblyGate(evidence_service)
replayed = historical.prepare(original_question, m8_package, original_m7_result,
                              model_configuration=None)
```

`HistoricalV1PromptAssemblyGate` is exactly the original
`tools.pre_generation_gate.prompt_v2.PromptAssemblyGate` class. The version-named
`prompt_v2` and `prompt_v3` modules remain immutable explicit replay routes for
templates v1 and v2 respectively. The package root previously exported no gate;
no default is claimed for imports that never existed. Start new integrations with
`assembly`, not a version-specific historical module.

Existing older README/API/architecture pages and saved inspection runners remain
delivery-time historical documentation; do not use their v1 import snippets for
new work. See [v2 anatomy and constraints](PROMPT_ANATOMY_V2.md) for the unchanged
content, and use this page for current selection and invocation behavior.

The source-free audit records template_version, response_schema_version,
request_sha256, M8_package_sha256, readiness status, model_configuration and an
explicit model_configuration_status. With no generator it is NOT_CONFIGURED;
a structurally declared profile remains DECLARED_UNQUALIFIED; invalid or not-yet
assessed configuration is labeled INVALID_OR_NOT_ASSESSED. The latter distinction
does not hide input or integrity blocks, which retain their original status/reason.
Request hashes are present only when an actual complete request was assembled.

No generator is qualified. Actual preparations remain BLOCKED_CONFIGURATION with
NO_OWNER_AUTHORIZED_GENERATOR_CONFIGURATION. Generator-token/context/schema support
remains unavailable/unverified; no readiness semantics changed. Coverage and
conflict outputs remain model declarations, not verified semantic findings.

M9-Q05 activation verification and source-free receipts:
`data/evals/prompt-default/activation-v1/`. No full publisher prompt is persisted.
All prior v1/v2 source/template/schema/example bytes, manifests, inspections and
accepted artifacts remain unchanged. No inference, source compaction, provider call,
production cutover, post-generation validation, M10/M11 or Git mutation is authorized.
The completed bounded implementation stops for owner review.
