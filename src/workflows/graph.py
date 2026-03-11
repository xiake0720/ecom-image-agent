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
from time import perf_counter
from typing import Callable

from langgraph.graph import END, StateGraph

from src.core.config import get_settings
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider
from src.providers.vision.nvidia_product_analysis import NVIDIAVisionProductAnalysisProvider
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

NODE_OUTPUT_HINTS: dict[str, str] = {
    "ingest_assets": "inputs/, task.json",
    "analyze_product": "product_analysis.json",
    "plan_shots": "shot_plan.json",
    "generate_copy": "copy_plan.json",
    "generate_layout": "layout_plan.json",
    "build_prompts": "image_prompt_plan.json",
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
    text_provider = (
        NVIDIATextProvider(settings)
        if settings.text_provider_mode == "real"
        else GeminiTextProvider()
    )
    vision_provider = (
        NVIDIAVisionProductAnalysisProvider(settings)
        if settings.vision_provider_mode == "real"
        else None
    )
    image_provider = (
        RunApiGeminiImageProvider(settings)
        if settings.image_provider_mode == "real"
        else GeminiImageProvider()
    )
    return WorkflowDependencies(
        storage=LocalStorageService(),
        text_provider=text_provider,
        vision_provider=vision_provider,
        image_provider=image_provider,
        text_renderer=TextRenderer(settings.default_font_path),
        ocr_service=PaddleOCRService(enabled=settings.enable_ocr_qc),
        text_provider_mode=settings.text_provider_mode,
        vision_provider_mode=settings.vision_provider_mode,
        image_provider_mode=settings.image_provider_mode,
    )


def _wrap_node(node_name: str, handler: NodeHandler, deps: WorkflowDependencies):
    """为单个节点增加统一日志与异常包装。"""

    def _runner(state: WorkflowState) -> dict:
        task_id = get_task_id_from_state(state)
        start_log = format_workflow_log(
            task_id=task_id,
            node_name=node_name,
            event="start",
            detail=(
                f"text_provider_mode={deps.text_provider_mode}, "
                f"vision_provider_mode={deps.vision_provider_mode}, "
                f"image_provider_mode={deps.image_provider_mode}"
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
                detail=str(exc),
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
        output_hint = NODE_OUTPUT_HINTS.get(node_name)
        end_log = format_workflow_log(
            task_id=task_id,
            node_name=node_name,
            event="finish",
            output=output_hint,
            elapsed_ms=elapsed_ms,
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
