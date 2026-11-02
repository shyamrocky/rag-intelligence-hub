"""Local, read-only ingestion dashboard. Run from the repository root."""

from pathlib import Path

from rag_hub.dashboard_ui import main

main(Path(__file__).resolve().parents[2])

# M9 adds an inspection-only measured-results panel. Existing modes/readers are unchanged.
import streamlit as st

from rag_hub.m9_dashboard import render as render_evaluation

render_evaluation(Path(__file__).resolve().parents[2],
                  selector=st.session_state.get("operational_release", ""))
