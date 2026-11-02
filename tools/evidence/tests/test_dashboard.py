"""Actual Streamlit evidence controls and native gateways, no fabricated evidence UI."""

import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[3]


def panel(budget=None, candidate_mutation=False):
    script = ("import json\nfrom pathlib import Path\nfrom rag_hub.m8_dashboard import render\n"
        f"root=Path({str(ROOT)!r})\n"
        "result=json.loads((root/'workspace/rag-implementation/v1/m7-hybrid-v1/CANDIDATE_EXAMPLE.json').read_bytes())\n")
    if candidate_mutation:
        script += "result['candidates'][0]['chunk_id']='rc:forged'\n"
    if budget:
        script += f"import streamlit as st\nst.session_state.setdefault('m8_budget',{budget})\n"
    return AppTest.from_string(script + "render(root,result)\n", default_timeout=240).run()


def test_evidence_is_opt_in_and_no_payload_cached():
    app = panel()
    assert not app.exception
    assert not app.checkbox(key="m8_view").value
    assert not any("Authorized source content" == h.value for h in app.subheader)
    assert "m8_package" not in app.session_state


def test_actual_C10_evidence_and_budget():
    app = panel(100000)
    app.checkbox(key="m8_view").check().run()
    assert not app.exception and not app.error
    assert any(h.value == "Authorized source content" for h in app.subheader)
    assert any(h.value == "Mandatory source context" for h in app.subheader)
    assert any("Qualifications & permitted use" == h.value for h in app.subheader)
    assert any("selected" in c.value and "parents" in c.value for c in app.caption)
    assert "m8_package" not in app.session_state


def test_insufficient_budget_never_shows_partial_parent():
    app = panel(1)
    app.checkbox(key="m8_view").check().run()
    assert not app.exception and not app.error
    assert any("INSUFFICIENT_EVIDENCE" in x.value for x in app.info)
    assert not any(h.value == "Authorized source content" for h in app.subheader)
    assert app.warning


def test_forged_result_integrity_failure_distinct_from_no_results():
    app = panel(candidate_mutation=True)
    app.checkbox(key="m8_view").check().run()
    assert not app.exception
    assert any("failed closed" in e.value for e in app.error)
    assert not any("NO_RETRIEVAL_CANDIDATES" in x.value for x in app.info)
    assert not any(h.value == "Authorized source content" for h in app.subheader)


def test_installed_entrypoint_without_repo_sys_path(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text("from pathlib import Path\n"
        "from rag_hub.m8_dashboard import get_service,SELECTOR_SHA256\n"
        f"service=get_service(Path({str(ROOT)!r}),SELECTOR_SHA256)\n"
        "service.check()\nprint('PASS')\n")
    result = subprocess.run([sys.executable, str(probe)], cwd=tmp_path, text=True,
                             capture_output=True, timeout=180, check=True)
    assert result.stdout.strip() == "PASS"


def test_M7_panel_optional_evidence_navigation():
    script = ("from pathlib import Path\nfrom rag_hub.m7_dashboard import render\n"
        f"render(Path({str(ROOT)!r}),selector='config/retrieval-chunks-m3-durable-v1.json',"
        "document_ids=['C01','C04','C06','C10','C14'])\n")
    app = AppTest.from_string(script, default_timeout=240).run()
    app.selectbox(key="m7_mode").set_value("bm25")
    app.text_input(key="m7_query").set_value("reciprocal rank fusion")
    app.selectbox(key="m7_document").set_value("C10")
    app.button(key="FormSubmitter:m7-retrieval-Search authorized chunks").click().run()
    assert not app.exception and not app.error
    app.number_input(key="m8_budget").set_value(100000)
    app.checkbox(key="m8_view").check().run()
    assert not app.exception and not app.error
    assert any(x.value == "Authorized source content" for x in app.subheader)
    cid = app.session_state["m7_result"]["candidates"][0]["chunk_id"]
    app.checkbox(key="m8_view").uncheck().run()
    app.button(key="m7_parent_" + cid).click().run()
    assert app.session_state["view"] == "Chunk Inspector"


def test_empty_package_no_citation_or_source_render():
    script = ("import json\nfrom pathlib import Path\nfrom rag_hub.m8_dashboard import render\n"
        f"root=Path({str(ROOT)!r})\n"
        "v=json.loads((root/'workspace/rag-implementation/v1/m7-hybrid-v1/CANDIDATE_EXAMPLE.json').read_bytes())\n"
        "v['candidates']=[]\nrender(root,v)\n")
    app = AppTest.from_string(script, default_timeout=240).run()
    app.checkbox(key="m8_view").check().run()
    assert not app.exception and not app.error
    assert any("NO_RETRIEVAL_CANDIDATES" in i.value for i in app.info)
    assert not app.subheader
