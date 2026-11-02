"""Existing question-level telemetry plus linked preflight and timing history."""
from pathlib import Path

import streamlit as st

from tools.preflight_suite.dashboard import compact
from tools.quality_dashboard.latency_ui import quality

quality(st.session_state['expanded_data'], root=Path(__file__).resolve().parents[3])
qid = st.session_state.get('expanded_question')
if qid:
    compact(st, st.session_state['preflight_telemetry'], qid)
