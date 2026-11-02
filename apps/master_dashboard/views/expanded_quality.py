"""Expanded benchmark connected quality tabs."""
import streamlit as st

from tools.quality_dashboard.expanded_ui import quality

quality(st.session_state["expanded_data"])
