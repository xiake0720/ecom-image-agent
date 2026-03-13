"""结果展示与调试信息面板。"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ui.components.download_panel import render_download_panel
from src.ui.components.preview_grid import render_preview_grid


def render_result_view(task_state: dict | None) -> None:
    if not task_state:
        st.subheader("结果")
        render_preview_grid([])
        return

    logs = task_state.get("logs", [])
    debug_info = task_state.get("debug", {})
    st.subheader("任务日志")
    st.code("\n".join(logs), language="text") if logs else st.info("当前还没有可展示的任务日志。")

    st.subheader("调试信息")
    _render_debug_panel(debug_info, logs)

    render_variant = str(task_state.get("render_variant") or "")
    preview_result = task_state.get("preview_generation_result", {"images": []})
    final_result = task_state.get("generation_result", {"images": []})
    if render_variant == "preview" and not preview_result.get("images"):
        preview_result = final_result
        final_result = {"images": []}
    preview_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in preview_result.get("images", [])]
    final_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in final_result.get("images", [])]

    st.subheader("预览结果")
    render_preview_grid(preview_paths)
    render_download_panel(preview_paths, task_state.get("preview_export_zip_path"), zip_label="下载预览 ZIP")

    st.subheader("正式成品")
    render_preview_grid(final_paths)
    render_download_panel(
        final_paths,
        task_state.get("export_zip_path"),
        zip_label="下载最终图片 ZIP",
        bundle_zip_path=task_state.get("full_task_bundle_zip_path"),
        bundle_zip_label="下载完整任务包 ZIP",
    )


def _render_debug_panel(debug_info: dict, logs: list[str]) -> None:
    if not debug_info:
        st.caption("当前任务未附带额外调试信息。")
        return

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    summary_col1.metric("Task ID", str(debug_info.get("task_id", "-")))
    summary_col2.metric("Budget Mode", str(debug_info.get("budget_mode", "-")))
    summary_col3.metric("Prompt Build", str(debug_info.get("prompt_build_mode", "-")))
    summary_col4.metric("Render Mode", str(debug_info.get("render_mode", "-")))

    if st.checkbox("显示 task 目录", value=True, key="debug_show_task_dir"):
        st.code(str(debug_info.get("task_dir", "-")), language="text")
    if st.checkbox("显示任务日志路径", value=True, key="debug_show_log_path"):
        log_path = str(debug_info.get("workflow_log_path", "-"))
        status = "exists" if log_path != "-" and Path(log_path).exists() else "missing"
        st.code(f"{log_path} [{status}]", language="text")
    if st.checkbox("显示中间 JSON 路径", value=False, key="debug_show_json_paths"):
        artifact_paths = debug_info.get("artifact_paths", {})
        path_lines = [f"{name}: {path} [{'exists' if Path(path).exists() else 'missing'}]" for name, path in artifact_paths.items()]
        st.code("\n".join(path_lines), language="text")
    if st.checkbox("显示最近 8 条执行日志", value=False, key="debug_show_recent_logs"):
        recent_logs = logs[-8:] if logs else []
        st.code("\n".join(recent_logs) if recent_logs else "暂无日志", language="text")
