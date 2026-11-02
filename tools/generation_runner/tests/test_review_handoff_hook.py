"""Native post-seal hook using disposable source/provider boundaries only."""
import json

from test_stage_policies import (
    fake_pipeline,
    run_synthetic,
    synthetic_approval,
)
from test_stage_policies import owned as owned  # noqa: PLC0414
from test_stage_policies import stages as stages  # noqa: PLC0414


def test_native_runner_invokes_handoff_only_after_immutable_seal(stages, monkeypatch):
    from tools.human_review import handoff
    stage = stages['pilot']
    path, fingerprint = synthetic_approval(stage, 'handoff-owned-test')
    fake_pipeline(monkeypatch, stage)
    calls = []
    def observe(root, manifest):
        value = json.loads((root / manifest).read_bytes())
        assert value['mode'] == 'live' and len(value['question_ids']) == 4
        assert (root / manifest).is_file()
        calls.append(manifest)
    monkeypatch.setattr(handoff, 'after_generation', observe)
    result = run_synthetic(stage, path, fingerprint)
    assert calls == [(result / 'MANIFEST.json').relative_to(stage.root).as_posix()]
