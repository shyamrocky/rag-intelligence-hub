"""Sealed quality-view discovery, independent of execution services."""
import json

from tools.answer_quality.reporting import discover
from tools.preflight_suite.artifacts import save, sha
from tools.quality_dashboard.artifacts import digest


def publish(root):
    base = root / 'data/evals/answer-quality/owned'
    source = root / 'data/owned-native'
    response = {'owned': True}
    save(source / 'RESULT.json', {'question_id': 'OWNED', 'response': response, 'request_sha256': 'b' * 64})
    save(source / 'MANIFEST.json', {'schema': 'owned-native', 'files': {'RESULT.json': sha(source / 'RESULT.json')}})
    binding = {'manifest_path': 'data/owned-native/MANIFEST.json', 'manifest_sha256': sha(source / 'MANIFEST.json'),
               'result_path': 'data/owned-native/RESULT.json', 'result_sha256': sha(source / 'RESULT.json')}
    value = {'schema': 'post-generation-validation-2.0', 'question_id': 'OWNED',
             'response_sha256': digest(response), 'request_sha256': 'b' * 64}
    save(base / 'ASSESSMENT.json', value)
    manifest = {'schema': 'answer-quality-evaluation-2.0', 'question_id': 'OWNED',
        'response_sha256': digest(response), 'request_sha256': 'b' * 64,
        'response_source': binding, 'files': {'ASSESSMENT.json': sha(base / 'ASSESSMENT.json')}}
    save(base / 'MANIFEST.json', manifest)
    return base


def test_sealed_discovery_only_and_no_cross_response_reuse(tmp_path):
    publish(tmp_path)
    entries, rejected = discover(tmp_path, question_id='OWNED', response_sha256=digest({'owned': True}), request_sha256='b' * 64)
    assert len(entries) == 1 and not rejected
    assert not discover(tmp_path, question_id='OWNED', response_sha256='c' * 64, request_sha256='b' * 64)[0]


def test_unsealed_and_tampered_evaluation_rejected(tmp_path):
    base = publish(tmp_path)
    (base / 'ASSESSMENT.json').write_text('{}')
    entries, rejected = discover(tmp_path, question_id='OWNED', response_sha256=digest({'owned': True}), request_sha256='b' * 64)
    assert not entries and rejected == ['owned']


def test_path_traversal_not_read(tmp_path):
    base = publish(tmp_path)
    p = base / 'MANIFEST.json'
    value = json.loads(p.read_text()); value['files'] = {'../../../../secrets.toml': 'a' * 64}
    p.write_text(json.dumps(value))
    assert discover(tmp_path, question_id='OWNED', response_sha256=digest({'owned': True}), request_sha256='b' * 64)[1]
