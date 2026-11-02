"""Expanded benchmark landing page."""
import streamlit as st

from tools.quality_dashboard.expanded_ui import home

home(st.session_state["expanded_data"])
