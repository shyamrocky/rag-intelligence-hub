"""Sealed synthetic history discovery and fail-closed payload checks."""
import json

import pytest

from tools.generation_runner.dashboard import discover
from tools.generation_runner.plan import VERSION
from tools.preflight_suite.artifacts import save, sha
from tools.quality_dashboard.artifacts import digest


def publish(root, *, tamper=None):
    run = root / 'data/evals/generation-runner/owned-mock'
    plan = {'owned': True}
    plan['plan_sha256'] = digest(plan)
    row = {'question_id': 'R01', 'mode': 'mock', 'provider_calls': 0, 'generation_executed': False}
    results = {'mode': 'mock', 'questions': [row]}
    save(run / 'PLAN.json', plan)
    save(run / 'RESULTS.json', results)
    save(run / 'questions/R01/RESULT.json', row)
    files = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    manifest = {'schema': VERSION, 'run_id': run.name, 'mode': 'mock',
                'status': 'SEALED_PENDING_OWNER_REVIEW', 'plan_sha256': plan['plan_sha256'],
                'question_ids': ['R01'], 'files': files}
    if tamper == 'wrong-mode':
        manifest['mode'] = 'live'
    save(run / 'MANIFEST.json', manifest)
    if tamper == 'changed-payload':
        (run / 'RESULTS.json').write_text('{}')
    if tamper == 'unsealed':
        (run / 'MANIFEST.json').write_text(json.dumps({'schema': VERSION}))
    return run


def test_new_sealed_records_appear_without_code_changes(tmp_path):
    assert not discover(tmp_path)['runs']
    publish(tmp_path)
    assert len(discover(tmp_path)['runs']) == 1


@pytest.mark.parametrize('tamper', ['changed-payload', 'unsealed', 'wrong-mode'])
def test_invalid_history_is_unavailable(tmp_path, tamper):
    publish(tmp_path, tamper=tamper)
    observed = discover(tmp_path)
    assert not observed['runs'] and len(observed['rejected']) == 1
