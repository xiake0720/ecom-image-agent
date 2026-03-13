"""Workflow 图构建与节点执行包装模块。"""

from __future__ import annotations

import logging
from functools import lru_cache
from time import perf_counter
from typing import Callable

from langgraph.graph import END, StateGraph

from src.core.config import get_settings, reload_settings
from src.core.logging import initialize_logging, log_context
from src.providers.router import build_capability_bindings
from src.services.ocr.paddle_ocr_service import PaddleOCRService
from src.services.rendering.text_renderer import TextRenderer
from src.services.storage.local_storage import LocalStorageService
from src.workflows.nodes.analyze_product import analyze_product
from src.workflows.nodes.build_prompts import build_prompts
from src.workflows.nodes.finalize import finalize
from src.workflows.nodes.generate_copy import generate_copy
from src.workflows.nodes.generate_layout import generate_layout
from src.workflows.nodes.ingest_assets import ingest_assets
from src.workflows.nodes.overlay_text import overlay_text
from src.workflows.nodes.plan_shots import plan_shots
from src.workflows.nodes.render_images import render_images
from src.workflows.nodes.run_qc import run_qc
from src.workflows.state import (
    WorkflowDependencies,
    WorkflowExecutionError,
    WorkflowState,
    append_log,
    format_workflow_log,
    get_task_id_from_state,
)

NodeHandler = Callable[[WorkflowState, WorkflowDependencies], dict]
logger = logging.getLogger(__name__)

NODE_OUTPUT_HINTS: dict[str, str] = {
    "ingest_assets": "inputs/, task.json",
    "analyze_product": "product_analysis.json",
    "plan_shots": "shot_plan.json",
    "generate_copy": "copy_plan.json",
    "generate_layout": "layout_plan.json",
    "build_prompts": "image_prompt_plan.json, artifacts/shots/",
    "render_images": "generated/ or generated_preview/",
    "overlay_text": "final/ or final_preview/",
    "run_qc": "qc_report.json or qc_report_preview.json",
    "finalize": "task.json, exports/",
}


def build_dependencies() -> WorkflowDependencies:
    settings = get_settings()
    initialize_logging(settings)
    bindings = build_capability_bindings(settings)
    return WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=bindings.planning_provider,
        vision_analysis_provider=bindings.vision_analysis_provider,
        image_generation_provider=bindings.image_generation_provider,
        text_renderer=TextRenderer(settings.default_font_path),
        ocr_service=PaddleOCRService(enabled=settings.enable_ocr_qc),
        text_provider_mode=bindings.planning_route.mode,
        vision_provider_mode=bindings.vision_route.mode,
        image_provider_mode=bindings.image_route.mode,
        planning_provider_name=bindings.planning_provider_name,
        vision_provider_name=bindings.vision_provider_name,
        image_provider_name=bindings.image_provider_name,
        planning_route=bindings.planning_route,
        vision_route=bindings.vision_route,
        image_route=bindings.image_route,
        planning_provider_status=bindings.planning_provider_status,
        vision_provider_status=bindings.vision_provider_status,
        image_provider_status=bindings.image_provider_status,
        planning_model_selection=bindings.planning_model_selection,
        vision_model_selection=bindings.vision_model_selection,
        image_model_selection=bindings.image_model_selection,
    )


def _wrap_node(node_name: str, handler: NodeHandler, deps: WorkflowDependencies):
    def _runner(state: WorkflowState) -> dict:
        task_id = get_task_id_from_state(state)
        with log_context(task_id=task_id, node_name=node_name):
            start_log = format_workflow_log(
                task_id=task_id,
                node_name=node_name,
                event="start",
                detail=(
                    "节点开始执行，"
                    f"text_provider_mode={deps.text_provider_mode}, "
                    f"vision_provider_mode={deps.vision_provider_mode}, "
                    f"image_provider_mode={deps.image_provider_mode}, "
                    f"text_provider_alias={deps.planning_route.alias if deps.planning_route else '-'}, "
                    f"vision_provider_alias={deps.vision_route.alias if deps.vision_route else '-'}, "
                    f"image_provider_alias={deps.image_route.alias if deps.image_route else '-'}"
                ),
            )
            started_state: WorkflowState = {
                **state,
                "logs": append_log(state.get("logs"), start_log),
            }
            started_at = perf_counter()
            try:
                updates = handler(started_state, deps)
            except Exception as exc:
                elapsed_ms = int((perf_counter() - started_at) * 1000)
                error_log = format_workflow_log(
                    task_id=task_id,
                    node_name=node_name,
                    event="error",
                    detail=f"节点执行失败，原因：{exc}",
                    elapsed_ms=elapsed_ms,
                    level="ERROR",
                )
                raise WorkflowExecutionError(
                    f"{node_name} failed for task {task_id}: {exc}",
                    logs=append_log(started_state.get("logs"), error_log),
                    task_id=task_id,
                    node_name=node_name,
                ) from exc

            elapsed_ms = int((perf_counter() - started_at) * 1000)
            end_log = format_workflow_log(
                task_id=task_id,
                node_name=node_name,
                event="finish",
                output_hint=NODE_OUTPUT_HINTS.get(node_name),
                detail="节点执行完成",
                elapsed_ms=elapsed_ms,
            )
            return {
                **updates,
                "logs": append_log(updates.get("logs", started_state.get("logs")), end_log),
            }

    return _runner


@lru_cache(maxsize=1)
def build_workflow():
    deps = build_dependencies()
    graph = StateGraph(WorkflowState)
    graph.add_node("ingest_assets", _wrap_node("ingest_assets", ingest_assets, deps))
    graph.add_node("analyze_product", _wrap_node("analyze_product", analyze_product, deps))
    graph.add_node("plan_shots", _wrap_node("plan_shots", plan_shots, deps))
    graph.add_node("generate_copy", _wrap_node("generate_copy", generate_copy, deps))
    graph.add_node("generate_layout", _wrap_node("generate_layout", generate_layout, deps))
    graph.add_node("build_prompts", _wrap_node("build_prompts", build_prompts, deps))
    graph.add_node("render_images", _wrap_node("render_images", render_images, deps))
    graph.add_node("overlay_text", _wrap_node("overlay_text", overlay_text, deps))
    graph.add_node("run_qc", _wrap_node("run_qc", run_qc, deps))
    graph.add_node("finalize", _wrap_node("finalize", finalize, deps))

    graph.set_entry_point("ingest_assets")
    graph.add_edge("ingest_assets", "analyze_product")
    graph.add_edge("analyze_product", "plan_shots")
    graph.add_edge("plan_shots", "generate_copy")
    graph.add_edge("generate_copy", "generate_layout")
    graph.add_edge("generate_layout", "build_prompts")
    graph.add_edge("build_prompts", "render_images")
    graph.add_edge("render_images", "overlay_text")
    graph.add_edge("overlay_text", "run_qc")
    graph.add_edge("run_qc", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def reload_runtime() -> None:
    reload_settings()
    build_workflow.cache_clear()
    logger.info("配置缓存与 workflow 缓存已清理，下一次调用将按最新配置重建。")


def run_render_stage_only(initial_state: WorkflowState) -> WorkflowState:
    """仅执行 render_images 之后的渲染后半段，用于 preview 后继续生成正式成品。"""
    deps = build_dependencies()
    state = initial_state
    for node_name, handler in (
        ("render_images", render_images),
        ("overlay_text", overlay_text),
        ("run_qc", run_qc),
        ("finalize", finalize),
    ):
        runner = _wrap_node(node_name, handler, deps)
        updates = runner(state)
        state = {
            **state,
            **updates,
        }
    return state
