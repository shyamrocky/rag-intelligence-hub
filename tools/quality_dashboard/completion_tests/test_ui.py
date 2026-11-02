from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "apps/master_dashboard/coverage.py"


def control(app, label):
    return next(s for s in app.selectbox if s.label == label)


def test_current_navigation_and_explorer():
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception
    assert app.session_state["expanded_data"]["summary"]["M8_target_evaluated_questions"] == 34
    app.switch_page("views/explorer.py").run()
    assert not app.exception
    assert "RAG Retrieval Pipeline Explorer" in str(app.get("iframe")[0].proto)


def test_completed_remaining_and_unsupported():
    app = (
        AppTest.from_file(str(APP), default_timeout=60)
        .run()
        .switch_page("views/coverage_quality.py")
        .run()
    )
    assert not app.exception
    assert len(control(app, "Shared question").options) == 34
    control(app, "Cohort").select("Original Remaining").run()
    assert not app.exception and len(control(app, "Shared question").options) == 16
    assert not any("NOT_MEASURED" in x.value for x in app.info)
    control(app, "Cohort").select("Abstention").run()
    assert not app.exception
    assert any("no positive-group recall denominator" in x.value for x in app.info)
    assert len(control(app, "Shared question").options) == 3
    assert any("NOT_RUN" in x.value for x in app.info)
    assert any("INSUFFICIENT RELEVANCE LABELS" in x.value for x in app.warning)


def test_q05_preserved_and_all_target_filter():
    app = (
        AppTest.from_file(str(APP), default_timeout=60)
        .run()
        .switch_page("views/coverage_quality.py")
        .run()
    )
    control(app, "Evaluation availability").select("Target M8 available").run()
    assert not app.exception and len(control(app, "Shared question").options) == 34
    control(app, "Generation status").select("COMPLETED").run()
    assert not app.exception and app.session_state["expanded_question"] == "M9-Q05"
    assert any("LlamaIndex introduction names" in x.value for x in app.text)
    assert any("UNDETERMINED" in x.value or "INDETERMINATE" in x.value for x in app.warning)
    assert any(x.label == "Cited-Parent Utilization" and "1/17" in x.value for x in app.metric)
