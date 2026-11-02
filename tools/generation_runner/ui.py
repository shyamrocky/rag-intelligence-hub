"""Canonical navigation extension. Reuses every existing page unchanged."""
from pathlib import Path

import streamlit as st

from tools.preflight_suite.dashboard import discover
from tools.quality_dashboard import ui as historical_ui
from tools.quality_dashboard.artifacts import ArtifactError
from tools.quality_dashboard.completion_adapter import load_completed


def main(root):
    st.set_page_config(page_title='RAG Intelligence Hub', page_icon='📚', layout='wide')
    st.markdown(historical_ui.STYLE, unsafe_allow_html=True)
    if st.sidebar.button('Refresh verified telemetry'):
        st.rerun()
    try:
        data, telemetry = load_completed(root), discover(root)
    except (ArtifactError, ValueError, KeyError, OSError, TypeError):
        st.error('UNAVAILABLE — benchmark or measurement bindings failed verification.')
        st.stop()
    st.session_state['expanded_data'] = st.session_state['quality_data'] = data
    st.session_state['preflight_telemetry'] = telemetry
    views = Path(root) / 'apps/master_dashboard/views'
    pages = [st.Page(views / 'preflight_home.py', title='Master Dashboard', icon='📚', default=True),
             st.Page(views / 'explorer.py', title='Candidate–Parent Explorer', icon='🔎', url_path='explorer'),
             st.Page(views / 'preflight_quality.py', title='End-to-End Quality & Telemetry', icon='📊', url_path='quality'),
             st.Page(views / 'preflight_suite.py', title='RAG Preflight Suite', icon='✅', url_path='preflight'),
             st.Page(views / 'generation_runner.py', title='Grounded Generation Runner', icon='🧪', url_path='generation-runner'),
             st.Page(views / 'final_generation_benchmark.py', title='Final Generation Benchmark Tracker', icon='📋', url_path='final-generation-benchmark-tracker')]
    st.session_state['explorer_page'], st.session_state['quality_page'], st.session_state['preflight_page'] = pages[1:4]
    st.session_state['master_dashboard_page'], st.session_state['benchmark_tracker_page'] = pages[0], pages[5]
    st.session_state['generation_runner_page'] = pages[4]
    historical_ui.show_artifact(data)
    st.navigation(pages).run()
    st.sidebar.caption('Refresh/navigation are read-only. Human Review accepts explicit authenticated '
                       'decisions only; no provider or generation execution is available.')
