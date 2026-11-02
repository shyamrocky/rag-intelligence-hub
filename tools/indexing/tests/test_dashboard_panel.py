"""M5 panel AppTests use the actual isolated index verifier, not fabricated evidence."""

from pathlib import Path

import pytest

from rag_hub.m5_dashboard import inspect_index, open_parent

ROOT = Path(__file__).resolve().parents[3]


def test_real_panel_metadata_reader():
    result = inspect_index(ROOT, document="C01")
    assert result["records"] == 992 and result["matching_records"] > 0
    assert result["authority"] == "INSPECTION_ONLY_NOT_EVIDENCE"
    assert result["exact_record"] is None


def test_reader_unknown_chunk_rejected():
    with pytest.raises(ValueError, match="unknown_chunk"):
        inspect_index(ROOT, chunk_id="UNKNOWN")


def test_worker_cannot_forge_inspection_result(tmp_path):
    import json

    selected = json.loads((ROOT / "config/vector-index-m5-v1-1.json").read_bytes())
    paths = ["config/vector-index-m5-v1-1.json", selected["manifest_path"]]
    manifest = json.loads((ROOT / selected["manifest_path"]).read_bytes())
    paths.extend(manifest["spec"]["components"])
    for name in paths:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    (tmp_path / "tools/indexing/m5_index.py").write_text('print("forged success")')
    with pytest.raises(ValueError, match="dashboard_component_changed"):
        inspect_index(tmp_path)


def test_parent_navigation_does_not_authorize_evidence():
    state = {}
    open_parent(state, "qualified-chunk-id")
    assert state["view"] == "Chunk Inspector"
    assert state["chunk_entered"] == "qualified-chunk-id"
    assert not any("text" in key or "payload" in key for key in state)


def panel(selector):
    from streamlit.testing.v1 import AppTest

    script = ("from pathlib import Path\nfrom rag_hub.m5_dashboard import render\n"
              f"render(Path({str(ROOT)!r}),selector={selector!r},"
              "document_ids=['C01','C02','C04','C06','C10','C14','C16'])\n")
    return AppTest.from_string(script, default_timeout=120).run()


def test_historical_panel_never_opens_durable_index():
    app = panel("config/retrieval-chunks-v2.json")
    assert not app.exception
    assert not app.form
    assert any("Historical modes" in item.value for item in app.info)


def test_actual_integrity_and_exact_lookup_panel():
    import json

    payload = json.loads((ROOT / "data/indexes/m5-chroma-v1/verified-inputs.json").read_bytes())
    row = payload["rows"][0]
    app = panel("config/retrieval-chunks-m3-durable-v1.json")
    assert not app.exception
    app.text_input(key="m5_chunk").set_value(row["id"])
    app.button(key="FormSubmitter:m5-index-inspection-Verify selected M5 index").click().run()
    assert not app.exception
    assert any("992" in item.value for item in app.success)
    assert app.button(key="m5-open-parent")
    assert not any("source_content" in item.value for item in app.text)
    assert any(row["id"] == item.value for item in app.text)


def test_unknown_id_safe_panel_error():
    app = panel("config/retrieval-chunks-m3-durable-v1.json")
    app.text_input(key="m5_chunk").set_value("UNAUTHORIZED")
    app.button(key="FormSubmitter:m5-index-inspection-Verify selected M5 index").click().run()
    assert not app.exception
    assert app.error
    assert not app.success


def test_existing_app_index_to_complete_qualified_parent():
    import json

    from streamlit.testing.v1 import AppTest

    payload = json.loads((ROOT / "data/indexes/m5-chroma-v1/verified-inputs.json").read_bytes())
    row = payload["rows"][0]
    assert row["metadata"]["document_id"] == "C10"
    app = AppTest.from_file(str(ROOT / "apps/ingestion_dashboard/app.py"), default_timeout=180)
    app.session_state["operational_release"] = "config/retrieval-chunks-m3-durable-v1.json"
    app.run()
    assert not app.exception
    app.text_input(key="m5_chunk").set_value(row["id"])
    app.button(key="FormSubmitter:m5-index-inspection-Verify selected M5 index").click().run()
    assert not app.exception
    app.button(key="m5-open-parent").click().run()
    assert not app.exception
    assert app.session_state["view"] == "Chunk Inspector"
    assert app.session_state["chunk_entered"] == row["id"]
    assert any(item.value == "Complete authorized parent" for item in app.subheader)
    assert any("scoring" in item.value or "scores" in item.value for item in app.warning)
