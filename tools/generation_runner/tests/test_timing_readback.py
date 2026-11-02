"""Filesystem-only readback of the sole owner-authorized real-M8/mock observation."""
import hashlib
import json
from pathlib import Path

from tools.generation_runner.dashboard import discover
from tools.generation_runner.timing import validate_timing

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'workspace/rag-implementation/v1/stage-latency-v1'
RUN = ROOT / 'data/evals/generation-runner/20261028T214228-mock-9aa0b209dbcf'


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_single_run_has_exact_recipe_and_no_provider_or_live_admission():
    manifest = read(RUN / 'MANIFEST.json')
    results = read(RUN / 'RESULTS.json')
    assert manifest['question_ids'] == ['M9-Q01'] and manifest['mode'] == 'mock'
    assert results['selected'] == results['completed'] == results['mock_invocations'] == 1
    assert results['provider_calls'] == results['live_generation_calls'] == results['live_generation_attempts'] == 0
    assert len(list(RUN.rglob('MOCK_ATTEMPT.json'))) == 1
    assert not list((ROOT / 'data/evals/generation-runner').rglob('LIVE_ATTEMPT.json'))
    assert not (ROOT / 'data/evals/generation-runner/authorization-use').exists()
    row = results['questions'][0]
    prior = read(ROOT / 'data/evals/preflight-suite/20261028T162022-model-preflight-b436659c001f/questions/M9-Q01/REQUEST_PACKAGE.json')
    assert row['request_sha256'] == row['audit']['request_sha256'] == prior['request_sha256']
    assert row['M8_package_sha256'] == prior['M8_package_sha256']
    assert row['source_integrity'] == row['post_validation']['source_integrity'] == 'LIVE_M8_VALIDATED'
    assert row['post_validation']['fully_validated'] is False
    assert row['response']['status'] == 'ABSTAINED' and row['fixture_only']


def test_run_and_execution_source_bindings_are_intact():
    manifest = read(RUN / 'MANIFEST.json')
    archives = read(WORK / 'EXECUTED_SOURCE.json')
    for name, fingerprint in manifest['files'].items():
        assert sha(RUN / name) == fingerprint
    for name, fingerprint in manifest['input_bindings'].items():
        # Exact measured source remains archived after documented lint-only cleanup.
        path = ROOT / archives[name]['archive'] if name in archives else ROOT / name
        assert sha(path) == fingerprint
    for change in read(WORK / 'LINT_ONLY_SOURCE_CHANGES.json').values():
        assert change['normalized_AST_equal']


def test_stage_receipt_and_dashboard_readback_are_consistent():
    receipt = read(RUN / 'questions/M9-Q01/STAGE_TIMINGS.json')
    row = read(RUN / 'questions/M9-Q01/RESULT.json')
    validate_timing(receipt, question_id='M9-Q01', run_id=RUN.name, mode='mock',
                    request_sha256=row['request_sha256'])
    found = next(r for r in discover(ROOT)['runs'] if r['manifest']['run_id'] == RUN.name)
    assert found['timings']['M9-Q01'] == receipt
    assert receipt['generation_label'] == 'MOCK_ADAPTER_DURATION'
    assert receipt['preflight_observation'] == 'REUSED_HISTORICAL'
    assert receipt['provider_reported_latency_ms'] is None
    assert receipt['error_stage'] is None
    assert set(read(ROOT / 'tools/generation_runner/stage-timings-v1.schema.json')['required']) == set(receipt)


def test_network_credentials_provider_and_live_markers_remain_zero():
    safety = read(WORK / 'SAFETY.json')
    assert all(safety[k] == 0 for k in ('network_attempts', 'credential_reads',
        'provider_operations', 'live_adapter_creation'))
    assert safety['token_worker_launches'] > 0


def test_protected_history_and_safeguards_preserved():
    before = read(WORK / 'BEFORE.json')
    allowed = set(before['authorized_edit_paths'])
    for name, fingerprint in before['bindings'].items():
        if name not in allowed:
            assert sha(ROOT / name) == fingerprint, name
    assert all(name not in allowed for name in ('tools/generation_runner/live.py',
        'tools/generation_runner/controls.py', 'tools/generation_runner/plan.py'))
