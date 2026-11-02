"""Actual measured M9 UI, bounded navigation and all original inspection behavior."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
DURABLE = 'config/retrieval-chunks-m3-durable-v1.json'


def panel(selector=DURABLE):
    script = ('from pathlib import Path\nfrom rag_hub.m9_dashboard import render\n'
              f'render(Path({str(ROOT)!r}),selector={selector!r})\n')
    return AppTest.from_string(script, default_timeout=180).run()


def test_evaluation_opt_in_no_raw_evidence_or_generation():
    app = panel()
    assert not app.exception and not app.dataframe
    assert app.checkbox(key='m9_enabled').value is False
    assert not any('Authorized source content' == s.value for s in app.subheader)


def test_historical_mode_does_not_mix_current_evaluation():
    app = panel('config/retrieval-chunks-v2.json')
    assert not app.exception and not app.checkbox
    assert any('Historical inspection' in x.value for x in app.info)


def test_measured_comparison_and_token_budget_tables():
    app = panel()
    app.checkbox(key='m9_enabled').check().run()
    assert not app.exception and not app.error
    assert any('29 owner-approved' in x.value for x in app.info)
    assert any('Recall@10' in frame.value.columns for frame in app.dataframe)
    assert any('Mean exact tokens' in frame.value.columns for frame in app.dataframe)
    assert any('answerable_questions' in frame.value.columns for frame in app.dataframe)
    assert any('Source-authored' in str(x.value) or 'source-authored' in str(x.value) for x in app.info)
    assert any('Chunk-size comparison PENDING' in x.value for x in app.warning)


def test_Q21_all_scenarios_reference_fit_and_native_omissions():
    app = panel()
    app.checkbox(key='m9_enabled').check().run()
    app.selectbox(key='m9_question').set_value('M9-Q21').run()
    for budget in (4000, 8000, 16000, 32000):
        app.selectbox(key='m9_scenario').set_value(budget).run()
        assert not app.exception and not app.error
    assert any('Shortformer' in str(x.value) for x in app.markdown)
    assert any('NOT retrieval performance' in x.label for x in app.expander)
    assert any({'unit_id','token_count','reason'} <= set(f.value.columns) for f in app.dataframe)


def test_unsupported_controls_not_presented_as_answered():
    app = panel()
    app.checkbox(key='m9_enabled').check().run()
    app.selectbox(key='m9_question').set_value('M9-Q27').run()
    assert not app.exception
    assert any('UNANSWERABLE' in x.value for x in app.caption)
    rows = [f.value for f in app.dataframe if 'Outcome' in f.value.columns]
    assert len(rows) == 1
    assert all(x == 'UNSUPPORTED_CONTROL_NOT_ANSWER_EVIDENCE' for x in rows[0]['Outcome'])


def test_links_use_existing_parent_inspector():
    app = panel()
    app.checkbox(key='m9_enabled').check().run()
    first = next(b for b in app.button if b.key.startswith('m9_parent_'))
    expected = first.key.removeprefix('m9_parent_')
    first.click().run()
    assert not app.exception
    assert app.session_state['view'] == 'Chunk Inspector'
    assert app.session_state['chunk_entered'] == expected


def test_actual_app_M9_to_existing_M7_and_live_parent_navigation():
    app = AppTest.from_file(str(ROOT / 'apps/ingestion_dashboard/app.py'), default_timeout=240)
    app.session_state['operational_release'] = DURABLE
    app.run()
    app.checkbox(key='m9_enabled').check().run()
    assert not app.exception and not app.error
    app.button(key='m9_to_m7').click().run()
    assert not app.exception
    assert app.text_input(key='m7_query').value
    assert 'm7_result' not in app.session_state  # Copying a question never executes a search.
    first = next(b for b in app.button if b.key.startswith('m9_parent_'))
    first.click().run()
    assert not app.exception and not app.error
    assert any(s.value == 'Complete authorized parent' for s in app.subheader)
