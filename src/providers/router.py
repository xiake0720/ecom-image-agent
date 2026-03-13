from __future__ import annotations

from dataclasses import dataclass
import logging

from src.core.config import ResolvedModelSelection, ResolvedProviderRoute, Settings
from src.providers.image.base import BaseImageProvider
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.base import BaseTextProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider
from src.providers.llm.ollama_text import OllamaTextProvider
from src.providers.llm.zhipu_text import ZhipuTextProvider
from src.providers.vision.base import BaseVisionAnalysisProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapabilityBindings:
    planning_provider: BaseTextProvider
    vision_analysis_provider: BaseVisionAnalysisProvider | None
    image_generation_provider: BaseImageProvider
    planning_provider_name: str
    vision_provider_name: str
    image_provider_name: str
    planning_route: ResolvedProviderRoute
    vision_route: ResolvedProviderRoute
    image_route: ResolvedProviderRoute
    planning_provider_status: str
    vision_provider_status: str
    image_provider_status: str
    planning_model_selection: ResolvedModelSelection
    vision_model_selection: ResolvedModelSelection
    image_model_selection: ResolvedModelSelection


def build_capability_bindings(settings: Settings) -> CapabilityBindings:
    planning_provider, planning_route, planning_status, planning_selection = _build_planning_provider(settings)
    vision_provider, vision_route, vision_status, vision_selection = _build_vision_provider(settings)
    image_provider, image_route, image_status, image_selection = _build_image_provider(settings)
    logger.info(
        "能力路由构建完成，结构化规划=%s[%s](%s)，视觉分析=%s[%s](%s)，图片生成=%s[%s](%s)",
        type(planning_provider).__name__,
        planning_route.alias,
        planning_selection.model_id,
        type(vision_provider).__name__ if vision_provider is not None else "None",
        vision_route.alias,
        vision_selection.model_id,
        type(image_provider).__name__,
        image_route.alias,
        image_selection.model_id,
    )
    return CapabilityBindings(
        planning_provider=planning_provider,
        vision_analysis_provider=vision_provider,
        image_generation_provider=image_provider,
        planning_provider_name=type(planning_provider).__name__,
        vision_provider_name=type(vision_provider).__name__ if vision_provider is not None else "None",
        image_provider_name=type(image_provider).__name__,
        planning_route=planning_route,
        vision_route=vision_route,
        image_route=image_route,
        planning_provider_status=planning_status,
        vision_provider_status=vision_status,
        image_provider_status=image_status,
        planning_model_selection=planning_selection,
        vision_model_selection=vision_selection,
        image_model_selection=image_selection,
    )


def _build_planning_provider(
    settings: Settings,
) -> tuple[BaseTextProvider, ResolvedProviderRoute, str, ResolvedModelSelection]:
    route = settings.resolve_text_provider_route()
    selection = settings.resolve_text_model_selection()
    if route.mode != "real":
        logger.info(
            "当前结构化规划能力使用本地 mock provider，请求别名=%s，已解析模型=%s，model_id=%s，来源=%s",
            route.alias,
            selection.label,
            selection.model_id,
            selection.source,
        )
        return GeminiTextProvider(), route, "mock-local", selection

    if route.alias == "nvidia":
        logger.info("当前结构化规划模型：%s，model_id=%s，来源=%s", selection.label, selection.model_id, selection.source)
        return NVIDIATextProvider(settings), route, "ready", selection
    if route.alias == "ollama":
        logger.info("当前结构化规划能力切换为 Ollama，model_id=%s，来源=%s", selection.model_id, selection.source)
        return OllamaTextProvider(settings), route, "ready", selection
    if route.alias in {"zhipu", "zhipu_glm47_flash", "zhipu_glm47"}:
        logger.info("当前结构化规划能力切换为 Zhipu，model_id=%s，来源=%s", selection.model_id, selection.source)
        return ZhipuTextProvider(settings), route, "ready", selection
    if route.alias == "dashscope":
        logger.warning("当前文本 provider 已进入配置路由，但当前阶段尚未接线：alias=%s", route.alias)
        return _UnsupportedTextProvider(route.alias), route, "planned-not-wired", selection
    raise RuntimeError(f"Unsupported text provider alias: {route.alias}")


