# M9 complete reproduction recipe

The final measured release and its original delivery seal remain unchanged. This additive recipe provides the repository structural-inspection helper used to reproduce the C16 overhead analysis; it introduces no runtime evidence path, new inference or compact projection.

Run from the repository root in the existing locked embedding environment. A fresh, separately authorized logical replay uses a new private output directory. Do not overwrite the accepted measured release or publish a replacement selector automatically.

```sh
uv run --locked --offline --no-sync --project tools/embeddings python -m tools.evaluation.runner --config-sha256 222e23d0987966eb3b7c748fa036b2d9fec435e06716ec7739f2d0ab917e9962 --output data/evals/m9/runs/m9-replay-001
uv run --locked --offline --no-sync --project tools/embeddings python -m tools.evaluation.verify_results --run data/evals/m9/runs/m9-replay-001
uv run --locked --offline --no-sync --project tools/embeddings python -m tools.evaluation.inspect_overhead --run data/evals/m9/runs/m9-replay-001
```

Compare logical rankings, metrics and token costs without writing the original reports:

```sh
uv run --locked --offline --no-sync --project tools/embeddings python - <<'PY'
import json
from pathlib import Path
base = json.loads(Path("data/evals/m9/runs/m9-v3/RESULTS.json").read_bytes())
replay = json.loads(Path("data/evals/m9/runs/m9-replay-001/RESULTS.json").read_bytes())
assert base["summary"] == replay["summary"]
for old, new in zip(base["cases"], replay["cases"], strict=True):
    assert (old["question_id"], old["mode"]) == (new["question_id"], new["mode"])
    assert old["retrieval"] == new["retrieval"]
    assert old["candidate_result"]["candidates"] == new["candidate_result"]["candidates"]
print("PASS_LOGICAL_METRIC_AND_RANKING_REPLAY")
PY
```

Timings, process resources and packages hashing timing-bearing candidate diagnostics are intentionally excluded. `tools.evaluation.report` is a canonical delivery build step that writes the original workstream reports; do not invoke it for a replay or after the delivery seal. The read-only comparison above is the supported replay check. The helper refuses to overwrite differing diagnostics and verifies an existing identical file without rewriting it. The original observed C16 diagnostic was reproduced byte-identically against the live gateway.

`tools.evaluation.publish_results` built the canonical opt-in result descriptor after verification. It refuses to overwrite a different existing selector. A replay is not permission to replace that descriptor, alter benchmark labels, publish source approvals or start M10. All existing QA, model, index, source and complete-parent restrictions remain binding.
