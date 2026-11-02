"""Discard bookkeeping preserves the immutable failed local result and locks."""
import json
from uuid import uuid4

import pytest

pytest.importorskip('tools')
pytest.importorskip('httpx')

from tools.bot_runtime import disposition, projection, store
from tools.generation_runner import bot_flow, bot_runtime
from tools.quality_dashboard.artifacts import ArtifactError


@pytest.fixture
def failed(tmp_path,monkeypatch):
    monkeypatch.setattr('tools.bot_runtime.trust.verify_implementation',lambda root:{'path':'OWNED','sha256':'a'*64,'generation_authority':False})
    q=store.register(tmp_path,'Owned failed local request.',uuid4().hex)
    def stop(*a,**kw):raise ValueError('m7_owned_failure')
    monkeypatch.setattr(bot_runtime,'local_services',stop)
    run=bot_runtime.execute(tmp_path,q['question_id'],mode='local-check')
    manifest=(run/'MANIFEST.json').relative_to(tmp_path).as_posix()
    before={p:p.read_bytes() for p in run.rglob('*') if p.is_file()}
    disposition.discard(tmp_path,q['question_id'],manifest,owner_statement='SYNTHETIC OWNER — DISCARD ONLY',reason='Owned failed local diagnostic.')
    return tmp_path,q,run,before


def test_discard_preserves_failure_and_does_not_unlock(failed):
    root,q,run,before=failed
    assert before=={p:p.read_bytes() for p in run.rglob('*') if p.is_file()}
    x=projection.discover(root);record=x['records'][q['question_id']]
    assert not x['rejected'] and record['disposition']=='DISCARDED'
    assert record['attempts'][0]['execution_status']=='FAILED'
    assert bot_flow.prepare_next(root,q['question_id'],'workspace/not-created')=={'status':'DISCARDED','stage':'none'}
    with pytest.raises(FileExistsError):bot_runtime.execute(root,q['question_id'],mode='local-check')
    assert not list(root.rglob('LIVE_ATTEMPT.json'))


def test_duplicate_disposition_cannot_overwrite(failed):
    root,q,run,_=failed
    with pytest.raises(ArtifactError,match='ALREADY_RECORDED'):
        disposition.discard(root,q['question_id'],(run/'MANIFEST.json').relative_to(root).as_posix(),owner_statement='SYNTHETIC',reason='Duplicate')


@pytest.mark.parametrize('change',['decision','source','question'])
def test_tampered_disposition_is_not_active_or_accepted(failed,change):
    root,q,run,_=failed
    if change=='source':(run/'RESULT.json').write_text('{}')
    else:
        path=root/disposition.BASE/q['question_id']/'DISPOSITION.json'
        value=json.loads(path.read_text());value['status' if change=='decision' else 'question_id']='WRONG'
        path.write_text(json.dumps(value))
    x=projection.discover(root)
    assert x['rejected'] and x['records'][q['question_id']]['disposition']=='UNVERIFIED_DISPOSITION'
    with pytest.raises((ArtifactError,KeyError)):disposition.read(root,q['question_id'])


def test_discarded_ui_history_is_explicit_and_refresh_read_only(failed,monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest

    from apps.knowledge_preparation import bot_live, bot_records
    root,q,_,_=failed
    monkeypatch.setattr(bot_records,'ROOT',root);monkeypatch.setattr(bot_live,'ROOT',root)
    app=AppTest.from_string('from apps.knowledge_preparation.bot_records import render\nrender("Generation")').run()
    assert not app.exception and not app.selectbox
    next(c for c in app.checkbox if c.label=='Show discarded questions').check().run()
    assert not app.exception
    assert 'Discarded' in next(s for s in app.selectbox if s.label=='Bot question').options[0]
    assert any('DISCARDED' in w.value for w in app.warning)
    app.run();assert not app.exception
    live=AppTest.from_string('from apps.knowledge_preparation.bot_live import render\nrender(active="'+q['question_id']+'")').run()
    assert not live.exception and not live.button and not live.form
    assert any('DISCARDED' in i.value for i in live.info)