def _build_vision_provider(
    settings: Settings,
) -> tuple[BaseVisionAnalysisProvider | None, ResolvedProviderRoute, str, ResolvedModelSelection]:
    route = settings.resolve_vision_provider_route()
    selection = settings.resolve_vision_model_selection()
    if route.mode != "real":
        logger.info(
            "当前视觉能力使用本地 mock 路径，请求别名=%s，已解析真实模型=%s，model_id=%s，来源=%s",
            route.alias,
            selection.label,
            selection.model_id,
            selection.source,
        )
        return None, route, "mock-local", selection

    if route.alias == "nvidia":
        logger.info(
            "开始加载真实视觉 provider，provider_key=%s，model_id=%s，期望模块路径=src/providers/vision/nvidia_product_analysis.py",
            selection.provider_key,
            selection.model_id,
        )
        try:
            from src.providers.vision.nvidia_product_analysis import NVIDIAVisionProductAnalysisProvider
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE=real, but the vision provider "
                "module is missing. Expected file: src/providers/vision/nvidia_product_analysis.py"
            ) from exc

        logger.info("当前视觉分析模型：%s，model_id=%s，来源=%s", selection.label, selection.model_id, selection.source)
        return NVIDIAVisionProductAnalysisProvider(settings), route, "ready", selection

    if route.alias in {"dashscope", "zhipu"}:
        logger.warning("当前视觉 provider 已进入配置路由，但当前阶段尚未接线：alias=%s", route.alias)
        return _UnsupportedVisionProvider(route.alias), route, "planned-not-wired", selection

    raise RuntimeError(f"Unsupported vision provider alias: {route.alias}")


def _build_image_provider(
    settings: Settings,
) -> tuple[BaseImageProvider, ResolvedProviderRoute, str, ResolvedModelSelection]:
    route = settings.resolve_image_provider_route()
    selection = settings.resolve_image_model_selection()
    if route.mode != "real" or route.alias == "mock":
        logger.info("当前图片生成能力使用本地 mock provider，请求别名=%s", route.alias)
        return GeminiImageProvider(), route, "mock-local", selection
    if route.alias == "runapi":
        logger.info("当前图片生成能力继续使用 RunAPI，model_id=%s", settings.runapi_image_model)
        return RunApiGeminiImageProvider(settings), route, "ready", selection
    if route.alias in {"dashscope", "zhipu"}:
        logger.warning("当前图片 provider 已进入配置路由，但当前阶段尚未接线：alias=%s", route.alias)
        return _UnsupportedImageProvider(route.alias), route, "planned-not-wired", selection
    raise RuntimeError(f"Unsupported image provider alias: {route.alias}")


class _UnsupportedTextProvider(BaseTextProvider):
    def __init__(self, alias: str) -> None:
        self.alias = alias

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        raise RuntimeError(
            f"文本 provider `{self.alias}` 已进入配置与路由体系，但当前阶段尚未接入真实调用实现。"
        )


class _UnsupportedVisionProvider(BaseVisionAnalysisProvider):
    def __init__(self, alias: str) -> None:
        self.alias = alias

    def generate_structured_from_assets(self, prompt: str, response_model, *, assets, system_prompt: str | None = None):
        raise RuntimeError(
            f"视觉 provider `{self.alias}` 已进入配置与路由体系，但当前阶段尚未接入真实调用实现。"
        )


class _UnsupportedImageProvider(BaseImageProvider):
    def __init__(self, alias: str) -> None:
        self.alias = alias

    def generate_images(self, plan, *, output_dir, reference_assets=None):
        raise RuntimeError(
            f"图片 provider `{self.alias}` 已进入配置与路由体系，但当前阶段尚未接入真实调用实现。"
        )
