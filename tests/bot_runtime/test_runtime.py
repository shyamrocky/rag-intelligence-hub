"""Owned full source path; all external access forbidden, no real corpus operations."""
import socket
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

pytest.importorskip('tools', reason='Requires explicit project PYTHONPATH; use documented Bot test command')
pytest.importorskip('httpx', reason='Requires the existing generation test environment')

from tools.bot_runtime import projection, store
from tools.generation_runner import bot_runtime


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*a, **kw):
        raise AssertionError('UNAUTHORIZED_EXTERNAL_OPERATION')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr('tools.generation.openai_adapter.OpenAIAdapter.__init__', denied)
    monkeypatch.setattr('tools.preflight_suite.provider.load_key', denied)
    monkeypatch.setattr('tools.bot_runtime.trust.verify_implementation', lambda root: {'path': 'OWNED_FIXTURE', 'sha256': 'a' * 64, 'generation_authority': False})


def question(root, text='How does retrieval work?'):
    return store.register(root, text, uuid4().hex)


def test_ids_nonce_concurrency_and_restart(tmp_path):
    nonce = uuid4().hex
    q = store.register(tmp_path, '  What is RAG?\n', nonce)
    assert q['question'] == 'What is RAG?'
    assert store.register(tmp_path, '  What is RAG?\n', nonce) == q
    with pytest.raises(ValueError):
        store.register(tmp_path, 'Different question', nonce)
    with ThreadPoolExecutor(4) as workers:
        ids = list(workers.map(lambda i: question(tmp_path, f'Question {i}')['question_id'], range(8)))
    assert len(set(ids)) == 8
    assert question(tmp_path)['question_id'] == 'BOT-000010'
    assert q['mandatory_evidence_group_ids'] is None and not q['offline_evaluation_eligible']
    assert (tmp_path / store.QUESTIONS / q['question_id'] / 'QUESTION.json').stat().st_mode & 0o077 == 0


@pytest.mark.parametrize('scenario,execution,status,contract', [
    ('answered', 'COMPLETED', 'ANSWERED', 'ACCEPTED'),
    ('partial', 'COMPLETED', 'PARTIAL', 'ACCEPTED'),
    ('abstained', 'COMPLETED', 'ABSTAINED', 'ACCEPTED'),
    ('schema-error', 'FAILED', None, 'REJECTED'),
    ('api-failure', 'FAILED', None, 'REJECTED'),
    ('empty-evidence', 'BLOCKED', None, 'NOT_RUN'),
])
def test_native_offline_end_to_end(tmp_path, scenario, execution, status, contract):
    qid = question(tmp_path)['question_id']
    run = bot_runtime.execute(tmp_path, qid, mode='mock', scenario=scenario)
    row = store.read(run / 'RESULT.json')
    assert (row['execution_status'], row['model_status'], row['response_contract_status']) == (execution, status, contract), row
    data = projection.discover(tmp_path)
    assert not data['rejected'], data['rejected']
    assert len(data['records'][qid]['attempts']) == 1
    assert data['summary']['real_generation_requests'] == 0
    assert row['provider_calls'] == row['generation_calls'] == 0
    assert not row['generation_executed'] and row['cost_usd'] is None
    assert row['source_integrity'] == 'OWNED_SYNTHETIC_NOT_SOURCE_AUTHORITY'
    if status:
        assert row['validation_status'] == 'REVIEW_REQUIRED'
        assert not row['post_validation']['fully_validated']
    if scenario == 'empty-evidence':
        assert row['application_outcome'] == 'INSUFFICIENT_EVIDENCE'
        assert not list(run.rglob('*ATTEMPT.json'))
    assert not list(tmp_path.rglob('LIVE_ATTEMPT.json'))
    with pytest.raises(FileExistsError):
        bot_runtime.execute(tmp_path, qid, mode='mock')


def test_live_and_unknown_modes_block_before_writes(tmp_path):
    for mode in ['live', 'model-preflight', 'LIVE']:
        with pytest.raises(ValueError, match='BOT_LIVE_REQUIRES'):
            bot_runtime.execute(tmp_path, 'BOT-000001', mode=mode)
    assert list(tmp_path.iterdir()) == []


def test_local_check_uses_public_search_and_no_provider(tmp_path, monkeypatch):
    q = question(tmp_path)
    from tools.generation_runner.bot_fixture import boundaries
    candidates, evidence = boundaries(q['question'], 'answered')
    calls = []
    class Retrieval:
        def _request(self, kind, request):
            calls.append(kind)
            return {'result': [{'chunk_id': 'owned', 'rank': 1}]}
        def search(self, query, **kwargs):
            assert query == q['question'] and kwargs == {'mode': 'hybrid', 'top_k': 30, 'candidate_depth': 50, 'rrf_k': 60}
            self._request('bm25', {})
            self._request('vector', {})
            return candidates
        def check(self):
            calls.append('check')
        def close(self):
            calls.append('close')
    monkeypatch.setattr(bot_runtime, 'local_services', lambda root: (Retrieval(), evidence))
    run = bot_runtime.execute(tmp_path, q['question_id'], mode='local-check')
    row = store.read(run / 'RESULT.json')
    assert row['execution_status'] == 'AWAITING_AUTHORIZATION', row
    assert row['response'] is None and not row['fixture_only']
    assert store.read(run / 'RETRIEVAL_OBSERVATIONS.json')['status'] == 'MEASURED'
    assert calls == ['bm25', 'vector', 'check', 'close']
    assert not list(tmp_path.rglob('*ATTEMPT.json'))


