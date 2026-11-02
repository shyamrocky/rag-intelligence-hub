"""Integration readback after representative real-M8 / synthetic-response execution."""
from pathlib import Path

from tools.generation_runner.dashboard import discover
from tools.quality_dashboard.artifacts import digest

ROOT = Path(__file__).resolve().parents[3]


def test_sealed_representative_mock_preserves_plan_and_validates_automatically():
    telemetry = discover(ROOT)
    assert not telemetry['rejected']
    expected = {'M9-Q01', 'R03', 'M9-Q27'}
    matching = [r for r in telemetry['runs'] if r['manifest']['mode'] == 'mock'
                and set(r['manifest']['question_ids']) == expected]
    assert matching, 'Representative integration must complete before this check'
    run = matching[-1]
    result, plan = run['results'], run['plan']
    assert result['provider_calls'] == result['live_generation_calls'] == result['live_generation_attempts'] == 0
    assert result['mock_invocations'] == 3
    assert plan['generation_authorized'] is False
    assert result['completed'] == result['selected'] == 3
    for row in result['questions']:
        assert row['source_integrity'] == 'LIVE_M8_VALIDATED'
        assert row['fixture_only'] is True
        assert row['response']['status'] == 'ABSTAINED'
        assert row['semantic_status'] == 'SYNTHETIC_NOT_SCORED'
        assert row['audit']['generation_executed']  # Owned adapter, never a provider request.
        post = row['post_validation']
        assert post['source_integrity'] == 'LIVE_M8_VALIDATED'
        assert post['response_sha256'] == digest(row['response'])
        assert post['semantic_status'] == 'PENDING_REVIEW'
        assert post['fully_validated'] is False
        assert post['M8_package_sha256'] == row['M8_package_sha256']
    directory = ROOT / run['manifest_path'].rsplit('/', 1)[0]
    assert len(list(directory.rglob('MOCK_ATTEMPT.json'))) == 3
    assert not list(directory.rglob('*LIVE*ATTEMPT*'))
    assert not (ROOT / 'data/evals/generation-runner/authorization-use').exists()
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in directory.rglob('*.json'))
