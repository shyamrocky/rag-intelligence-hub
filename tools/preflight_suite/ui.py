"""Additive Master Dashboard integration; historical pages and explorer unchanged."""
from pathlib import Path

import streamlit as st

from tools.quality_dashboard import ui as historical_ui
from tools.quality_dashboard.artifacts import ArtifactError
from tools.quality_dashboard.completion_adapter import load_completed

from .dashboard import discover


def main(root):
    st.set_page_config(page_title='RAG Intelligence Hub', page_icon='📚', layout='wide')
    st.markdown(historical_ui.STYLE, unsafe_allow_html=True)
    if st.sidebar.button('Refresh verified telemetry'):
        st.rerun()
    try:
        data = load_completed(root)
        telemetry = discover(root)
    except (ArtifactError, ValueError, KeyError, OSError, TypeError):
        st.error('UNAVAILABLE — benchmark or measurement bindings failed verification.')
        st.stop()
    st.session_state['expanded_data'] = data
    st.session_state['quality_data'] = data
    st.session_state['preflight_telemetry'] = telemetry

    views = Path(root) / 'apps/master_dashboard/views'
    pages = [st.Page(views / 'preflight_home.py', title='Master Dashboard', icon='📚', default=True),
             st.Page(views / 'explorer.py', title='Candidate–Parent Explorer', icon='🔎', url_path='explorer'),
             st.Page(views / 'preflight_quality.py', title='End-to-End Quality & Telemetry', icon='📊', url_path='quality'),
             st.Page(views / 'preflight_suite.py', title='RAG Preflight Suite', icon='✅', url_path='preflight')]
    st.session_state['explorer_page'], st.session_state['quality_page'], st.session_state['preflight_page'] = pages[1:]
    historical_ui.show_artifact(data)
    st.navigation(pages).run()
    st.sidebar.caption('Read-only: no retrieval, assembly, provider or generation calls on refresh')
