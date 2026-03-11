from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph

from src.core.config import get_settings
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.llm.gemini_text import GeminiTextProvider
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
from src.workflows.state import WorkflowDependencies, WorkflowState


def build_dependencies() -> WorkflowDependencies:
    settings = get_settings()
    return WorkflowDependencies(
        storage=LocalStorageService(),
        text_provider=GeminiTextProvider(),
        image_provider=GeminiImageProvider(),
        text_renderer=TextRenderer(settings.default_font_path),
        ocr_service=PaddleOCRService(enabled=settings.enable_ocr_qc),
    )


@lru_cache(maxsize=1)
def build_workflow():
    deps = build_dependencies()
    graph = StateGraph(WorkflowState)
    graph.add_node("ingest_assets", lambda state: ingest_assets(state, deps))
    graph.add_node("analyze_product", lambda state: analyze_product(state, deps))
    graph.add_node("plan_shots", lambda state: plan_shots(state, deps))
    graph.add_node("generate_copy", lambda state: generate_copy(state, deps))
    graph.add_node("generate_layout", lambda state: generate_layout(state, deps))
    graph.add_node("build_prompts", lambda state: build_prompts(state, deps))
    graph.add_node("render_images", lambda state: render_images(state, deps))
    graph.add_node("overlay_text", lambda state: overlay_text(state, deps))
    graph.add_node("run_qc", lambda state: run_qc(state, deps))
    graph.add_node("finalize", lambda state: finalize(state, deps))

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
