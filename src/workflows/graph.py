"""工作流主链与统一执行入口。

文件位置：
- `src/workflows/graph.py`

核心职责：
- 只保留 v2 固定主链
- 统一构建 workflow 运行依赖
- 在节点切换时更新任务进度、状态和日志
- 允许节点在内部上报增量进度，用于前端实时刷新
"""

from __future__ import annotations

import logging
from dataclasses import replace
from functools import lru_cache
from time import perf_counter
from typing import Callable

from langgraph.graph import END, StateGraph

from src.core.config import get_settings, reload_settings
from src.core.logging import initialize_logging, log_context
from src.domain.task import TaskStatus
from src.providers.router import build_capability_bindings
from src.services.rendering.text_renderer import TextRenderer
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.director_v2 import director_v2
from src.workflows.nodes.finalize import finalize
from src.workflows.nodes.ingest_assets import ingest_assets
from src.workflows.nodes.prompt_refine_v2 import prompt_refine_v2
from src.workflows.nodes.render_images import render_images
from src.workflows.nodes.run_qc import run_qc
from src.workflows.state import (
    WorkflowDependencies,
    WorkflowExecutionError,
    WorkflowState,
    append_log,
    format_workflow_log,
    get_task_id_from_state,
    update_task_progress,
)

NodeHandler = Callable[[WorkflowState, WorkflowDependencies], dict]
logger = logging.getLogger(__name__)

NODE_SEQUENCE: tuple[tuple[str, NodeHandler], ...] = (
    ("ingest_assets", ingest_assets),
    ("director_v2", director_v2),
    ("prompt_refine_v2", prompt_refine_v2),
    ("render_images", render_images),
    ("run_qc", run_qc),
    ("finalize", finalize),
)

USER_FACING_ERRORS: dict[str, str] = {
    "ingest_assets": "素材缺失或格式不符合要求，请检查上传内容后重试。",
    "director_v2": "商品分析失败，请重试或检查素材是否清晰。",
    "prompt_refine_v2": "提示词生成失败，请重试。",
    "render_images": "图片生成失败，请重试或检查素材和模型配置。",
    "run_qc": "结果整理失败，请重试。",
    "finalize": "结果导出失败，请重试。",
}


def build_dependencies() -> WorkflowDependencies:
    """构建 v2 workflow 运行依赖。"""

    settings = get_settings()
    initialize_logging(settings)
    bindings = build_capability_bindings(settings)
    return WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=bindings.planning_provider,
        image_generation_provider=bindings.image_generation_provider,
        text_renderer=TextRenderer(settings.default_font_path),
        text_provider_mode=bindings.planning_route.mode,
        image_provider_mode=bindings.image_route.mode,
        planning_provider_name=bindings.planning_provider_name,
        image_provider_name=bindings.image_provider_name,
        planning_route=bindings.planning_route,
        image_route=bindings.image_route,
        planning_model_selection=bindings.planning_model_selection,
        image_model_selection=bindings.image_model_selection,
    )


def build_workflow() -> object:
    """构建 LangGraph 固定主链。"""

    deps = build_dependencies()
    graph = StateGraph(WorkflowState)
    for node_name, handler in NODE_SEQUENCE:
        graph.add_node(node_name, _wrap_node(node_name, handler, deps))
    graph.set_entry_point("ingest_assets")
    for index, (node_name, _) in enumerate(NODE_SEQUENCE[:-1]):
        graph.add_edge(node_name, NODE_SEQUENCE[index + 1][0])
    graph.add_edge(NODE_SEQUENCE[-1][0], END)
    return graph.compile()


@lru_cache(maxsize=1)
def get_compiled_workflow() -> object:
    """返回缓存后的 LangGraph 实例。"""

    return build_workflow()


def reload_runtime() -> None:
    """清理配置与 workflow 缓存。"""

    reload_settings()
    get_compiled_workflow.cache_clear()


