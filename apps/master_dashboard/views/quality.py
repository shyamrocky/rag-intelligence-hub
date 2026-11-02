"""Read-only quality page in the master app."""
import streamlit as st

from tools.quality_dashboard.ui import quality

quality(st.session_state["quality_data"])
