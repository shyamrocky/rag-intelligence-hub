"""Read-only explorer page in the master app."""
import streamlit as st

from tools.quality_dashboard.ui import explorer

explorer(st.session_state["quality_data"])
