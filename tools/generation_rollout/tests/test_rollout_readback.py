"""Sealed rollout readback and tamper rejection, with no pipeline operations."""
import json
from pathlib import Path

import pytest

from tools.generation_rollout.dashboard import read_rollout
from tools.quality_dashboard.artifacts import ArtifactError

ROOT = Path(__file__).resolve().parents[3]


def test_sealed_inventory_bindings_and_local_canary():
    summary, path = read_rollout(ROOT)
    assert summary['total_pending'] == 33 and summary['total_benchmark'] == 34
    assert [s['name'] for s in summary['stages']] == ['canary', 'pilot', 'remaining']
    assert summary['aggregate_maximum_estimated_cost_usd'] == '0.76430900'
    assert not summary['generation_authorized']
    base = ROOT / path.rsplit('/', 1)[0]
    q = json.loads((base / 'CANARY_LOCAL_VALIDATION.json').read_bytes())
    assert q['qualified_recipe_equivalence'] is True
    assert q['source_integrity'] == 'FRESH_PUBLIC_M8_VALIDATED'
    assert q['candidate_count'] == 30 and q['parent_count'] == 16
    assert q['provider_qualification'] == 'NOT_RUN_SEPARATE_APPROVAL_REQUIRED'


def test_altered_plan_is_rejected(tmp_path):
    source = ROOT / 'data/evals/generation-rollout/v1'
    target = tmp_path / 'data/evals/generation-rollout/v1'
    # Only small source-free sealed planning artifacts copied, never corpus text.
    for p in source.rglob('*'):
        if p.is_file():
            dst = target / p.relative_to(source)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(p.read_bytes())
    (target / 'canary/PLAN.json').write_text('{}')
    with pytest.raises(ArtifactError):
        read_rollout(tmp_path)
