"""Detail workflow 状态、依赖与进度工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypedDict

from backend.engine.core.config import ResolvedModelSelection, ResolvedProviderRoute
from backend.engine.domain.task import Task, TaskStatus
from backend.schemas.detail import (
    DetailDirectorBrief,
    DetailPageAssetRef,
    DetailPageCopyBlock,
    DetailPageJobCreatePayload,
    DetailPagePlanPayload,
    DetailPagePromptPlanItem,
    DetailPageQCSummary,
    DetailPageRenderResult,
    DetailPreflightReport,
    DetailRetryDecisionReport,
    DetailVisualReviewReport,
)

DETAIL_STEP_PROGRESS: dict[str, tuple[int, str]] = {
    "detail_ingest_assets": (10, "正在接收详情图输入"),
    "detail_plan": (28, "正在规划详情页叙事"),
    "detail_generate_copy": (44, "正在生成详情页文案"),
    "detail_generate_prompt": (60, "正在生成渲染提示词"),
    "detail_render_pages": (82, "正在渲染详情页"),
    "detail_run_qc": (92, "正在执行规则 QC"),
    "detail_finalize": (100, "正在打包与导出"),
}


class DetailWorkflowState(TypedDict, total=False):
    """详情图 workflow 节点共享状态。"""

    task: Task
    detail_payload: DetailPageJobCreatePayload
    detail_assets: list[DetailPageAssetRef]
    detail_preflight_report: DetailPreflightReport
    detail_director_brief: DetailDirectorBrief
    detail_plan: DetailPagePlanPayload
    detail_copy_blocks: list[DetailPageCopyBlock]
    detail_prompt_plan: list[DetailPagePromptPlanItem]
    detail_render_results: list[DetailPageRenderResult]
    detail_visual_review: DetailVisualReviewReport
    detail_retry_decisions: DetailRetryDecisionReport
    detail_qc_summary: DetailPageQCSummary
    logs: list[str]
    error_message: str
    current_step: str
    current_step_label: str
    progress_percent: int


DetailProgressCallback = Callable[[DetailWorkflowState], None]


@dataclass
class DetailWorkflowDependencies:
    """详情图 workflow 运行依赖。"""

    storage: object
    planning_provider: object
    image_generation_provider: object
    planning_provider_name: str
    image_provider_name: str
    planning_route: ResolvedProviderRoute | None = None
    image_route: ResolvedProviderRoute | None = None
    planning_model_selection: ResolvedModelSelection | None = None
    image_model_selection: ResolvedModelSelection | None = None
    progress_callback: DetailProgressCallback | None = None


class DetailWorkflowExecutionError(RuntimeError):
    """包装 detail workflow 节点失败信息。"""

    def __init__(
        self,
        message: str,
        *,
        logs: list[str],
        task_state: DetailWorkflowState | None = None,
        task_id: str | None = None,
        node_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.logs = logs
        self.task_state = task_state
        self.task_id = task_id
        self.node_name = node_name


def get_detail_task_id_from_state(state: DetailWorkflowState) -> str:
    """稳定提取 detail task_id。"""

    task = state.get("task")
    if hasattr(task, "task_id"):
        return str(task.task_id)
    if isinstance(task, dict):
        return str(task.get("task_id", "unknown-detail-task"))
    return "unknown-detail-task"


def append_detail_log(logs: list[str] | None, message: str) -> list[str]:
    """追加一条 detail workflow 日志。"""

    return [*(logs or []), message]


def format_detail_workflow_log(
    *,
    task_id: str,
    node_name: str,
    event: str,
    detail: str | None = None,
    elapsed_ms: int | None = None,
    level: str = "INFO",
) -> str:
    """生成 detail workflow 统一日志行。"""

    parts = [f"[{level}]", f"task_id={task_id}", f"node={node_name}", f"event={event}"]
    if elapsed_ms is not None:
        parts.append(f"elapsed_ms={elapsed_ms}")
    if detail:
        parts.append(f"detail={detail}")
    return " | ".join(parts)


def update_detail_task_progress(
    task: Task,
    *,
    step: str,
    status: TaskStatus | None = None,
    error_message: str | None = None,
    step_label: str | None = None,
    progress_percent: int | None = None,
) -> Task:
    """按节点更新 detail task 进度。"""

    default_progress, default_label = DETAIL_STEP_PROGRESS.get(step, (task.progress_percent, task.current_step_label))
    return task.model_copy(
        update={
            "status": status or task.status,
            "current_step": step,
            "current_step_label": step_label or default_label,
            "progress_percent": default_progress if progress_percent is None else progress_percent,
            "error_message": error_message or "",
        }
    )


def build_detail_render_progress_task(task: Task, *, completed_count: int, total_count: int) -> Task:
    """构造 `detail_render_pages` 节点内部的增量进度。"""

    safe_total = max(total_count, 1)
    safe_completed = max(0, min(completed_count, safe_total))
    start_progress = DETAIL_STEP_PROGRESS["detail_render_pages"][0]
    end_progress = DETAIL_STEP_PROGRESS["detail_run_qc"][0] - 2
    progress = start_progress + int(((end_progress - start_progress) * safe_completed) / safe_total)
    return update_detail_task_progress(
        task,
        step="detail_render_pages",
        step_label=f"正在渲染详情页（{safe_completed}/{safe_total}）",
        progress_percent=progress,
    )
