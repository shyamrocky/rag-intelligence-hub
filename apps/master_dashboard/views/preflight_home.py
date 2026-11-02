"""Existing master landing with additive preflight telemetry."""
import streamlit as st

from tools.quality_dashboard.coverage_ui import home

home(st.session_state['expanded_data'])
if 'benchmark_tracker_page' in st.session_state:
    st.page_link(st.session_state['benchmark_tracker_page'], label='Final Generation Benchmark Tracker', icon='📋')
st.page_link(st.session_state['preflight_page'], label='RAG Preflight Suite', icon='✅')
runs = st.session_state['preflight_telemetry']['runs']
if runs:
    st.caption('Latest preflight run: ' + runs[-1]['manifest']['run_id'])
    st.json(runs[-1]['results']['summary'])
