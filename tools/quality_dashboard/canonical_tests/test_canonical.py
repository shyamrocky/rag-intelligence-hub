"""Canonical launch integration using sealed data; every execution path forbidden."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'apps/master_dashboard/canonical.py'


def forbidden(*args, **kwargs):
    raise AssertionError('CANONICAL_DASHBOARD_MUST_REMAIN_READ_ONLY')


@pytest.fixture(autouse=True)
def read_only(monkeypatch):
    import importlib.abc
    import socket
    import sys

    from tools.evidence.service import EvidenceService
    from tools.generation.current import GenerationService
    from tools.generation.openai_adapter import OpenAIAdapter
    from tools.pre_generation_gate.current import PromptAssemblyGate
    from tools.preflight_suite import runner
    from tools.quality_dashboard.post_generation import PostGenerationValidator
    from tools.retrieval.service import RetrievalService

    for cls, methods in [
        (EvidenceService, ['assemble', 'validate']),
        (RetrievalService, ['search']),
        (GenerationService, ['dry_run', 'generate']),
        (OpenAIAdapter, ['configuration_error', '_sdk', 'verify_model', 'count', 'invoke']),
        (PromptAssemblyGate, ['prepare']),
        (PostGenerationValidator, ['validate']),
    ]:
        for method in methods:
            monkeypatch.setattr(cls, method, forbidden)
    monkeypatch.setattr(runner, 'execute', forbidden)
    class NoProviderImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in {'tools.preflight_suite.provider', 'openai', 'httpx'}:
                forbidden()

    monkeypatch.setattr(sys, 'meta_path', [NoProviderImports(), *sys.meta_path])
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


def launch():
    return AppTest.from_file(str(APP), default_timeout=90).run()


def control(app, label):
    return next(x for x in app.selectbox if x.label == label)


def test_navigation_all_capabilities_and_inert_refresh():
    app = launch()
    assert not app.exception
    data = app.session_state['expanded_data']
    assert len(data['records']) == 34
    assert data['summary']['mandatory_groups'] == 40
    assert data['summary']['generation_completed'] == 1
    assert data['summary']['M8_target_evaluated_questions'] == 34
    assert any(x.label == 'RAG Preflight Suite' for x in app.get('page_link'))
    next(b for b in app.button if b.label == 'Refresh verified telemetry').click().run()
    assert not app.exception
    app.switch_page('views/explorer.py').run()
    assert not app.exception
    assert 'RAG Retrieval Pipeline Explorer' in str(app.get('iframe')[0].proto)
    app.switch_page('views/preflight_quality.py').run()
    assert not app.exception and len(control(app, 'Shared question').options) == 34
    assert [t.label for t in app.tabs] == ['Retrieval Pipeline Telemetry',
        'Generation — Output & Telemetry', 'Post-Generation Validation']
    app.switch_page('views/preflight_suite.py').run()
    assert not app.exception
    assert len(control(app, 'Preflight question').options) == 33


def test_cohort_filters_shared_question_and_historical_comparisons():
    app = launch().switch_page('views/preflight_quality.py').run()
    assert not app.exception
    for label, count in [('Original Difficult', 10), ('NLP', 5), ('Original Remaining', 16), ('Abstention', 3)]:
        control(app, 'Cohort').select(label).run()
        assert not app.exception and len(control(app, 'Shared question').options) == count
    assert any('no positive-group recall denominator' in i.value for i in app.info)
    assert any('INSUFFICIENT RELEVANCE LABELS' in w.value for w in app.warning)
    control(app, 'Cohort').select('NLP').run()
    control(app, 'Shared question').select('R03').run()
    assert app.session_state['expanded_question'] == 'R03'
    app.switch_page('views/preflight_suite.py').run()
    assert not app.exception and control(app, 'Preflight question').value == 'R03'
    runs = app.session_state['preflight_telemetry']['runs']
    assert {r['manifest']['mode'] for r in runs} == {'local-check', 'model-preflight'}
    frozen = app.session_state['expanded_data']['frozen_data']
    assert frozen['selection_comparison'] and frozen['budget_comparison']
    assert frozen['original_m9']['summary']


def test_real_q05_answer_usage_cost_and_qualification_caveat():
    app = launch().switch_page('views/preflight_quality.py').run()
    control(app, 'Generation status').select('COMPLETED').run()
    assert not app.exception
    assert app.session_state['expanded_question'] == 'M9-Q05'
    row = app.session_state['expanded_data']['records']['M9-Q05']
    attempt = row['latest']
    assert attempt['response']['status'] == 'ANSWERED'
    usage = attempt['usage']
    assert (usage['input_tokens'], usage['output_tokens'], usage['total_tokens']) == (86200, 848, 87048)
    assert usage['total_estimated_cost_usd'] == '0.011198925'
    assert usage['latency_ms'] == pytest.approx(8336.271291947924)
    assert len(attempt['response']['claims']) == 2 and len(attempt['cited_parent_ids']) == 1
    assert attempt['supplied_parents'] == 17
    assert any('LlamaIndex introduction names' in x.value for x in app.text)
    assert any('UNDETERMINED' in x.value or 'INDETERMINATE' in x.value for x in app.warning)
    assert any(m.label == 'Cited-Parent Utilization' and '1/17' in m.value for m in app.metric)
    assert any({'Metric', 'Value'}.issubset(d.value.columns) and
               '0.011198925' in set(d.value['Value'].astype(str)) for d in app.dataframe)


def test_all33_preflight_results_versions_readiness_and_cost():
    app = launch().switch_page('views/preflight_suite.py').run()
    assert not app.exception
    runs = app.session_state['preflight_telemetry']['runs']
    assert not app.session_state['preflight_telemetry']['rejected']
    for run in runs:
        assert len(run['results']['questions']) == 33
        assert len({r['question_id'] for r in run['results']['questions']}) == 33
        assert 'M9-Q05' not in run['manifest']['question_ids']
    local = next(r for r in runs if r['manifest']['mode'] == 'local-check')
    model = next(r for r in runs if r['manifest']['mode'] == 'model-preflight')
    assert local['results']['summary']['local_validated'] == 33
    assert local['results']['summary']['model_qualified'] == 0
    assert model['results']['summary']['model_qualified'] == 33
    assert model['results']['summary']['exact_input_tokens'] == 2786900
    assert model['results']['summary']['aggregate_maximum_estimated_cost_usd'] == '0.76430900'
    control(app, 'Preflight run').select(runs.index(local)).run()
    assert not app.exception and any('Provider stages SKIPPED' in x.value for x in app.info)
    control(app, 'Preflight run').select(runs.index(model)).run()
    assert not app.exception and any('Generation endpoints denied' in x.value for x in app.info)
    assert len(control(app, 'Preflight question').options) == 33
    assert not any(b.label in {'Execute', 'Run', 'Generate', 'Model preflight'} for b in app.button)
    for r in model['results']['questions']:
        assert r['status'] == 'MODEL_QUALIFIED' and not r['generation_executed']
        assert r['prompt_version'] == 'grounded-generation-prompt-v2.1'
        assert r['schema_version'] == 'grounded-response-2.0'
    next(b for b in app.button if b.label == 'Refresh verified telemetry').click().run()
    assert not app.exception


def test_unsafe_artifact_link_still_rejected():
    app = launch()
    app.query_params['artifact'] = '../../.env'
    app.run()
    assert not app.exception
    assert any('unknown artifact reference' in x.value for x in app.warning)