@pytest.mark.parametrize('file', ['CANDIDATES.json', 'EVIDENCE_PACKAGE.json', 'RESULT.json', 'STAGE_TIMINGS.json', 'LOCAL_VALIDATION.json'])
def test_tampering_rejected(tmp_path, file):
    qid = question(tmp_path)['question_id']
    run = bot_runtime.execute(tmp_path, qid, mode='mock')
    (run / file).write_text('{}')
    data = projection.discover(tmp_path)
    assert data['rejected'] and data['records'][qid]['attempts'] == []


def test_symlinks_and_question_tampering_fail_closed(tmp_path):
    qid = question(tmp_path)['question_id']
    path = tmp_path / store.QUESTIONS / qid / 'QUESTION.json'
    path.write_text('{}')
    with pytest.raises(ValueError):
        store.question_record(tmp_path, qid)
    assert projection.discover(tmp_path)['rejected']
    other = tmp_path / 'other'; other.mkdir()
    (tmp_path / 'bad').symlink_to(other)
    with pytest.raises(ValueError):
        store.directory(tmp_path, 'bad/child')
    assert not (other / 'child').exists()


def test_persistence_failure_is_incomplete_never_replayed(tmp_path, monkeypatch):
    qid = question(tmp_path)['question_id']
    original = bot_runtime.write
    def failing(path, value):
        if path.name == 'RESULT.json':
            raise OSError('PRIVATE_ERROR_BODY')
        return original(path, value)
    monkeypatch.setattr(bot_runtime, 'write', failing)
    with pytest.raises(OSError):
        bot_runtime.execute(tmp_path, qid, mode='mock')
    assert list(tmp_path.rglob('STAGE_TIMINGS.json'))
    value = projection.discover(tmp_path)['records'][qid]['attempts'][0]
    assert value['execution_status'] == 'INCOMPLETE' and value['response'] is None
    with pytest.raises(FileExistsError):
        bot_runtime.execute(tmp_path, qid, mode='mock')


def test_raw_capture_failure_and_tamper(tmp_path, monkeypatch):
    from tools.generation import response_capture
    monkeypatch.setattr(response_capture, '_write', lambda *a: (_ for _ in ()).throw(OSError('private')))
    qid = question(tmp_path)['question_id']
    run = bot_runtime.execute(tmp_path, qid, mode='mock')
    row = store.read(run / 'RESULT.json')
    assert row['audit']['status'] == 'RAW_RESPONSE_CAPTURE_FAILED'
    assert row['raw_capture']['artifact'] is None and row['execution_status'] == 'FAILED'


def test_reconstruction_hashes_repeat_but_run_ids_differ(tmp_path):
    a, b = question(tmp_path), question(tmp_path)
    ar = store.read(bot_runtime.execute(tmp_path, a['question_id'], mode='mock') / 'RESULT.json')
    br = store.read(bot_runtime.execute(tmp_path, b['question_id'], mode='mock') / 'RESULT.json')
    assert ar['run_id'] != br['run_id'] and ar['request_sha256'] == br['request_sha256']
    assert ar['M8_package_sha256'] == br['M8_package_sha256']


def test_mock_and_local_modes_have_separate_claims(tmp_path, monkeypatch):
    q = question(tmp_path)
    from tools.generation_runner.bot_fixture import boundaries
    result, evidence = boundaries(q['question'], 'answered')
    class Retrieval:
        def _request(self, *a):
            return {'result': []}
        def search(self, *a, **kw):
            return result
        def check(self):
            pass
        def close(self):
            pass
    monkeypatch.setattr(bot_runtime, 'local_services', lambda root: (Retrieval(), evidence))
    bot_runtime.execute(tmp_path, q['question_id'], mode='local-check')
    bot_runtime.execute(tmp_path, q['question_id'], mode='mock')
    assert len(projection.discover(tmp_path)['records'][q['question_id']]['attempts']) == 2


def test_capture_body_tampering_rejected(tmp_path):
    qid = question(tmp_path)['question_id']
    run = bot_runtime.execute(tmp_path, qid, mode='mock')
    row = store.read(run / 'RESULT.json')
    (tmp_path / row['raw_capture']['artifact']['path']).write_bytes(b'changed')
    assert projection.discover(tmp_path)['rejected']


def test_byte_level_hashes_do_not_normalize_newlines(tmp_path):
    qid = question(tmp_path)['question_id']
    path = tmp_path / store.QUESTIONS / qid / 'QUESTION.json'
    path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
    with pytest.raises(ValueError):
        store.question_record(tmp_path, qid)
