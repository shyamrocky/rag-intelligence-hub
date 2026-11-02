"""Real Streamlit AppTest interactions; browser visual checks are recorded separately."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "apps/master_dashboard/app.py"


def test_master_navigation_and_explorer():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "RAG Intelligence Hub"
    assert len(app.page_link) == 2
    app.switch_page("views/explorer.py").run()
    assert not app.exception
    assert app.title[0].value == "Candidate–Parent Explorer"
    assert "RAG Retrieval Pipeline Explorer" in str(app.get("iframe")[0].proto)


def test_shared_question_and_real_generation():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.switch_page("views/quality.py").run()
    assert not app.exception
    assert len(app.selectbox[0].options) == 15
    app.selectbox[0].select("M9-Q05").run()
    assert not app.exception
    assert len(app.tabs) == 3
    assert any("five stages" in text.value for text in app.text)
    assert any(m.label == "Cited-Parent Utilization" and "1/17" in m.value for m in app.metric)
    assert any("INSUFFICIENT RELEVANCE LABELS" in w.value for w in app.warning)
    assert "source_content" not in " ".join(t.value for t in app.text)
    app.selectbox[0].select("R03").run()
    assert not app.exception
    assert any("NOT_RUN" in i.value for i in app.info)
    assert not any("The LlamaIndex introduction names" in t.value for t in app.text)


def test_unknown_artifact_query_is_not_file_access():
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.query_params["artifact"] = "../../.env"
    app.run()
    assert not app.exception
    assert any("unknown artifact reference" in w.value for w in app.warning)
    assert not app.code


def test_history_and_refresh():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.switch_page("views/quality.py").run()
    app.selectbox[0].select("M9-Q05").run()
    generation = next(s for s in app.selectbox if s.label == "Generation experiment")
    generation.select("data/evals/generation/live-q05-v1").run()
    assert not app.exception
    assert any("FAILED" in e.value and "provider" in e.value for e in app.error)
    assert not any("The LlamaIndex introduction names" in t.value for t in app.text)
    app.button[0].click().run()
    assert not app.exception
    assert app.selectbox[0].value == "M9-Q05"
