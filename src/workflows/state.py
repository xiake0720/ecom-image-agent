"""Workflow 状态与调试辅助定义。

该模块集中定义：
- LangGraph 在节点间传递的 `WorkflowState`
- workflow 运行时依赖 `WorkflowDependencies`
- 统一的日志格式化与异常包装

这里不承载业务逻辑，只负责让调用链、日志和错误边界更清晰。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from src.core.config import ResolvedModelSelection, ResolvedProviderRoute
from src.domain.asset import Asset
from src.domain.copy_plan import CopyPlan
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan
from src.domain.layout_plan import LayoutPlan
from src.domain.product_analysis import ProductAnalysis
from src.domain.qc_report import QCReport
from src.domain.shot_plan import ShotPlan
from src.domain.task import Task


class WorkflowState(TypedDict, total=False):
    task: Task
    assets: list[Asset]
    logs: list[str]
    cache_enabled: bool
    ignore_cache: bool
    prompt_build_mode: str
    render_mode: str
    render_variant: str
    render_generation_mode: str
    render_reference_asset_ids: list[str]
    render_image_provider_impl: str
    render_image_model_id: str
    render_selected_main_asset_id: str
    render_selected_detail_asset_id: str
    render_reference_selection_reason: str
    analyze_reference_asset_ids: list[str]
    analyze_selected_main_asset_id: str
    analyze_selected_detail_asset_id: str
    analyze_reference_selection_reason: str
    analyze_max_reference_images: int
    render_max_reference_images: int
    preview_generation_result: GenerationResult
    product_analysis: ProductAnalysis
    shot_plan: ShotPlan
    copy_plan: CopyPlan
    layout_plan: LayoutPlan
    image_prompt_plan: ImagePromptPlan
    generation_result: GenerationResult
    qc_report: QCReport
    export_zip_path: str


@dataclass
class WorkflowDependencies:
    storage: object
    planning_provider: object
    vision_analysis_provider: object | None
    image_generation_provider: object
    text_renderer: object
    ocr_service: object
    text_provider_mode: str
    vision_provider_mode: str
    image_provider_mode: str
    planning_provider_name: str = ""
    vision_provider_name: str = ""
    image_provider_name: str = ""
    planning_route: ResolvedProviderRoute | None = None
    vision_route: ResolvedProviderRoute | None = None
    image_route: ResolvedProviderRoute | None = None
    planning_provider_status: str = ""
    vision_provider_status: str = ""
    image_provider_status: str = ""
    planning_model_selection: ResolvedModelSelection | None = None
    vision_model_selection: ResolvedModelSelection | None = None
    image_model_selection: ResolvedModelSelection | None = None


class WorkflowExecutionError(RuntimeError):
    """包装 workflow 节点失败信息，便于 UI 展示部分执行日志。"""

    def __init__(
        self,
        message: str,
        *,
        logs: list[str],
        task_id: str | None = None,
        node_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.logs = logs
        self.task_id = task_id
        self.node_name = node_name


def get_task_id_from_state(state: WorkflowState) -> str:
    """从当前 workflow state 中提取 task_id。"""
    task = state.get("task")
    if hasattr(task, "task_id"):
        return str(task.task_id)
    if isinstance(task, dict):
        return str(task.get("task_id", "unknown-task"))
    return "unknown-task"


def append_log(logs: list[str] | None, message: str) -> list[str]:
    """向日志列表追加一条日志并返回新列表。"""
    return [*(logs or []), message]


def format_workflow_log(
    *,
    task_id: str,
    node_name: str,
    event: str,
    detail: str | None = None,
    output: str | None = None,
    output_hint: str | None = None,
    elapsed_ms: int | None = None,
    level: str = "INFO",
) -> str:
    """生成统一格式的 workflow 日志行。

    保留现有字符串日志格式，便于：
    - 页面直接展示
    - 异常时随 state 一起回传
    - 与标准库 logging 并行存在
    """
    parts = [
        f"[{level}]",
        f"task_id={task_id}",
        f"node={node_name}",
        f"event={event}",
    ]
    if elapsed_ms is not None:
        parts.append(f"elapsed_ms={elapsed_ms}")
    resolved_output = output_hint or output
    if resolved_output:
        parts.append(f"output={resolved_output}")
    if detail:
        parts.append(f"detail={detail}")
    return " | ".join(parts)
