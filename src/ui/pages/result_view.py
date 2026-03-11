from __future__ import annotations

import streamlit as st

from src.ui.components.download_panel import render_download_panel
from src.ui.components.preview_grid import render_preview_grid


def render_result_view(task_state: dict | None) -> None:
    if not task_state:
        st.subheader("结果")
        render_preview_grid([])
        return

    st.subheader("任务日志")
    for line in task_state.get("logs", []):
        st.code(line)

    st.subheader("结果预览")
    image_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in task_state["generation_result"]["images"]]
    render_preview_grid(image_paths)

    st.subheader("下载")
    render_download_panel(image_paths, task_state.get("export_zip_path"))

