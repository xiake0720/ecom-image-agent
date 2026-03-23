"""结果展示页。

文件位置：
- `src/ui/pages/result_view.py`

核心职责：
- 展示预览结果和正式成品
- 展示日志、QC、debug 信息
- 展示“本次真实生成链路”
- 调用下载面板组件

主要调用方：
- `src/ui/pages/home.py`
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ui.components.download_panel import render_download_panel
from src.ui.components.preview_grid import render_preview_grid


def render_result_view(task_state: dict | None) -> None:
    """渲染任务结果页。"""
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

<<<<<<< HEAD
    if task_state.get("director_output") or task_state.get("prompt_plan_v2"):
        st.subheader("v2 调试产物")
        _render_v2_debug_artifacts(task_state)

=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
    """根据 render_variant 决定结果页应展示哪些图片。"""
    render_variant = str(task_state.get("render_variant") or "")
    preview_result = task_state.get("preview_generation_result", {"images": []})
    final_result = task_state.get("generation_result", {"images": []})
    if render_variant == "preview":
        if not preview_result.get("images"):
            preview_result = final_result
        # preview 模式下不能把同一批预览图再重复当成正式成品展示。
        final_result = {"images": []}
    preview_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in preview_result.get("images", [])]
    final_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in final_result.get("images", [])]
    return preview_paths, final_paths


def _render_generation_chain(debug_info: dict) -> None:
    """渲染“本次真实生成链路”摘要。"""
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
    """渲染调试信息面板。"""
    if not debug_info:
        st.caption("当前任务未附带额外调试信息。")
        return

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    summary_col1.metric("Task ID", str(debug_info.get("task_id", "-")))
    summary_col2.metric("Budget Mode", str(debug_info.get("budget_mode", "-")))
<<<<<<< HEAD
    summary_col3.metric("Workflow", str(debug_info.get("workflow_version", "-")))
=======
    summary_col3.metric("Prompt Build", str(debug_info.get("prompt_build_mode", "-")))
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
                f"connected_contract_files: {debug_info.get('connected_contract_files', [])}",
                f"style_architecture_connected: {debug_info.get('style_architecture_connected', False)}",
                f"shot_prompt_specs_available_for_render: {debug_info.get('shot_prompt_specs_available_for_render', False)}",
<<<<<<< HEAD
                f"prompt_plan_v2_available_for_render: {debug_info.get('prompt_plan_v2_available_for_render', False)}",
                f"product_lock_connected: {debug_info.get('product_lock_connected', False)}",
                f"needs_overlay_fallback: {debug_info.get('needs_overlay_fallback', False)}",
                f"overlay_fallback_candidates: {debug_info.get('overlay_fallback_candidates', [])}",
=======
                f"product_lock_connected: {debug_info.get('product_lock_connected', False)}",
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD


def _render_v2_debug_artifacts(task_state: dict) -> None:
    """展示 v2 director_output 和 prompt_plan_v2 的最小调试摘要。"""
    director_output = task_state.get("director_output") or {}
    prompt_plan_v2 = task_state.get("prompt_plan_v2") or {}
    if director_output:
        st.code(
            "\n".join(
                [
                    f"product_summary: {director_output.get('product_summary', '-')}",
                    f"platform: {director_output.get('platform', '-')}",
                    f"shot_count: {len(director_output.get('shots', []) or [])}",
                ]
            ),
            language="text",
        )
    if prompt_plan_v2:
        preview_lines = []
        for shot in (prompt_plan_v2.get("shots", []) or [])[:4]:
            preview_lines.append(
                f"{shot.get('shot_id', '-')} | {shot.get('shot_role', '-')} | {shot.get('title_copy', '-')} | {shot.get('subtitle_copy', '-')}"
            )
        st.code("\n".join(preview_lines) if preview_lines else "暂无 prompt_plan_v2", language="text")
=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
