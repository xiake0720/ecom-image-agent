"""结果展示页。

文件位置：
- `src/ui/pages/result_view.py`

职责：
- 展示当前已生成的图片结果
- 在 `render_images` 尚未完成时展示增量结果
- 提供最终结果包下载入口
"""

from __future__ import annotations

import streamlit as st

from src.ui.components.download_panel import render_download_panel
from src.ui.components.preview_grid import render_preview_grid


def render_result_view(task_state: dict | None) -> None:
    """展示当前已生成的最终图片结果。"""

    st.subheader("生成结果")
    if not task_state:
        render_preview_grid([])
        return

    generation_result = task_state.get("generation_result_v2") or task_state.get("generation_result") or {}
    images = generation_result.get("images", []) if isinstance(generation_result, dict) else []
    image_paths = [image["image_path"] if isinstance(image, dict) else image.image_path for image in images]
    current_step = str(task_state.get("current_step") or "")
    shot_total = _resolve_total_count(task_state)

    if not image_paths:
        render_preview_grid([])
        return

    if current_step == "render_images" and shot_total:
        st.caption(f"已生成 {len(image_paths)}/{shot_total} 张，系统正在继续补齐整套图片。")

    render_preview_grid(image_paths)
    render_nonce = _next_download_render_nonce()
    render_download_panel(
        image_paths,
        task_state.get("export_zip_path"),
        zip_label="下载结果 ZIP",
        bundle_zip_path=task_state.get("full_task_bundle_zip_path"),
        bundle_zip_label="下载完整任务包 ZIP",
        panel_key_prefix=f"final-{render_nonce}",
    )


def _resolve_total_count(task_state: dict[str, object]) -> int:
    """优先从 prompt plan 读取应生成图数，回退到任务默认张数。"""

    prompt_plan = task_state.get("prompt_plan_v2")
    if isinstance(prompt_plan, dict):
        shots = prompt_plan.get("shots")
        if isinstance(shots, list):
            return len(shots)
    task = task_state.get("task")
    if isinstance(task, dict):
        try:
            return int(task.get("shot_count", 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _next_download_render_nonce() -> int:
    """为下载组件生成本次渲染前缀，避免增量刷新时 key 冲突。"""

    state_key = "_result_download_render_nonce"
    current = int(st.session_state.get(state_key, 0)) + 1
    st.session_state[state_key] = current
    return current
