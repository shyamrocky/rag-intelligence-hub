from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "apps/master_dashboard/expanded.py"


def launch():
    return AppTest.from_file(str(APP), default_timeout=45).run()


def control(app, name):
    return next(s for s in app.selectbox if s.label == name)


def test_navigation_and_preserved_explorer():
    app = launch()
    assert not app.exception
    assert any(m.label == "Reconciled questions" and m.value == "34" for m in app.metric)
    app.switch_page("views/explorer.py").run()
    assert not app.exception
    assert "RAG Retrieval Pipeline Explorer" in str(app.get("iframe")[0].proto)


def test_filters_shared_question_and_unsupported():
    app = launch().switch_page("views/expanded_quality.py").run()
    assert not app.exception
    assert len(control(app, "Shared question").options) == 34
    control(app, "Cohort").select("Abstention").run()
    assert not app.exception
    assert len(control(app, "Shared question").options) == 3
    assert len(app.tabs) == 3
    cohort = "Abstention — Test correct unsupported-question handling"
    assert sum(c.value == cohort for c in app.caption) >= 4
    assert any("no positive-group" in i.value for i in app.info)
    assert any("NOT_MEASURED" in i.value for i in app.info)
    assert any("ABSTAINED" in w.value for w in app.warning)
    assert not any("correct abstention: PASS" in c.value for c in app.caption)
    control(app, "Generation status").select("COMPLETED").run()
    assert not app.exception and any("No questions match" in i.value for i in app.info)


def test_actual_q05_generation_and_indeterminate():
    app = launch().switch_page("views/expanded_quality.py").run()
    control(app, "Generation status").select("COMPLETED").run()
    assert not app.exception
    assert len(control(app, "Shared question").options) == 1
    assert app.session_state["expanded_question"] == "M9-Q05"
    assert any("LlamaIndex introduction names" in t.value for t in app.text)
    assert any("INDETERMINATE" in str(x.value) or "UNDETERMINED" in str(x.value) for x in app.warning)
    assert any(m.label == "Cited-Parent Utilization" and "1/17" in m.value for m in app.metric)


def test_remaining_historical_m8_and_safe_links():
    app = launch().switch_page("views/expanded_quality.py").run()
    control(app, "Cohort").select("Original Remaining").run()
    assert not app.exception and len(control(app, "Shared question").options) == 16
    assert any("NOT_MEASURED" in i.value for i in app.info)
    assert control(app, "Historical M8 measurement").options
    assert any("INSUFFICIENT RELEVANCE LABELS" in w.value for w in app.warning)
    app.query_params["artifact"] = "../../.env"
    app.run()
    assert not app.exception and any("unknown artifact reference" in w.value for w in app.warning)


def test_historical_15_dashboard_still_replays():
    app = AppTest.from_file(str(ROOT/"apps/master_dashboard/app.py"), default_timeout=30).run()
    app.switch_page("views/quality.py").run()
    assert not app.exception
    assert len(control(app, "Shared question").options) == 15
