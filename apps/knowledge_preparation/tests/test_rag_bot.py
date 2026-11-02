"""Offline Bot UI starts empty; no execution on refresh or saved chat transcript."""
import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from apps.knowledge_preparation import (
    generation,
    post_generation,
    pre_generation,
    rag_bot,
    retrieval,
    views,
)
from apps.knowledge_preparation.tests.test_generation import offline  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]


def test_empty_landing_and_no_readers(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("BOT_FOUNDATION_MUST_NOT_READ_KNOWLEDGE_OR_RUN_PIPELINE")
    for module in (views, generation, post_generation, pre_generation, retrieval):
        monkeypatch.setattr(module, "load", forbidden)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120).run()
    assert not result.exception and not result.error
    assert result.title[0].value == "What would you like to explore?"
    assert len(result.chat_input) == 1 and not result.chat_input[0].disabled
    assert not result.chat_message and not result.metric
    # Normal Chat has no approval form or conflicting simulation toggle.
    assert not result.form and not result.toggle
    assert next(r for r in result.radio if r.label == "Request mode").value == "Chat"
    assert not any(b.label == "Enable live chat" for b in result.button)
    assert [link.label for link in result.sidebar.get("page_link")][:2] == ["New chat", "Knowledge Preparation"]
    assert [c.value for c in result.sidebar.caption][:2] == ["RAG BOT", "KNOWLEDGE WORKSPACE"]
    assert not result.sidebar.expander[0].proto.expanded
    assert all(any(question in m.value for m in result.markdown) for _, _, question in rag_bot.EXAMPLES)
    result.run()
    assert not result.exception and not result.chat_message
    navigate = result.sidebar.get("page_link")[0]
    assert navigate.label == "New chat"
    # A newly opened browser session also starts empty.
    fresh = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120).run()
    assert not fresh.exception and not fresh.chat_message and not fresh.chat_input[0].disabled


def test_bot_has_no_history_cache_or_provider_client():
    source = (ROOT / "apps/knowledge_preparation/rag_bot.py").read_text()
    tree = ast.parse(source)
    assert not any(isinstance(n, ast.Attribute) and n.attr in {
        "cache_data", "cache_resource", "write_text", "write_bytes", "chat_message", "invoke"}
        for n in ast.walk(tree))
    assert "from openai" not in source and "chat_history" not in source


def test_simulation_requires_opt_in_and_never_enables_live(monkeypatch):
    from tools.bot_runtime import dispatch
    def forbidden(*args, **kwargs):
        raise AssertionError("NO_SUBMISSION_NO_EXECUTION")
    monkeypatch.setattr(dispatch, "simulate", forbidden)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120).run()
    assert not result.chat_input[0].disabled
    next(r for r in result.radio if r.label == 'Request mode').set_value('Offline Simulation').run()
    assert not result.exception and result.chat_input[0].disabled
    result.run()
    assert not result.exception and not result.chat_message
    assert any("Ask a question about RAG. We’ll find and verify the evidence before answering" in m.value for m in result.markdown)


def test_existing_direct_routes_remain_registered(monkeypatch):
    def display_only(*args, **kwargs):
        import streamlit as st
        st.title("Existing workspace destination")
    monkeypatch.setattr(views, "render", display_only)
    result = AppTest.from_file(str(ROOT / "apps/knowledge_preparation/app.py"), default_timeout=120)
    result._page_hash = calc_hash("knowledge-preparation")
    result.run()
    assert not result.exception and result.title[0].value == "Existing workspace destination"
    assert result.sidebar.expander[0].proto.expanded
    assert {p.url_path for p in result.session_state["kp_pages"].values()} >= {
        "knowledge-preparation", "sources", "parsing-evidence", "chunks-lineage", "embeddings-indexes",
        "validation-publications", "knowledge-retrieval", "offline-retrieval-evaluation", "pre-generation",
        "generation", "post-generation-evaluation-human-review", "human-review", "parse", "normalize", "qa-evidence"}
    result._page_hash = calc_hash("sources")
    result.run()
    assert not result.exception
    assert any("[Knowledge Preparation](/knowledge-preparation)" in c.value for c in result.caption)
