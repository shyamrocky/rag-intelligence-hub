"""Owned synthetic records and keys only. Never enroll the project owner."""
import hashlib
import shutil
from pathlib import Path

import pytest

from tools.answer_quality.tests import test_policy as baseline_fixtures
from tools.generation.qualifications import _assess_metadata
from tools.human_review import workflow
from tools.human_review.identity import register
from tools.preflight_suite.artifacts import save
from tools.quality_dashboard.artifacts import digest, sha

PASSWORD = 'synthetic-test-passphrase-only'
REVIEWER = 'synthetic-reviewer'


@pytest.fixture
def owned():
    return baseline_fixtures.owned.__wrapped__()


@pytest.fixture(autouse=True)
def deny_network_and_api_keys(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('HUMAN_REVIEW_MUST_NOT_CALL_NETWORK_OR_PROVIDER')
    for name in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo',
                 'tools.preflight_suite.provider.load_key', 'tools.generation.openai_adapter.OpenAIAdapter.invoke',
                 'tools.generation.openai_adapter.OpenAIAdapter.count',
                 'tools.generation.openai_adapter.OpenAIAdapter.verify_model'):
        monkeypatch.setattr(name, denied)


@pytest.fixture
def context(tmp_path, owned, monkeypatch):
    root = tmp_path.resolve() / 'project'
    root.mkdir()
    store = tmp_path.resolve() / 'private-credentials'
    register(store, REVIEWER, 'Synthetic Reviewer', PASSWORD,
             'REGISTER synthetic-reviewer AS Synthetic Reviewer')
    for name in ('tools/human_review/POLICY.json', 'tools/answer_quality/POLICY.json'):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[3] / name, p)
    m7 = {'parameters': {'top_k': 30, 'candidate_depth': 50, 'rrf_k': 60, 'filters': {}},
          'retrieval_mode': 'hybrid', 'query_sha256': hashlib.sha256(owned['question'].encode()).hexdigest()}
    row = {'question_id': 'SYNTHETIC-Q1', 'question_sha256': hashlib.sha256(owned['question'].encode()).hexdigest(),
        'generation_executed': True, 'fixture_only': False, 'response': owned['response'],
        'M7_result_sha256': digest(m7), 'M8_package_sha256': digest(owned['package']),
        'request_sha256': owned['request_sha256'], 'post_validation': {'overall_status': 'REVIEW_REQUIRED'}}
    base = root / 'data/evals/generation-runner/synthetic-owned-test'
    save(base / 'RESULT.json', row)
    save(base / 'MANIFEST.json', {'schema': 'SYNTHETIC_TEST_ONLY_NOT_REAL_GENERATION', 'mode': 'live',
                                'files': {'RESULT.json': sha(base / 'RESULT.json')}})
    source = {'manifest_path': (base / 'MANIFEST.json').relative_to(root).as_posix(),
        'manifest_sha256': sha(base / 'MANIFEST.json'),
        'result_path': (base / 'RESULT.json').relative_to(root).as_posix(),
        'result_sha256': sha(base / 'RESULT.json')}
    assessment = baseline_fixtures.review(owned, method='ASSISTANT_ANALYSIS', independent_of_generator=False)
    calls = []

    class Source:
        def __init__(self):
            self.inventory = {}

        def validate(self, package, result):
            calls.append('source-validate')
            assert digest(package) == row['M8_package_sha256']
            assert digest(result) == row['M7_result_sha256']
            return True

        def check(self):
            calls.append('source-check')

    class SyntheticQualifications:
        def __init__(self, service):
            self.service = service

        def validate(self, response, package, result):
            self.service.validate(package, result)
            return _assess_metadata(response, {p['evidence']['unit_id']: p['evidence']['verified_parent']
                                               for p in package['parents']})

    service = Source()
    monkeypatch.setattr('tools.generation.qualifications.QualificationValidator', SyntheticQualifications)
    monkeypatch.setattr(workflow, 'live_context', lambda *a: (service, owned['package'], m7))
    monkeypatch.setattr(workflow, 'trust_check', lambda *a: (calls.append('trust-check') or ({}, {}, {})))
    manifest = workflow.prepare(root, source=source, question=owned['question'], assessment=assessment,
        trust={'path': 'SYNTHETIC_TRUST_ONLY', 'sha256': '0' * 64})
    p, _, h = workflow.load_package(root, manifest)
    return {'root': root, 'store': store, 'manifest': manifest, 'sha': h, 'package': p,
            'row': row, 'owned': owned, 'service': service, 'calls': calls}

