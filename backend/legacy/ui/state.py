from __future__ import annotations

import streamlit as st


def ensure_ui_state() -> None:
    st.session_state.setdefault("task_state", None)
    st.session_state.setdefault("task_error", None)

