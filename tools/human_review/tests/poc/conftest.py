"""POC controls use owned evidence and NO reviewer keys, even synthetic ones."""
import hashlib
import shutil
from pathlib import Path

import pytest

from tools.answer_quality.tests.test_policy import review
from tools.generation.qualifications import _assess_metadata
from tools.human_review import identity, local_poc, workflow
from tools.preflight_suite.artifacts import save
from tools.quality_dashboard.artifacts import digest, sha


@pytest.fixture(autouse=True)
def no_signing_or_human_authentication(monkeypatch):
    def denied(*a, **kw):
        pytest.fail('POC_MUST_NOT_REGISTER_SIGN_OR_IMPORT_AUTHENTICATED_HUMAN_REVIEW')
    for name in ('register', 'keygen', 'sign', 'authenticate'):
        monkeypatch.setattr(identity, name, denied)
    monkeypatch.setattr('tools.answer_quality.review.HumanReview.__init__', denied)
    monkeypatch.setattr(local_poc, 'local_access', lambda: {
        'bind': '127.0.0.1', 'headers': {'Host': '127.0.0.1:8514', 'Origin': 'http://127.0.0.1:8514'}, 'peer': None})


@pytest.fixture
def poc_context(tmp_path, owned, monkeypatch):
    root = tmp_path.resolve()
    for name in (workflow.POLICY, local_poc.POLICY, 'tools/answer_quality/POLICY.json',
                 'tools/answer_quality/POLICY_2_1.json'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[4] / name, target)
    m7 = {'parameters': {'top_k': 30, 'candidate_depth': 50, 'rrf_k': 60, 'filters': {}},
          'query_sha256': hashlib.sha256(owned['question'].encode()).hexdigest(), 'retrieval_mode': 'hybrid'}
    row = {'question_id': 'SYNTHETIC-Q1', 'question_sha256': hashlib.sha256(owned['question'].encode()).hexdigest(),
        'generation_executed': True, 'fixture_only': False, 'response': owned['response'],
        'M7_result_sha256': digest(m7), 'M8_package_sha256': digest(owned['package']),
        'request_sha256': owned['request_sha256'], 'post_validation': {'overall_status': 'REVIEW_REQUIRED'}}
    base = root / 'data/evals/generation-runner/owned-test-only'
    save(base / 'RESULT.json', row)
    save(base / 'MANIFEST.json', {'schema': 'SYNTHETIC_ONLY', 'mode': 'live',
                                'files': {'RESULT.json': sha(base / 'RESULT.json')}})
    source = {'manifest_path': (base / 'MANIFEST.json').relative_to(root).as_posix(),
        'manifest_sha256': sha(base / 'MANIFEST.json'), 'result_path': (base / 'RESULT.json').relative_to(root).as_posix(),
        'result_sha256': sha(base / 'RESULT.json')}
    calls = []
    class Source:
        def __init__(self):
            self.inventory = {}
        def validate(self, *a):
            calls.append('validate')
            return True
        def check(self):
            calls.append('check')
    class Qualifications:
        def __init__(self, service):
            self.service = service
        def validate(self, response, evidence, result):
            self.service.validate(evidence, result)
            return _assess_metadata(response, {p['evidence']['unit_id']: p['evidence']['verified_parent']
                                               for p in evidence['parents']})
    service = Source()
    monkeypatch.setattr(workflow, 'trust_check', lambda *a: ({}, {}, {}))
    monkeypatch.setattr(workflow, 'live_context', lambda *a: (service, owned['package'], m7))
    monkeypatch.setattr('tools.generation.qualifications.QualificationValidator', Qualifications)
    manifest = workflow.prepare(root, source=source, question=owned['question'],
        assessment=review(owned, method='ASSISTANT_ANALYSIS', independent_of_generator=False),
        trust={'path': 'SYNTHETIC', 'sha256': '0' * 64})
    p, _, h = workflow.load_package(root, manifest)
    return {'root': root, 'manifest': manifest, 'sha': h, 'package': p, 'row': row,
            'source': service, 'calls': calls}

