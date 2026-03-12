"""模型能力路由层。

当前模块只负责最小能力选择，不引入多模型 fallback，也不改动 workflow 节点顺序。
目标是把“模型开关”和“具体 provider 类”集中收敛到这里，减少后续切换模型时的改动量。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from src.core.config import ResolvedModelSelection, Settings
from src.providers.image.base import BaseImageProvider
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.base import BaseTextProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider
from src.providers.vision.base import BaseVisionAnalysisProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapabilityBindings:
    """当前工作流各能力位的实际 provider 绑定结果。"""

    planning_provider: BaseTextProvider
    vision_analysis_provider: BaseVisionAnalysisProvider | None
    image_generation_provider: BaseImageProvider
    planning_provider_name: str
    vision_provider_name: str
    image_provider_name: str
    planning_model_selection: ResolvedModelSelection
    vision_model_selection: ResolvedModelSelection


def build_capability_bindings(settings: Settings) -> CapabilityBindings:
    """根据当前配置构建能力层绑定结果。"""
    planning_provider, planning_selection = _build_planning_provider(settings)
    vision_provider, vision_selection = _build_vision_provider(settings)
    image_provider = _build_image_provider(settings)
    logger.info(
        "能力路由构建完成，结构化规划=%s(%s)，视觉分析=%s(%s)，图片生成=%s(%s)",
        type(planning_provider).__name__,
        planning_selection.model_id,
        type(vision_provider).__name__ if vision_provider is not None else "None",
        vision_selection.model_id,
        type(image_provider).__name__,
        settings.runapi_image_model if settings.image_provider_mode == "real" else "mock-local",
    )
    return CapabilityBindings(
        planning_provider=planning_provider,
        vision_analysis_provider=vision_provider,
        image_generation_provider=image_provider,
        planning_provider_name=type(planning_provider).__name__,
        vision_provider_name=type(vision_provider).__name__ if vision_provider is not None else "None",
        image_provider_name=type(image_provider).__name__,
        planning_model_selection=planning_selection,
        vision_model_selection=vision_selection,
    )


def _build_planning_provider(settings: Settings) -> tuple[BaseTextProvider, ResolvedModelSelection]:
    selection = settings.resolve_text_model_selection()
    if settings.text_provider_mode != "real":
        logger.info(
            "当前结构化规划能力使用本地 mock provider，已解析真实模型=%s，model_id=%s，来源=%s",
            selection.label,
            selection.model_id,
            selection.source,
        )
        return GeminiTextProvider(), selection
    if selection.provider_key == "glm5":
        logger.info("当前文本模型开关已切换为 GLM-5，model_id=%s，来源=%s", selection.model_id, selection.source)
    else:
        logger.info("当前结构化规划模型：%s，model_id=%s，来源=%s", selection.label, selection.model_id, selection.source)
    return NVIDIATextProvider(settings), selection


def _build_vision_provider(
    settings: Settings,
) -> tuple[BaseVisionAnalysisProvider | None, ResolvedModelSelection]:
    selection = settings.resolve_vision_model_selection()
    if settings.vision_provider_mode != "real":
        logger.info(
            "当前视觉能力使用本地 mock 路径，已解析真实模型=%s，model_id=%s，来源=%s",
            selection.label,
            selection.model_id,
            selection.source,
        )
        return None, selection

    try:
        logger.info(
            "开始加载真实视觉 provider，provider_key=%s，model_id=%s，期望模块路径=src/providers/vision/nvidia_product_analysis.py",
            selection.provider_key,
            selection.model_id,
        )
        from src.providers.vision.nvidia_product_analysis import (
            NVIDIAVisionProductAnalysisProvider,
        )
    except ModuleNotFoundError as exc:
        logger.exception("真实视觉 provider 加载失败：缺少标准文件 src/providers/vision/nvidia_product_analysis.py")
        raise RuntimeError(
            "ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE=real, but the vision provider "
            "module is missing. Expected file: src/providers/vision/"
            "nvidia_product_analysis.py"
        ) from exc

    logger.info("当前视觉分析模型：%s，model_id=%s，来源=%s", selection.label, selection.model_id, selection.source)
    return NVIDIAVisionProductAnalysisProvider(settings), selection


def _build_image_provider(settings: Settings) -> BaseImageProvider:
    if settings.image_provider_mode == "real":
        logger.info("当前图片生成能力继续使用 RunAPI，model_id=%s", settings.runapi_image_model)
        return RunApiGeminiImageProvider(settings)
    logger.info("当前图片生成能力使用本地 mock provider")
    return GeminiImageProvider()
