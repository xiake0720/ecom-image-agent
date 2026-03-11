from __future__ import annotations

from pathlib import Path

import streamlit as st


def render_preview_grid(image_paths: list[str]) -> None:
    if not image_paths:
        st.info("任务执行后会在这里展示结果占位图。")
        return
    columns = st.columns(2)
    for index, image_path in enumerate(image_paths):
        with columns[index % 2]:
            st.image(image_path, use_container_width=True, caption=Path(image_path).name)

