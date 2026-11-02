"""Read-only home page in the master app."""
import streamlit as st

from tools.quality_dashboard.ui import home

home(st.session_state["quality_data"])
