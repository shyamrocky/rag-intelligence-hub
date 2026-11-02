"""Bot records reach each read-only operational page; simulations cannot approve."""
from uuid import uuid4

import pytest

AppTest = pytest.importorskip('streamlit.testing.v1', reason='Requires existing ingestion UI environment').AppTest
pytest.importorskip('tools', reason='Requires explicit project PYTHONPATH')
pytest.importorskip('httpx', reason='Requires the existing generation test environment')

from tools.bot_runtime import store
from tools.generation_runner.bot_runtime import execute


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr('tools.bot_runtime.trust.verify_implementation', lambda root: {'path': 'OWNED', 'sha256': 'a' * 64, 'generation_authority': False})
    q = store.register(tmp_path, 'Explain owned simulation evidence.', uuid4().hex)
    execute(tmp_path, q['question_id'], mode='mock', scenario='answered')
    return tmp_path


@pytest.mark.parametrize('stage', ['Knowledge Retrieval', 'Pre-Generation', 'Generation', 'Post-Generation Evaluation', 'Human Review'])
def test_all_operational_pages_discover_same_identity(saved, monkeypatch, stage):
    def denied(*a, **kw):
        raise AssertionError('REFRESH_MUST_BE_READ_ONLY')
    monkeypatch.setattr('tools.generation_runner.bot_runtime.execute', denied)
    before = {str(p): p.read_bytes() for p in saved.rglob('*') if p.is_file()}
    script = f'''from apps.knowledge_preparation.bot_records import render
from pathlib import Path
render({stage!r}, root=Path({str(saved)!r}))'''
    app = AppTest.from_string(script).run()
    assert not app.exception, app.exception
    assert app.selectbox[0].value == 'BOT-000001'
    assert any('MOCK' in x.value for x in app.warning)
    if stage == 'Human Review':
        assert all(b.disabled for b in app.button)
    app.run()
    assert not app.exception
    assert before == {str(p): p.read_bytes() for p in saved.rglob('*') if p.is_file()}


def test_question_source_does_not_invoke_benchmark_reader(saved):
    from tools.bot_runtime.projection import workspace
    data = workspace(saved, 'BOT', benchmark_loader=lambda _: (_ for _ in ()).throw(AssertionError('NOT_A_BENCHMARK')))
    assert data['records']['BOT-000001']['reference']['mandatory_evidence_group_ids'] is None
    sentinel = object()
    assert workspace(saved, 'BENCHMARK', benchmark_loader=lambda _: sentinel) is sentinel
