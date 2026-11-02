"""Canonical read-only final benchmark page."""
from pathlib import Path

import streamlit as st

from tools.benchmark_tracker.ui import render

render(Path(__file__).resolve().parents[3], st.session_state['expanded_data'])
