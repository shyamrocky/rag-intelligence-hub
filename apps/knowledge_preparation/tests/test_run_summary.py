"""Read-only overview, actual existing adapters and bounded native table height."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import human_review, post_generation
from apps.knowledge_preparation import run_summary as view
from apps.knowledge_preparation.generation import ROOT, load
from apps.knowledge_preparation.tests.test_generation import offline  # noqa: F401
from tools.bot_runtime.projection import discover


def event(stage, status, ms=None):
    return {'stage': stage, 'operation': stage, 'status': status, 'duration_ms': ms}


def test_nested_trace_accounting_is_exclusive():
    stages = view.trace_stages([
        event('PROMPT_ASSEMBLY','RUNNING'), event('M8_SOURCE_VALIDATION','RUNNING'),
        event('M8_EVIDENCE_ASSEMBLY','RUNNING'), event('M8_EVIDENCE_ASSEMBLY','COMPLETED',20),
        event('M8_SOURCE_VALIDATION','COMPLETED',25), event('PROMPT_ASSEMBLY','COMPLETED',40)])
    result = view.phase_times(stages)
    assert result == {'Context assembly':25, 'Pre-generation':15, 'Generation':None}


@pytest.mark.parametrize('events', [
    [event('PROMPT_ASSEMBLY','RUNNING')],
    [event('PROMPT_ASSEMBLY','COMPLETED',10)],
    [event('PROMPT_ASSEMBLY','RUNNING'), event('LLM_GENERATION','COMPLETED',10)],
    [event('PROMPT_ASSEMBLY','RUNNING'),event('M8_EVIDENCE_ASSEMBLY','RUNNING'),
     event('M8_EVIDENCE_ASSEMBLY','COMPLETED',20),event('PROMPT_ASSEMBLY','COMPLETED',10)]])
def test_incomplete_or_invalid_timing_cannot_become_zero_or_a_total(events):
    with pytest.raises(ValueError):
        view.trace_stages(events)


def test_stage_receipt_inclusive_values_are_never_added():
    stages = [{'stage':'PROMPT_ASSEMBLY','duration_ms':10,'inclusive_ms':100},
              {'stage':'M8_EVIDENCE_ASSEMBLY','duration_ms':90,'inclusive_ms':90}]
    result = view.phase_times(stages)
    assert result['Context assembly'] == 90 and result['Pre-generation'] == 10
    assert result['Generation'] is None
    assert view.duration(None) == 'Not measured'
    assert view.duration(18647) == '18.65s'
    assert view.duration(513224) == '8m 33.22s'


def test_other_processing_reconciles_unrounded_same_scope_timings():
    phases = {'Context assembly': 155130, 'Pre-generation': 29920, 'Generation': 18650}
    remainder = view.other_processing(phases, 513220)
    assert remainder == 309520
    assert sum(phases.values()) + remainder == 513220
    assert view.duration(remainder) == '5m 09.52s'
    assert view.other_processing(phases, sum(phases.values())) == 0


@pytest.mark.parametrize('phases,total', [
    ({'Context assembly': None, 'Pre-generation': 10, 'Generation': 20}, 100),
    ({'Context assembly': 10, 'Pre-generation': 20, 'Generation': None}, 100),
    ({'Context assembly': 10, 'Pre-generation': 20, 'Generation': 30}, None)])
def test_other_processing_missing_measurements_remain_unavailable(phases, total):
    assert view.other_processing(phases, total) is None


@pytest.mark.parametrize('phases,total', [
    ({'Context assembly': 100, 'Pre-generation': 20, 'Generation': 30}, 100),
    ({'Context assembly': float('nan'), 'Pre-generation': 20, 'Generation': 30}, 100),
    ({'Context assembly': -10, 'Pre-generation': 20, 'Generation': 30}, 100)])
def test_other_processing_invalid_measurements_cannot_become_a_remainder(phases, total):
    with pytest.raises(ValueError):
        view.other_processing(phases, total)


def test_missing_measurements_cost_and_unrun_questions_remain_explicit():
    record = {'question':'An owned question?', 'question_id':'BOT-999999'}
    row = view.overview_row(ROOT,'BOT-999999',record,None,source='Bot')
    assert row['Total runtime'] == row['Context assembly'] == 'Not measured'
    assert row['Other processing'] == 'Not measured'
    assert row['Cost (USD)'] is None and row['Model status'] == 'NOT_RUN'


def test_mock_and_discarded_records_are_not_real_answers_or_approvals():
    attempt = {'mode':'mock','execution_status':'COMPLETED','response':{'status':'ABSTAINED',
        'answer':'','missing_information':['Owned evidence unavailable.']},'model_status':'ABSTAINED',
        'cost_usd':'0.02','owner_review_status':'OWNER_APPROVED_POC'}
    record = {'question':'Owned?', 'question_id':'BOT-999999','disposition':'DISCARDED'}
    row = view.overview_row(ROOT,'BOT-999999',record,attempt,source='Bot')
    assert row['Cost (USD)'] is None and 'SIMULATION' in row['Human Review']
    assert 'DISCARDED' in row['Execution'] and 'MOCK' in row['Execution']
    assert row['Answer preview'] == 'Owned evidence unavailable.'


@pytest.fixture(scope='module')
def current():
    data, tracker = load()
    bots = discover(ROOT)
    rows, unavailable = view.rows(ROOT,data,tracker,bots)
    assert not unavailable
    return data,tracker,bots,rows


def test_actual_latest_attempts_rejections_and_known_history_are_preserved(current):
    data,_,bots,rows = current
    assert len(rows) == len(data['records']) + len(bots['records'])
    assert len({r['Question'].split(' — ')[0] for r in rows}) == len(rows)
    find = lambda q: next(r for r in rows if r['Question'].startswith(q+' — '))
    assert find('M9-Q04')['Human Review'] == 'OWNER_APPROVED_POC'
    assert find('R03')['Human Review'] == 'COMPLETENESS_ACCEPTED / GROUNDING_REVIEW_REQUIRED'
    assert find('M9-Q05')['Total runtime'] == 'Not measured'
    assert find('M9-Q05')['Other processing'] == 'Not measured'
    assert 'Unaccepted response' in find('M9-Q18')['Answer preview']
    assert 'DIAGNOSTIC' in find('M9-Q18')['Human Review']
    assert 'DISCARDED' in find('BOT-000003')['Execution']
    assert find('BOT-000006')['Total runtime'] == '8m 33.22s · full request'
    assert find('BOT-000006')['Other processing'] == '5m 09.52s'
    assert 'Unaccepted response' in find('BOT-000007')['Answer preview']
    assert find('BOT-000007')['Cost (USD)'] == pytest.approx(.00921105)
    assert find('BOT-000007')['Technical validation'] == 'VALIDATION_FAILED'


def test_unsealed_dispatch_cannot_replace_native_runner_total(current, monkeypatch):
    _,_,bots,_ = current
    record=bots['records']['BOT-000006'];attempt=record['attempts'][-1]
    original=view.traces_for
    def unsealed(*args,**kwargs):
        result=deepcopy(original(*args,**kwargs))
        for trace in result['traces']:
            if trace['mode']=='chat':trace['observation']='UNSEALED_PROGRESS_NOT_COMPLETION_AUTHORITY'
        return result
    monkeypatch.setattr(view,'traces_for',unsealed)
    _,total,scope=view.request_timing(ROOT,record,attempt)
    assert scope=='runner'
    assert total==attempt['timings']['end_to_end_ms'] and total<513224


@pytest.mark.parametrize('route,key', [('post-generation-evaluation-human-review','post-overview'),
                                      ('human-review','review-overview')])
def test_first_table_is_scrollable_and_identical_on_both_pages(current,monkeypatch,route,key):
    data,tracker,bots,rows=current
    monkeypatch.setattr(post_generation,'load',lambda:(data,tracker))
    monkeypatch.setattr(human_review,'load',lambda:(data,tracker))
    monkeypatch.setattr(view,'load_bots',lambda root:bots)
    app=AppTest.from_file(str(ROOT/'apps/knowledge_preparation/app.py'),default_timeout=120)
    app._page_hash=calc_hash(route);app.run()
    assert not app.exception
    table=app.dataframe[0]
    assert len(table.value)==len(rows) and table.proto.row_height==35
    assert 'Cost (USD)' in table.value and 'Technical validation' in table.value
    assert 'Other processing' in table.value
    assert list(table.value.columns).index('Other processing') + 1 == list(table.value.columns).index('Total runtime')
    assert list(table.value['Other processing']) == [r['Other processing'] for r in rows]
    assert list(table.value['Question'])==[r['Question'] for r in rows]
    labels=[getattr(e,'type','') for e in app.main]
    assert labels.index('dataframe')<labels.index('radio')
    app.selectbox(key=key+'-source').set_value('Bot').run()
    assert not app.exception
    assert len(app.dataframe[0].value)==len(bots['records'])
    app.run()
    assert not app.exception and len(app.dataframe[0].value)==len(bots['records'])
    # Details remain available, with the same source/review controls as before.
    radio=next(r for r in app.radio if r.label=='Question source')
    radio.set_value('Bot questions').run()
    assert not app.exception
    assert any(s.label=='Bot question' for s in app.selectbox)
    assert len(app.dataframe[0].value)==len(bots['records'])


def test_untrusted_row_fails_closed_without_hiding_the_question(monkeypatch):
    record={'question':'Owned pending question','attempts':[{'created_at':'owned'}]}
    bots={'records':{'BOT-999999':record}}
    monkeypatch.setattr(view,'overview_row',lambda *a,**kw: (_ for _ in ()).throw(ValueError('tampered'))
                        if a[3] is not None else {'Question':'BOT-999999 — Owned pending question'})
    rows,unavailable=view.rows(ROOT,{'records':{}},{'rows':[]},bots)
    assert unavailable==1 and len(rows)==1
    assert rows[0]['Execution']=='UNAVAILABLE — UNVERIFIED'
    assert rows[0]['Human Review']=='UNVERIFIED'
