"""Workflow 图构建与节点执行包装模块。

该模块是 LangGraph 在当前项目中的实际接入位置，负责：
- 构建 LangGraph 图
- 注入 provider / storage / renderer 等依赖
- 根据配置选择 mock 或 real provider
- 为每个节点补齐统一的开始 / 结束 / 失败 / 耗时日志

它不改变既有 10 个节点的顺序和契约，只让调用链更容易理解和调试。
"""

from __future__ import annotations

from functools import lru_cache
import logging
from time import perf_counter
from typing import Callable

from langgraph.graph import END, StateGraph

from src.core.config import get_settings
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
    "render_images": "generated/",
    "overlay_text": "final/, previews/",
    "run_qc": "qc_report.json",
    "finalize": "task.json, exports/",
}

def build_dependencies() -> WorkflowDependencies:
    """构建 workflow 运行依赖。

    provider mode 的选择集中放在这里，避免把 mock / real 分支散落到 UI 或节点外层。
    """
    settings = get_settings()
    initialize_logging(settings)
    logger.info(
        "开始构建工作流依赖，文本模式=%s，视觉模式=%s，图片模式=%s",
        settings.text_provider_mode,
        settings.vision_provider_mode,
        settings.image_provider_mode,
    )
    bindings = build_capability_bindings(settings)
    logger.info(
        "工作流依赖构建完成，结构化规划 provider=%s，model=%s，视觉 provider=%s，model=%s，图片 provider=%s",
        bindings.planning_provider_name,
        bindings.planning_model_selection.model_id,
        bindings.vision_provider_name,
        bindings.vision_model_selection.model_id,
        bindings.image_provider_name,
    )
    return WorkflowDependencies(
        storage=LocalStorageService(),
        planning_provider=bindings.planning_provider,
        vision_analysis_provider=bindings.vision_analysis_provider,
        image_generation_provider=bindings.image_generation_provider,
        text_renderer=TextRenderer(settings.default_font_path),
        ocr_service=PaddleOCRService(enabled=settings.enable_ocr_qc),
        text_provider_mode=settings.text_provider_mode,
        vision_provider_mode=settings.vision_provider_mode,
        image_provider_mode=settings.image_provider_mode,
        planning_provider_name=bindings.planning_provider_name,
        vision_provider_name=bindings.vision_provider_name,
        image_provider_name=bindings.image_provider_name,
        planning_model_selection=bindings.planning_model_selection,
        vision_model_selection=bindings.vision_model_selection,
    )


def _wrap_node(node_name: str, handler: NodeHandler, deps: WorkflowDependencies):
    """为单个节点增加统一日志与异常包装。"""

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
                    f"planning_model={deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}, "
                    f"vision_model={deps.vision_model_selection.model_id if deps.vision_model_selection else '-'}"
                ),
            )
            logger.info(
                "节点开始：%s，文本模式=%s，视觉模式=%s，图片模式=%s，规划模型=%s，视觉模型=%s",
                node_name,
                deps.text_provider_mode,
                deps.vision_provider_mode,
                deps.image_provider_mode,
                deps.planning_model_selection.model_id if deps.planning_model_selection else "-",
                deps.vision_model_selection.model_id if deps.vision_model_selection else "-",
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
                logger.exception("节点失败：%s，耗时=%sms，原因=%s", node_name, elapsed_ms, exc)
                raise WorkflowExecutionError(
                    f"{node_name} failed for task {task_id}: {exc}",
                    logs=append_log(started_state.get("logs"), error_log),
                    task_id=task_id,
                    node_name=node_name,
                ) from exc

            elapsed_ms = int((perf_counter() - started_at) * 1000)
            output_hint = NODE_OUTPUT_HINTS.get(node_name)
            end_log = format_workflow_log(
                task_id=task_id,
                node_name=node_name,
                event="finish",
                output_hint=output_hint,
                detail="节点执行完成",
                elapsed_ms=elapsed_ms,
            )
            logger.info(
                "节点完成：%s，耗时=%sms，输出=%s",
                node_name,
                elapsed_ms,
                output_hint or "-",
            )
            return {
                **updates,
                "logs": append_log(updates.get("logs", started_state.get("logs")), end_log),
            }

    return _runner


@lru_cache(maxsize=1)
def build_workflow():
    """构建并缓存 LangGraph 工作流。

    返回值是已编译的图对象，供 UI 层直接 invoke。
    """
    deps = build_dependencies()
    logger.info("开始构建 LangGraph 工作流图")
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
    logger.info("LangGraph 工作流图构建完成，固定节点数=%s", 10)
    return graph.compile()
