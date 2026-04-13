"""详情图渲染节点。"""

from __future__ import annotations

from pathlib import Path

from backend.engine.workflows.detail_state import (
    DetailWorkflowDependencies,
    DetailWorkflowState,
    build_detail_render_progress_task,
)
from backend.services.detail_render_service import DetailRenderService


def detail_render_pages(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """按 prompt plan 调用统一图片 provider 渲染每张详情图。"""

    prompt_plan = state.get("detail_prompt_plan")
    if prompt_plan is None or not prompt_plan:
        raise RuntimeError("detail_render_pages requires detail_prompt_plan")

    task = state["task"]
    service = DetailRenderService()

    def on_progress(processed_count: int, total_count: int, render_results) -> None:
        if deps.progress_callback is None:
            return
        progress_task = build_detail_render_progress_task(task, completed_count=processed_count, total_count=total_count)
        deps.progress_callback(
            {
                **state,
                "task": progress_task,
                "detail_render_results": render_results,
                "current_step": progress_task.current_step,
                "current_step_label": progress_task.current_step_label,
                "progress_percent": progress_task.progress_percent,
                "error_message": "",
            }
        )

    render_results = service.render_pages(
        task_dir=Path(task.task_dir),
        prompt_plan=prompt_plan,
        image_provider=deps.image_generation_provider,
        provider_name=deps.image_provider_name,
        model_name=deps.image_model_selection.label if deps.image_model_selection else "",
        usage_provider_name=deps.image_route.alias if deps.image_route is not None else deps.image_provider_name,
        usage_model_id=deps.image_model_selection.model_id if deps.image_model_selection is not None else "",
        usage_enabled=bool(deps.image_route is not None and deps.image_route.mode == "real"),
        task_id=task.task_id,
        stage_label=state.get("current_step_label", ""),
        image_size=state["detail_payload"].image_size,
        progress_callback=on_progress,
    )
    success_count = sum(1 for item in render_results if item.status == "completed")
    failed_count = sum(1 for item in render_results if item.status == "failed")
    return {
        "detail_render_results": render_results,
        "logs": [
            *state.get("logs", []),
            f"[detail_render_pages] completed={success_count} failed={failed_count}",
            "[detail_render_pages] saved generated/detail_render_report.json",
        ],
    }
