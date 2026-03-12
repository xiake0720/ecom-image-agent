"""结果展示与调试信息面板。

该页面负责展示：
- 本次任务的执行日志
- 生成结果预览
- 下载入口
- 当前 provider 模式、task 目录和关键 JSON 路径等调试信息

它不负责触发 workflow，只消费首页传入的 `task_state`。
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ui.components.download_panel import render_download_panel
from src.ui.components.preview_grid import render_preview_grid


def render_result_view(task_state: dict | None) -> None:
    """渲染任务结果与调试信息。"""
    if not task_state:
        st.subheader("结果")
        render_preview_grid([])
        return

    logs = task_state.get("logs", [])
    debug_info = task_state.get("debug", {})

    st.subheader("任务日志")
    if logs:
        st.code("\n".join(logs), language="text")
    else:
        st.info("当前还没有可展示的任务日志。")

    st.subheader("调试信息")
    _render_debug_panel(debug_info, logs)

    st.subheader("结果预览")
    generation_result = task_state.get("generation_result", {"images": []})
    image_paths = [
        image["image_path"] if isinstance(image, dict) else image.image_path
        for image in generation_result.get("images", [])
    ]
    render_preview_grid(image_paths)

    st.subheader("下载")
    render_download_panel(image_paths, task_state.get("export_zip_path"))


def _render_debug_panel(debug_info: dict, logs: list[str]) -> None:
    """按需展示 provider 模式、task 目录和中间产物路径。"""
    if not debug_info:
        st.caption("当前任务未附带额外调试信息。")
        return

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    summary_col1.metric("Task ID", str(debug_info.get("task_id", "-")))
    summary_col2.metric("Text Mode", str(debug_info.get("text_provider_mode", "-")))
    summary_col3.metric("Image Mode", str(debug_info.get("image_provider_mode", "-")))
    summary_col4.metric("Log Level", str(debug_info.get("log_level", "-")))

    show_provider_modes = st.checkbox("显示 provider 模式", value=True, key="debug_show_provider_modes")
    show_task_dir = st.checkbox("显示 task 目录", value=True, key="debug_show_task_dir")
    show_log_path = st.checkbox("显示任务日志路径", value=True, key="debug_show_log_path")
    show_json_paths = st.checkbox("显示中间 JSON 路径", value=False, key="debug_show_json_paths")
    show_recent_logs = st.checkbox("显示最近 8 条执行日志", value=False, key="debug_show_recent_logs")

    if show_provider_modes:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Text Provider Mode", str(debug_info.get("text_provider_mode", "-")))
        col2.metric("Vision Provider Mode", str(debug_info.get("vision_provider_mode", "-")))
        col3.metric("Image Provider Mode", str(debug_info.get("image_provider_mode", "-")))
        col4.metric("任务文件日志", str(debug_info.get("enable_file_log", "-")))
        model_col1, model_col2, model_col3, model_col4 = st.columns(4)
        model_col1.metric("Text Model", str(debug_info.get("nvidia_text_model", "-")))
        model_col2.metric("Vision Model", str(debug_info.get("nvidia_vision_model", "-")))
        model_col3.metric("Text Model Label", str(debug_info.get("text_model_label", "-")))
        model_col4.metric("Vision Model Label", str(debug_info.get("vision_model_label", "-")))
        source_col1, source_col2 = st.columns(2)
        source_col1.metric("Text Model Source", str(debug_info.get("text_model_source", "-")))
        source_col2.metric("Vision Model Source", str(debug_info.get("vision_model_source", "-")))

    if show_task_dir:
        st.code(str(debug_info.get("task_dir", "-")), language="text")

    if show_log_path:
        log_path = str(debug_info.get("workflow_log_path", "-"))
        status = "exists" if log_path != "-" and Path(log_path).exists() else "missing"
        st.code(f"{log_path} [{status}]", language="text")

    if show_json_paths:
        artifact_paths = debug_info.get("artifact_paths", {})
        path_lines = []
        for name, path in artifact_paths.items():
            status = "exists" if Path(path).exists() else "missing"
            path_lines.append(f"{name}: {path} [{status}]")
        st.code("\n".join(path_lines), language="text")

    if show_recent_logs:
        recent_logs = logs[-8:] if logs else []
        st.code("\n".join(recent_logs) if recent_logs else "暂无日志", language="text")

