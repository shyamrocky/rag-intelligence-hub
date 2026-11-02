"""Read-only generation planning and run history; no execution controls."""
from pathlib import Path

import streamlit as st

from tools.generation_rollout.dashboard import render as render_rollout
from tools.generation_runner.dashboard import render

render(st, Path(__file__).resolve().parents[3], st.session_state['expanded_data'])
render_rollout(st, Path(__file__).resolve().parents[3])
