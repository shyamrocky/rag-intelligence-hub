"""Real Streamlit panel and authorized parent navigation; no forged evidence mocks."""

import json
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]
DURABLE = "config/retrieval-chunks-m3-durable-v1.json"


def panel(selector=DURABLE):
    script = ("from pathlib import Path\nfrom rag_hub.m7_dashboard import render\n"
              f"render(Path({str(ROOT)!r}),selector={selector!r},"
              "document_ids=['C01','C02','C04','C06','C10','C14','C16'])\n")
    return AppTest.from_string(script, default_timeout=180).run()


def test_historical_panel_no_durable_search():
    app = panel("config/retrieval-chunks-v2.json")
    assert not app.exception and not app.form
    assert any("Historical inspection" in item.value for item in app.info)


def test_bm25_results_and_reverse_navigation():
    app = panel()
    app.selectbox(key="m7_mode").set_value("bm25")
    app.text_input(key="m7_query").set_value("BM25")
    app.button(key="FormSubmitter:m7-retrieval-Search authorized chunks").click().run()
    assert not app.exception and not app.error
    result = app.session_state["m7_result"]
    assert result["candidates"]
    assert all(h["contributing_retrievers"] == ["bm25"] for h in result["candidates"])
    assert not any("source_content" in t.value for t in app.text)
    cid = result["candidates"][0]["chunk_id"]
    app.button(key="m7_parent_" + cid).click().run()
    assert app.session_state["view"] == "Chunk Inspector"
    assert app.session_state["chunk_entered"] == cid
    assert "source_content" not in result


def test_hybrid_contributions_and_safe_filters():
    app = panel()
    app.text_input(key="m7_query").set_value("reciprocal rank fusion")
    app.selectbox(key="m7_document").set_value("C10")
    app.selectbox(key="m7_classification").set_value("ILLUSTRATIVE_REFERENCE")
    app.button(key="FormSubmitter:m7-retrieval-Search authorized chunks").click().run()
    assert not app.exception and not app.error
    result = app.session_state["m7_result"]
    assert result["retrieval_mode"] == "hybrid"
    assert result["candidates"]
    assert all(h["document_id"] == "C10" for h in result["candidates"])
    assert all(set(h["contributing_retrievers"]) <= {"vector", "bm25"} for h in result["candidates"])
    assert any("contributing_retrievers" in frame.value.columns for frame in app.dataframe)


def test_invalid_depth_clears_previous_results():
    app = panel()
    app.text_input(key="m7_query").set_value("RAG")
    app.number_input(key="m7_top_k").set_value(10)
    app.number_input(key="m7_depth").set_value(2)
    app.button(key="FormSubmitter:m7-retrieval-Search authorized chunks").click().run()
    assert not app.exception and app.error
    assert not any(b.key.startswith("m7_parent_") for b in app.button)


def test_empty_query_no_candidates():
    app = panel()
    app.button(key="FormSubmitter:m7-retrieval-Search authorized chunks").click().run()
    assert not app.exception
    assert app.session_state["m7_result"]["candidates"] == []


def test_installed_entrypoint_without_repository_import_path(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text("from pathlib import Path\n"
        "from rag_hub.m7_dashboard import get_service,SELECTOR_SHA256\n"
        f"service=get_service(Path({str(ROOT)!r}),SELECTOR_SHA256)\n"
        "service.check()\nservice.close()\nprint('PASS')\n")
    result = subprocess.run([sys.executable, str(probe)], cwd=tmp_path, text=True,
                            capture_output=True, timeout=120, check=True)
    assert result.stdout.strip() == "PASS"


def test_existing_app_retrieval_to_C10_complete_parent():
    app = AppTest.from_file(str(ROOT / "apps/ingestion_dashboard/app.py"), default_timeout=240)
    app.session_state["operational_release"] = DURABLE
    app.run()
    assert not app.exception
    app.text_input(key="m7_query").set_value("reciprocal rank fusion")
    app.selectbox(key="m7_document").set_value("C10")
    app.number_input(key="m7_top_k").set_value(50)
    app.button(key="FormSubmitter:m7-retrieval-Search authorized chunks").click().run()
    assert not app.exception and not app.error
    # Select the exact qualified scoring-table parent, not an arbitrary prose hit.
    payload = json.loads((ROOT / "data/indexes/m5-chroma-v1/verified-inputs.json").read_bytes())
    cid = payload["rows"][0]["id"]
    assert payload["rows"][0]["metadata"]["document_id"] == "C10"
    assert cid in {h["chunk_id"] for h in app.session_state["m7_result"]["candidates"]}
    app.button(key="m7_parent_" + cid).click().run()
    assert not app.exception
    assert app.session_state["view"] == "Chunk Inspector"
    assert any(item.value == "Complete authorized parent" for item in app.subheader)
    assert any("scores" in item.value.lower() or "scoring" in item.value.lower() for item in app.warning)
