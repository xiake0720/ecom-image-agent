"""详情图工作流主链与统一执行入口。"""

from __future__ import annotations

import logging
from dataclasses import replace
from functools import lru_cache
from time import perf_counter
from typing import Callable

from langgraph.graph import END, StateGraph

from backend.engine.core.config import get_settings, reload_settings
from backend.engine.core.logging import initialize_logging, log_context
from backend.engine.domain.task import TaskStatus
from backend.engine.providers.router import build_capability_bindings
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.engine.workflows.detail_nodes.detail_finalize import detail_finalize
from backend.engine.workflows.detail_nodes.detail_generate_copy import detail_generate_copy
from backend.engine.workflows.detail_nodes.detail_generate_prompt import detail_generate_prompt
from backend.engine.workflows.detail_nodes.detail_ingest_assets import detail_ingest_assets
from backend.engine.workflows.detail_nodes.detail_plan import detail_plan
from backend.engine.workflows.detail_nodes.detail_render_pages import detail_render_pages
from backend.engine.workflows.detail_nodes.detail_run_qc import detail_run_qc
from backend.engine.workflows.detail_state import (
    DetailWorkflowDependencies,
    DetailWorkflowExecutionError,
    DetailWorkflowState,
    append_detail_log,
    format_detail_workflow_log,
    get_detail_task_id_from_state,
    update_detail_task_progress,
)

NodeHandler = Callable[[DetailWorkflowState, DetailWorkflowDependencies], dict]
logger = logging.getLogger(__name__)

DETAIL_NODE_SEQUENCE: tuple[tuple[str, NodeHandler], ...] = (
    ("detail_ingest_assets", detail_ingest_assets),
    ("detail_plan", detail_plan),
    ("detail_generate_copy", detail_generate_copy),
    ("detail_generate_prompt", detail_generate_prompt),
    ("detail_render_pages", detail_render_pages),
    ("detail_run_qc", detail_run_qc),
    ("detail_finalize", detail_finalize),
)

DETAIL_USER_FACING_ERRORS: dict[str, str] = {
    "detail_ingest_assets": "详情图输入读取失败，请检查素材是否完整。",
    "detail_plan": "详情图规划失败，请检查素材、平台与茶类参数后重试。",
    "detail_generate_copy": "详情图文案生成失败，请稍后重试。",
    "detail_generate_prompt": "详情图渲染提示词生成失败，请稍后重试。",
    "detail_render_pages": "详情图渲染失败，请检查模型配置、参考图和 prompt 约束。",
    "detail_run_qc": "详情图 QC 失败，请检查生成结果后重试。",
    "detail_finalize": "详情图导出失败，请稍后重试。",
}


def build_detail_dependencies() -> DetailWorkflowDependencies:
    """构建 detail workflow 运行依赖。"""

    settings = get_settings()
    initialize_logging(settings)
    bindings = build_capability_bindings(settings)
    return DetailWorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=bindings.planning_provider,
        image_generation_provider=bindings.image_generation_provider,
        planning_provider_name=bindings.planning_provider_name,
        image_provider_name=bindings.image_provider_name,
        planning_route=bindings.planning_route,
        image_route=bindings.image_route,
        planning_model_selection=bindings.planning_model_selection,
        image_model_selection=bindings.image_model_selection,
    )


def build_detail_workflow() -> object:
    """构建 LangGraph 详情图主链。"""

    deps = build_detail_dependencies()
    graph = StateGraph(DetailWorkflowState)
    for node_name, handler in DETAIL_NODE_SEQUENCE:
        graph.add_node(node_name, _wrap_node(node_name, handler, deps))
    graph.set_entry_point("detail_ingest_assets")
    for index, (node_name, _) in enumerate(DETAIL_NODE_SEQUENCE[:-1]):
        graph.add_edge(node_name, DETAIL_NODE_SEQUENCE[index + 1][0])
    graph.add_edge(DETAIL_NODE_SEQUENCE[-1][0], END)
    return graph.compile()


@lru_cache(maxsize=1)
def get_compiled_detail_workflow() -> object:
    """返回缓存后的 detail LangGraph 实例。"""

    return build_detail_workflow()


def reload_detail_runtime() -> None:
    """清理 detail workflow 缓存。"""

    reload_settings()
    get_compiled_detail_workflow.cache_clear()


def run_detail_workflow(
    initial_state: DetailWorkflowState,
    *,
    stop_after: str | None = None,
    on_progress: Callable[[DetailWorkflowState], None] | None = None,
) -> DetailWorkflowState:
    """按固定顺序执行 detail workflow。"""

    deps = build_detail_dependencies()
    state = initial_state
    node_names = {item[0] for item in DETAIL_NODE_SEQUENCE}
    if stop_after is not None and stop_after not in node_names:
        raise RuntimeError(f"Unsupported detail stop_after node: {stop_after}")
    for node_name, handler in DETAIL_NODE_SEQUENCE:
        updates = _run_node(node_name, handler, state, deps, on_progress=on_progress)
        state = {**state, **updates}
        if stop_after == node_name:
            return _finalize_plan_only_state(state, deps, on_progress=on_progress)
    return state


