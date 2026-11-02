"""Read-only preflight run history; no execution controls."""
from pathlib import Path

import streamlit as st

from tools.preflight_suite.dashboard import suite

suite(st, Path(__file__).resolve().parents[3], st.session_state['expanded_data'],
      st.session_state['preflight_telemetry'])

from tools.quality_dashboard.preflight_history import render

render(st, Path(__file__).resolve().parents[3])
