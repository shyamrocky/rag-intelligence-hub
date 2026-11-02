# Experimental pre-generation gate v1

Owner-authorized bounded build, October 27, 2026. No production cutover.

This component implements live evidence validation, question binding, conservative
syntactic requirements, source-pointer audit records and a deterministic decision
contract. **No qualified semantic assessor exists in the project.** The implemented
runtime therefore reports `INDETERMINATE / ABSTAIN`, including for valid complete
evidence. It cannot establish semantic relevance, completeness, conflicts or a
reliable requirement-to-source support mapping. This is an unmet acceptance
criterion, not a successful semantic gate.

Use the existing embedding environment (NumPy and PyMuPDF) and the existing M8
counting environment. No dependency, environment or model changes are needed.
From the project root, inside a trusted local Python application:

```python
from tools.evidence.service import EvidenceService
from tools.pre_generation_gate.contract import GateConfiguration
from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA, ValidationGate

service = EvidenceService(root, selector=M8_SELECTOR, selector_sha256=M8_SHA)
gate = ValidationGate(service, configuration=GateConfiguration())
package = service.assemble(original_m7_result, token_budget=128000)
verdict = gate.assess(question, package, original_m7_result)
```

`original_m7_result` must be an accepted explicit-release candidate envelope bound
to the same normalized question. Obtain it through existing approved retrieval or
an explicitly labeled, verified sealed-result replay. Do not fabricate retrieval
provenance. This example performs no search or generation.

Every `assess` calls the original `EvidenceService.validate(package, result)`;
that function reassembles live complete parents. A verification flag, package
checksum or saved result is never a detached evidence authorization. The gate
retains no packages or authorization cache. Caller-owned inputs are copied and
not mutated. Immediately revalidate M8 before a future separately authorized
consumer uses evidence; a gate audit is not a reusable permission token.

Only the implemented `deterministic-controls-semantic-unavailable-1.0` configuration
is accepted. There is no public semantic-verdict injection API. The pure
`reduce_assessment` function defines future decision semantics and can be tested
with explicitly synthetic assertions; those tests do not implement an assessor.

The actual gate does not issue PROCEED or RETRIEVE_MORE. Without semantic scope
and support qualification, it cannot determine that further retrieval would help.
See the isolated evaluation packet under
`data/evals/pre-generation-gate/experiment-v1/` and the
[architecture and evaluation contract](../../docs/PRE_GENERATION_GATE_EXPERIMENT.md).

Pure deterministic tests:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  uv run --locked --offline --no-sync python -m pytest \
  tools/pre_generation_gate/tests/test_contract.py -q -p no:cacheprovider
```

Actual M8 integration controls (private accepted assets required):

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  tools/embeddings/.venv/bin/python -m pytest \
  tools/pre_generation_gate/tests/test_live.py -q -p no:cacheprovider
```

Keep publisher packages out of logs, Git and unrestricted caches. The audit output
contains hashes and native source pointers, not publisher passages. No external
calls, model execution, retrieval retry loop, M8 compaction or generation exists.
