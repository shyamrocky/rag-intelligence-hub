"""Verified benchmark completion view; historical views remain unchanged."""

import streamlit as st

from tools.quality_dashboard.coverage_ui import quality

quality(st.session_state["expanded_data"])
