"""Result display and debug panels."""

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

    st.subheader("本次真实生成链路")
    _render_generation_chain(debug_info)

    st.subheader("任务日志")
    st.code("\n".join(logs), language="text") if logs else st.info("当前还没有可展示的任务日志。")

    st.subheader("调试信息")
    _render_debug_panel(debug_info, logs)

    preview_paths, final_paths = resolve_result_image_paths(task_state)

    st.subheader("预览结果")
    render_preview_grid(preview_paths)
    render_download_panel(
        preview_paths,
        task_state.get("preview_export_zip_path"),
        zip_label="下载预览 ZIP",
        panel_key_prefix="preview",
    )

    st.subheader("正式成品")
    if final_paths:
        render_preview_grid(final_paths)
        render_download_panel(
            final_paths,
            task_state.get("export_zip_path"),
            zip_label="下载最终图片 ZIP",
            bundle_zip_path=task_state.get("full_task_bundle_zip_path"),
            bundle_zip_label="下载完整任务包 ZIP",
            panel_key_prefix="final",
        )
    else:
        st.info("尚未生成正式成品。")
        render_download_panel(
            [],
            None,
            bundle_zip_path=task_state.get("full_task_bundle_zip_path"),
            bundle_zip_label="下载完整任务包 ZIP",
            panel_key_prefix="bundle",
        )


def resolve_result_image_paths(task_state: dict) -> tuple[list[str], list[str]]:
    render_variant = str(task_state.get("render_variant") or "")
    preview_result = task_state.get("preview_generation_result", {"images": []})
    final_result = task_state.get("generation_result", {"images": []})
    if render_variant == "preview":
        if not preview_result.get("images"):
            preview_result = final_result
        final_result = {"images": []}
    preview_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in preview_result.get("images", [])]
    final_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in final_result.get("images", [])]
    return preview_paths, final_paths


def _render_generation_chain(debug_info: dict) -> None:
    if not debug_info:
        st.info("当前还没有可展示的生成链路信息。")
        return

    chain = debug_info.get("real_generation_chain", {})
    cols = st.columns(5)
    cols[0].metric("Preview/Final", str(chain.get("preview_or_final", "-")))
    cols[1].metric("Generation", str(chain.get("generation_mode", "-")))
    cols[2].metric("Image Provider", str(chain.get("image_provider_impl", "-")))
    cols[3].metric("Image Model", str(chain.get("image_model_id", "-")))
    cols[4].metric("Cache Hits", str(len(chain.get("cache_hit_nodes", []) or [])))

    ref_ids = chain.get("reference_asset_ids", []) or []
    cache_hit_nodes = chain.get("cache_hit_nodes", []) or []
    st.code(
        "\n".join(
            [
                f"reference_asset_ids: {ref_ids}",
                f"cache_hit_nodes: {cache_hit_nodes}",
            ]
        ),
        language="text",
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

    debug_cols = st.columns(4)
    debug_cols[0].metric("Cache Enabled", str(debug_info.get("cache_enabled", "-")))
    debug_cols[1].metric("Ignore Cache", str(debug_info.get("ignore_cache", "-")))
    debug_cols[2].metric("Render Variant", str(debug_info.get("render_variant", "-")))
    debug_cols[3].metric("Render Gen Mode", str(debug_info.get("render_generation_mode", "-")))

    provider_cols = st.columns(2)
    provider_cols[0].metric("Image Provider Impl", str(debug_info.get("image_provider_impl", "-")))
    provider_cols[1].metric("Image Model ID", str(debug_info.get("image_model_id", "-")))

    st.code(
        "\n".join(
            [
                f"cache_hit_nodes: {debug_info.get('cache_hit_nodes', [])}",
                f"render_reference_asset_ids: {debug_info.get('render_reference_asset_ids', [])}",
            ]
        ),
        language="text",
    )

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
