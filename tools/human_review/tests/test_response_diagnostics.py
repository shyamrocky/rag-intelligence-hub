"""Disposable sealed failures; protected output shown only on explicit local inspection."""
import hashlib
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from tools.generation.response_capture import ResponseCapture
from tools.human_review.response_diagnostics import capture_reference, discover
from tools.preflight_suite.artifacts import save, sha
from tools.quality_dashboard.artifacts import digest


def publication(root, *, failed=False, historical=False):
    run=root/'data/evals/generation-runner/owned-run'
    qdir=run/'questions/OWNED-Q'
    row={'question_id':'OWNED-Q','question_sha256':hashlib.sha256(b'Owned?').hexdigest(),
        'request_sha256':'a'*64,'M8_package_sha256':'b'*64,'mode':'live',
        'generation_executed':True,'provider_calls':0,'response':None,
        'status':'RAW_RESPONSE_CAPTURE_FAILED' if failed else 'INVALID_OR_INCOMPLETE_PROVIDER_RESPONSE',
        'audit':{'response_diagnostics':[{'code':'UNAUTHORIZED_EVIDENCE_REFERENCE','path':['claims',0,'evidence_unit_ids',0]}]}}
    if not historical:
        sink=ResponseCapture(root,qdir,question_id='OWNED-Q',run_id='owned-run',
            request_sha256='a'*64,package_sha256='b'*64,mode='live')
        if failed:
            with patch('tools.generation.response_capture._write',side_effect=OSError('Owned disk failure')):
                receipt=sink.capture(b'OWNED-PROTECTED-TEXT',http_status=200)
        else:
            receipt=sink.capture(b'{"output":"OWNED-PROTECTED-TEXT"}',http_status=200)
        row['audit']['raw_response_capture']=receipt
    plan={'owned':True};plan['plan_sha256']=digest(plan)
    save(run/'PLAN.json',plan)
    save(qdir/'RESULT.json',row)
    save(run/'RESULTS.json',{'mode':'live','questions':[row]})
    save(run/'MANIFEST.json',{'schema':'grounded-generation-runner-1.0','status':'SEALED_PENDING_OWNER_REVIEW',
        'run_id':'owned-run','mode':'live','plan_sha256':plan['plan_sha256'],'question_ids':['OWNED-Q'],
        'files':{p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file()}})
    return run


@pytest.mark.parametrize('failed,historical',[(False,False),(True,False),(False,True)])
def test_diagnostic_ui_is_read_only_and_never_approves(tmp_path,failed,historical):
    publication(tmp_path,failed=failed,historical=historical)
    script=tmp_path/'view.py'
    script.write_text('import streamlit as st\nfrom pathlib import Path\nfrom tools.human_review.response_diagnostics import render\nrender(st, Path('+repr(str(tmp_path))+'))\n')
    before={p:sha(p) for p in tmp_path.rglob('*') if p.is_file()}
    def denied(*a,**kw):raise AssertionError('NO_PIPELINE_PROVIDER_OR_APPROVAL_ON_REFRESH')
    with ExitStack() as stack:
        for name in ['tools.evidence.service.EvidenceService.assemble',
                     'tools.generation_runner.runner.execute','tools.generation.openai_adapter.OpenAIAdapter.invoke',
                     'tools.preflight_suite.provider.load_key','tools.human_review.local_poc.decide',
                     'socket.create_connection']:
            stack.enter_context(patch(name,denied))
        stack.enter_context(patch('tools.human_review.local_poc.require_localhost',lambda:None))
        app=AppTest.from_file(str(script)).run()
        assert not app.exception and not app.button
        assert not any('OWNED-PROTECTED-TEXT' in x.value for x in app.code)
        if not failed and not historical:
            app.checkbox[0].check().run()
            assert not app.exception
            assert any('OWNED-PROTECTED-TEXT' in x.value for x in app.code)
        else:
            assert not app.checkbox
            assert any('unavailable' in x.value.lower() for x in [*app.info,*app.warning])
        app.run()
        assert not app.exception
    assert all(sha(p)==h for p,h in before.items())


def test_tampered_raw_body_stays_visible_as_failure_but_is_not_displayable(tmp_path):
    publication(tmp_path)
    entry=discover(tmp_path)[0]
    _,path=capture_reference(tmp_path,entry)
    path.write_bytes(b'changed')
    with pytest.raises(ValueError):capture_reference(tmp_path,entry)
