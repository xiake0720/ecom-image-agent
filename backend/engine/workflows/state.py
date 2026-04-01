"""Workflow 状态、依赖容器与进度工具。

文件位置：
- `src/workflows/state.py`

职责：
- 定义 workflow 节点之间共享的最小状态
- 定义 workflow 运行时依赖容器
- 提供统一的进度、日志和任务状态回写工具
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypedDict

from backend.engine.core.config import ResolvedModelSelection, ResolvedProviderRoute
from backend.engine.domain.asset import Asset
from backend.engine.domain.director_output import DirectorOutput
from backend.engine.domain.generation_result import GenerationResult
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2
from backend.engine.domain.qc_report import QCReport
from backend.engine.domain.task import Task, TaskStatus

CORE_CONTRACT_ARTIFACTS: dict[str, str] = {
    "director_output": "director_output.json",
    "prompt_plan_v2": "prompt_plan_v2.json",
    "generation_result_v2": "final/",
    "qc_report_v2": "qc_report.json",
}

STEP_PROGRESS: dict[str, tuple[int, str]] = {
    "ingest_assets": (10, "正在校验素材"),
    "director_v2": (30, "正在分析产品与规划图组"),
    "prompt_refine_v2": (55, "正在生成每张图提示词"),
    "render_images": (85, "正在生成图片"),
    "run_qc": (100, "正在质检与整理结果"),
    "finalize": (100, "正在质检与整理结果"),
}


class WorkflowState(TypedDict, total=False):
    """LangGraph 节点间共享的最小状态。"""

    task: Task
    assets: list[Asset]
    uploaded_files: list[str]
    logs: list[str]
    cache_enabled: bool
    ignore_cache: bool
    current_step: str
    current_step_label: str
    progress_percent: int
    director_output: DirectorOutput
    prompt_plan_v2: PromptPlanV2
    generation_result: GenerationResult
    generation_result_v2: GenerationResult
    qc_report: QCReport
    qc_report_v2: QCReport
    text_render_reports: dict[str, dict[str, object]]
    export_zip_path: str
    full_task_bundle_zip_path: str
    error_message: str


ProgressCallback = Callable[[WorkflowState], None]


@dataclass
class WorkflowDependencies:
    """Workflow 运行时依赖容器。"""

    storage: object
    planning_provider: object
    image_generation_provider: object
    text_renderer: object
    text_provider_mode: str
    image_provider_mode: str
    planning_provider_name: str = ""
    image_provider_name: str = ""
    planning_route: ResolvedProviderRoute | None = None
    image_route: ResolvedProviderRoute | None = None
    planning_model_selection: ResolvedModelSelection | None = None
    image_model_selection: ResolvedModelSelection | None = None
    progress_callback: ProgressCallback | None = None


class WorkflowExecutionError(RuntimeError):
    """包装节点失败信息，供 UI 统一展示。"""

    def __init__(
        self,
        message: str,
        *,
        logs: list[str],
        task_state: WorkflowState | None = None,
        task_id: str | None = None,
        node_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.logs = logs
        self.task_state = task_state
        self.task_id = task_id
        self.node_name = node_name


def get_task_id_from_state(state: WorkflowState) -> str:
    """从 workflow state 中稳定提取 task_id。"""

    task = state.get("task")
    if hasattr(task, "task_id"):
        return str(task.task_id)
    if isinstance(task, dict):
        return str(task.get("task_id", "unknown-task"))
    return "unknown-task"


def append_log(logs: list[str] | None, message: str) -> list[str]:
    """向日志列表追加一条日志。"""

    return [*(logs or []), message]


def format_workflow_log(
    *,
    task_id: str,
    node_name: str,
    event: str,
    detail: str | None = None,
    elapsed_ms: int | None = None,
    level: str = "INFO",
) -> str:
    """生成统一格式的 workflow 日志行。"""

    parts = [f"[{level}]", f"task_id={task_id}", f"node={node_name}", f"event={event}"]
    if elapsed_ms is not None:
        parts.append(f"elapsed_ms={elapsed_ms}")
    if detail:
        parts.append(f"detail={detail}")
    return " | ".join(parts)


def update_task_progress(
    task: Task,
    *,
    step: str,
    status: TaskStatus | None = None,
    error_message: str | None = None,
    step_label: str | None = None,
    progress_percent: int | None = None,
) -> Task:
    """根据节点信息更新任务进度。"""

    default_progress, default_label = STEP_PROGRESS.get(step, (task.progress_percent, task.current_step_label))
    return task.model_copy(
        update={
            "status": status or task.status,
            "current_step": step,
            "current_step_label": step_label or default_label,
            "progress_percent": default_progress if progress_percent is None else progress_percent,
            "error_message": error_message or "",
        }
    )


def build_render_progress_task(task: Task, *, completed_count: int, total_count: int) -> Task:
    """构造 `render_images` 节点内部的增量进度。"""

    safe_total = max(total_count, 1)
    safe_completed = max(0, min(completed_count, safe_total))
    return update_task_progress(
        task,
        step="render_images",
        step_label=f"正在生成图片（{safe_completed}/{safe_total}）",
        progress_percent=STEP_PROGRESS["render_images"][0],
    )


def build_connected_contract_summary(state: WorkflowState) -> dict[str, object]:
    """汇总当前 state 中已接入的核心 contract。"""

    connected_files = [
        filename
        for state_key, filename in CORE_CONTRACT_ARTIFACTS.items()
        if state.get(state_key) is not None
    ]
    return {"connected_contract_files": connected_files}


def format_connected_contract_logs(state: WorkflowState, *, node_name: str) -> list[str]:
    """把已接入 contract 摘要格式化成日志。"""

    summary = build_connected_contract_summary(state)
    return [f"[{node_name}] connected_contract_files={summary['connected_contract_files']}"]