def _wrap_node(node_name: str, handler: NodeHandler, deps: DetailWorkflowDependencies):
    """为 LangGraph 节点包裹统一执行器。"""

    def _runner(state: DetailWorkflowState) -> dict:
        return _run_node(node_name, handler, state, deps, on_progress=None)

    return _runner


def _run_node(
    node_name: str,
    handler: NodeHandler,
    state: DetailWorkflowState,
    deps: DetailWorkflowDependencies,
    *,
    on_progress: Callable[[DetailWorkflowState], None] | None,
) -> dict:
    """执行单个 detail 节点，并统一处理进度、日志和失败回写。"""

    task_id = get_detail_task_id_from_state(state)
    task = state["task"]
    started_task = update_detail_task_progress(task, step=node_name, status=TaskStatus.RUNNING)
    started_log = format_detail_workflow_log(task_id=task_id, node_name=node_name, event="start")
    started_state: DetailWorkflowState = {
        **state,
        "task": started_task,
        "current_step": started_task.current_step,
        "current_step_label": started_task.current_step_label,
        "progress_percent": started_task.progress_percent,
        "error_message": "",
        "logs": append_detail_log(state.get("logs"), started_log),
    }
    deps.storage.save_task_manifest(started_task)
    if on_progress is not None:
        on_progress(started_state)

    runtime_deps = replace(deps, progress_callback=None)
    if on_progress is not None:
        runtime_deps = replace(
            deps,
            progress_callback=lambda progress_state: _publish_progress(deps, on_progress, progress_state),
        )

    with log_context(task_id=task_id, node_name=node_name):
        started_at = perf_counter()
        try:
            updates = handler(started_state, runtime_deps)
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("Detail workflow node failed: node=%s task_id=%s", node_name, task_id)
            failed_message = _build_user_facing_error(node_name, exc)
            failed_task = update_detail_task_progress(
                started_task,
                step=node_name,
                status=TaskStatus.FAILED,
                error_message=failed_message,
            )
            error_log = format_detail_workflow_log(
                task_id=task_id,
                node_name=node_name,
                event="error",
                detail=str(exc),
                elapsed_ms=elapsed_ms,
                level="ERROR",
            )
            failed_state: DetailWorkflowState = {
                **started_state,
                "task": failed_task,
                "error_message": failed_task.error_message,
                "logs": append_detail_log(started_state.get("logs"), error_log),
            }
            deps.storage.save_task_manifest(failed_task)
            if on_progress is not None:
                on_progress(failed_state)
            raise DetailWorkflowExecutionError(
                failed_task.error_message,
                logs=failed_state["logs"],
                task_state=failed_state,
                task_id=task_id,
                node_name=node_name,
            ) from exc

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    finished_log = format_detail_workflow_log(task_id=task_id, node_name=node_name, event="finish", elapsed_ms=elapsed_ms)
    merged_logs = append_detail_log(updates.get("logs", started_state.get("logs")), finished_log)
    result: DetailWorkflowState = {
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
    deps: DetailWorkflowDependencies,
    on_progress: Callable[[DetailWorkflowState], None],
    progress_state: DetailWorkflowState,
) -> None:
    task = progress_state.get("task")
    if task is not None:
        deps.storage.save_task_manifest(task)
    on_progress(progress_state)


def _build_user_facing_error(node_name: str, exc: Exception) -> str:
    prefix = DETAIL_USER_FACING_ERRORS.get(node_name, "详情图任务执行失败。")
    detail = str(exc).strip()
    if detail and detail not in prefix:
        return f"{prefix} 原因：{detail}"
    return prefix


def _finalize_plan_only_state(
    state: DetailWorkflowState,
    deps: DetailWorkflowDependencies,
    *,
    on_progress: Callable[[DetailWorkflowState], None] | None,
) -> DetailWorkflowState:
    """把 `/plan` 模式停在 prompt 生成阶段时的任务状态收口为已完成。"""

    task = state["task"]
    completed_task = task.model_copy(
        update={
            "status": TaskStatus.COMPLETED,
            "current_step": "detail_generate_prompt",
            "current_step_label": "规划、文案与 Prompt 已完成",
            "progress_percent": 100,
            "error_message": "",
        }
    )
    deps.storage.save_task_manifest(completed_task)
    final_state: DetailWorkflowState = {
        **state,
        "task": completed_task,
        "current_step": completed_task.current_step,
        "current_step_label": completed_task.current_step_label,
        "progress_percent": completed_task.progress_percent,
        "error_message": "",
        "logs": append_detail_log(state.get("logs"), "[detail_generate_prompt] plan_only_completed=true"),
    }
    if on_progress is not None:
        on_progress(final_state)
    return final_state