def run_workflow(
    initial_state: WorkflowState,
    *,
    on_progress: Callable[[WorkflowState], None] | None = None,
) -> WorkflowState:
    """按固定顺序执行 v2 workflow。"""

    deps = build_dependencies()
    state = initial_state
    for node_name, handler in NODE_SEQUENCE:
        updates = _run_node(node_name, handler, state, deps, on_progress=on_progress)
        state = {**state, **updates}
    return state


def _wrap_node(node_name: str, handler: NodeHandler, deps: WorkflowDependencies):
    """为 LangGraph 节点包装统一执行器。"""

    def _runner(state: WorkflowState) -> dict:
        return _run_node(node_name, handler, state, deps, on_progress=None)

    return _runner


def _run_node(
    node_name: str,
    handler: NodeHandler,
    state: WorkflowState,
    deps: WorkflowDependencies,
    *,
    on_progress: Callable[[WorkflowState], None] | None,
) -> dict:
    """执行单个节点，并统一处理进度、日志和失败回写。"""

    task_id = get_task_id_from_state(state)
    task = state["task"]
    started_task = update_task_progress(task, step=node_name, status=TaskStatus.RUNNING)
    started_log = format_workflow_log(task_id=task_id, node_name=node_name, event="start")
    started_state: WorkflowState = {
        **state,
        "task": started_task,
        "current_step": started_task.current_step,
        "current_step_label": started_task.current_step_label,
        "progress_percent": started_task.progress_percent,
        "error_message": "",
        "logs": append_log(state.get("logs"), started_log),
    }
    deps.storage.save_task_manifest(started_task)
    if on_progress is not None:
        on_progress(started_state)

    runtime_deps = replace(deps, progress_callback=None)
    if on_progress is not None:
        runtime_deps = replace(deps, progress_callback=lambda progress_state: _publish_progress(deps, on_progress, progress_state))

    with log_context(task_id=task_id, node_name=node_name):
        started_at = perf_counter()
        try:
            updates = handler(started_state, runtime_deps)
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("Workflow node failed: node=%s task_id=%s", node_name, task_id)
            failed_task = update_task_progress(
                started_task,
                step=node_name,
                status=TaskStatus.FAILED,
                error_message=USER_FACING_ERRORS.get(node_name, "生成失败，请重试或检查素材/配置。"),
            )
            error_log = format_workflow_log(
                task_id=task_id,
                node_name=node_name,
                event="error",
                detail=str(exc),
                elapsed_ms=elapsed_ms,
                level="ERROR",
            )
            failed_state: WorkflowState = {
                **started_state,
                "task": failed_task,
                "error_message": failed_task.error_message,
                "logs": append_log(started_state.get("logs"), error_log),
            }
            deps.storage.save_task_manifest(failed_task)
            if on_progress is not None:
                on_progress(failed_state)
            raise WorkflowExecutionError(
                failed_task.error_message,
                logs=failed_state["logs"],
                task_state=failed_state,
                task_id=task_id,
                node_name=node_name,
            ) from exc

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    finished_log = format_workflow_log(
        task_id=task_id,
        node_name=node_name,
        event="finish",
        elapsed_ms=elapsed_ms,
    )
    merged_logs = append_log(updates.get("logs", started_state.get("logs")), finished_log)
    result: WorkflowState = {
        **updates,
        "logs": merged_logs,
        "current_step": started_task.current_step,
        "current_step_label": started_task.current_step_label,
        "progress_percent": started_task.progress_percent,
        "error_message": "",
    }
    persisted_task = result.get("task", started_task)
    deps.storage.save_task_manifest(persisted_task)
    if on_progress is not None:
        on_progress({**started_state, **result, "task": persisted_task})
    return result


def _publish_progress(
    deps: WorkflowDependencies,
    on_progress: Callable[[WorkflowState], None],
    progress_state: WorkflowState,
) -> None:
    """发布节点内部的增量进度，并同步持久化最新任务状态。"""

    task = progress_state.get("task")
    if task is not None:
        deps.storage.save_task_manifest(task)
    on_progress(progress_state)
