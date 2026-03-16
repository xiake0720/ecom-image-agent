"""Workflow 状态、依赖与统一日志格式定义。

文件位置：
- `src/workflows/state.py`

核心职责：
- 定义 LangGraph 节点之间传递的 `WorkflowState`
- 定义 workflow 运行期依赖容器 `WorkflowDependencies`
- 提供统一的 contract 接入摘要工具，便于日志、结果页和调试面板复用

主要被谁调用：
- `src/workflows/graph.py`
- 所有 `src/workflows/nodes/*.py`
- UI 结果页调试信息构建
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
from src.domain.shot_prompt_specs import ShotPromptSpecPlan
from src.domain.shot_plan import ShotPlan
from src.domain.style_architecture import StyleArchitecture
from src.domain.task import Task

CORE_CONTRACT_ARTIFACTS: dict[str, str] = {
    "product_analysis": "product_analysis.json",
    "style_architecture": "style_architecture.json",
    "shot_plan": "shot_plan.json",
    "shot_prompt_specs": "shot_prompt_specs.json",
}


class WorkflowState(TypedDict, total=False):
    """LangGraph 在节点之间传递的共享状态。

    对 Java 开发者可以把它理解成整条 pipeline 的共享上下文对象。
    本文件里显式声明这些字段，是为了让“哪个节点写了什么、下游哪个节点又读了什么”可追踪。
    """

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
    analyze_asset_completeness_mode: str
    analyze_max_reference_images: int
    render_max_reference_images: int
    preview_generation_result: GenerationResult
    product_analysis: ProductAnalysis
    product_lock: ProductAnalysis
    style_architecture: StyleArchitecture
    shot_plan: ShotPlan
    copy_plan: CopyPlan
    layout_plan: LayoutPlan
    shot_prompt_specs: ShotPromptSpecPlan
    image_prompt_plan: ImagePromptPlan
    generation_result: GenerationResult
    qc_report: QCReport
    export_zip_path: str


@dataclass
class WorkflowDependencies:
    """Workflow 运行时依赖容器。

    为什么需要：
    - 避免每个节点自己实例化 storage/provider/renderer
    - 让 graph 层统一注入 mock/real provider 和模型选择结果
    """

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
    """包装节点执行失败信息，供 UI 统一展示。"""

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
    """从 workflow state 中尽量稳定地取出 task_id。"""
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
    """生成统一格式的 workflow 日志行。"""
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


def build_connected_contract_summary(state: WorkflowState) -> dict[str, object]:
    """汇总当前 state 中已经接入的核心 contract。

    这组摘要用于：
    - 节点日志里统一打印“当前链路已经接了哪些 contract”
    - 结果页 debug 面板展示当前主链路 contract 接入情况
    - finalize 阶段补充任务目录产物可见性日志
    """
    connected_files = [
        filename
        for state_key, filename in CORE_CONTRACT_ARTIFACTS.items()
        if state.get(state_key) is not None
    ]
    style_connected = state.get("style_architecture") is not None
    shot_specs_ready = state.get("shot_prompt_specs") is not None
    product_lock_connected = state.get("product_lock") is not None or state.get("product_analysis") is not None
    return {
        "connected_contract_files": connected_files,
        "style_architecture_connected": style_connected,
        "shot_prompt_specs_available_for_render": shot_specs_ready,
        "product_lock_connected": product_lock_connected,
    }


def format_connected_contract_logs(state: WorkflowState, *, node_name: str) -> list[str]:
    """把当前核心 contract 接入情况格式化成统一日志。"""
    summary = build_connected_contract_summary(state)
    return [
        f"[{node_name}] connected_contract_files={summary['connected_contract_files']}",
        f"[{node_name}] style_architecture_connected={str(summary['style_architecture_connected']).lower()}",
        f"[{node_name}] shot_prompt_specs_available_for_render={str(summary['shot_prompt_specs_available_for_render']).lower()}",
        f"[{node_name}] product_lock_connected={str(summary['product_lock_connected']).lower()}",
    ]
