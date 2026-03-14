"""Provider 总路由入口。

文件位置：
- `src/providers/router.py`

核心职责：
- 根据 `Settings` 解析文本、视觉、图片三类能力应绑定的 provider
- 集中管理 mock / real 路由
- 为图片生成额外注入 `RoutedImageProvider`，统一处理 `t2i / image_edit` 分流

主要调用方：
- `src/workflows/graph.py`
- `src/ui/pages/home.py` 的运行时调试面板
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from src.core.config import ResolvedModelSelection, ResolvedProviderRoute, Settings
from src.providers.image.base import BaseImageProvider
from src.providers.image.dashscope_image import DashScopeImageProvider
from src.providers.image.dashscope_image_edit import DashScopeImageEditProvider
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.image.routed_image import RoutedImageProvider
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.base import BaseTextProvider
from src.providers.llm.dashscope_text import DashScopeTextProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider
from src.providers.llm.ollama_text import OllamaTextProvider
from src.providers.llm.zhipu_text import ZhipuTextProvider
from src.providers.vision.base import BaseVisionAnalysisProvider
from src.providers.vision.dashscope_vision import DashScopeVisionProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapabilityBindings:
    """workflow 运行时会消费的 provider 绑定结果。"""

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
    """按配置构建三类能力的 provider 绑定结果。"""
    planning_provider, planning_route, planning_status, planning_selection = _build_planning_provider(settings)
    vision_provider, vision_route, vision_status, vision_selection = _build_vision_provider(settings)
    image_provider, image_route, image_status, image_selection = _build_image_provider(settings)
    logger.info(
        "Resolved providers: planning=%s[%s](%s), vision=%s[%s](%s), image=%s[%s](%s)",
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
        return GeminiTextProvider(), route, "mock-local", selection
    if route.alias == "nvidia":
        return NVIDIATextProvider(settings), route, "ready", selection
    if route.alias == "ollama":
        return OllamaTextProvider(settings), route, "ready", selection
    if route.alias == "dashscope":
        return DashScopeTextProvider(settings), route, "ready", selection
    if route.alias in {"zhipu", "zhipu_glm47_flash", "zhipu_glm47"}:
        return ZhipuTextProvider(settings), route, "ready", selection
    raise RuntimeError(f"Unsupported text provider alias: {route.alias}")


def _build_vision_provider(
    settings: Settings,
) -> tuple[BaseVisionAnalysisProvider | None, ResolvedProviderRoute, str, ResolvedModelSelection]:
    route = settings.resolve_vision_provider_route()
    selection = settings.resolve_vision_model_selection()
    if route.mode != "real":
        return None, route, "mock-local", selection
    if route.alias == "nvidia":
        from src.providers.vision.nvidia_product_analysis import NVIDIAVisionProductAnalysisProvider

        return NVIDIAVisionProductAnalysisProvider(settings), route, "ready", selection
    if route.alias == "zhipu":
        from src.providers.vision.zhipu_vision import ZhipuVisionProvider

        return ZhipuVisionProvider(settings), route, "ready", selection
    if route.alias == "dashscope":
        return DashScopeVisionProvider(settings), route, "ready", selection
    raise RuntimeError(f"Unsupported vision provider alias: {route.alias}")


def _build_image_provider(
    settings: Settings,
) -> tuple[BaseImageProvider, ResolvedProviderRoute, str, ResolvedModelSelection]:
    route = settings.resolve_image_provider_route()
    selection = settings.resolve_image_model_selection()
    if route.mode != "real" or route.alias == "mock":
        return GeminiImageProvider(), route, "mock-local", selection
    if route.alias == "dashscope":
        return _build_dashscope_image_provider(settings, route, selection)
    if route.alias == "runapi":
        return RunApiGeminiImageProvider(settings), route, "ready", selection
    if route.alias == "zhipu":
        logger.warning("Image provider is routed but not wired yet: alias=%s", route.alias)
        return _UnsupportedImageProvider(route.alias), route, "planned-not-wired", selection
    raise RuntimeError(f"Unsupported image provider alias: {route.alias}")


def _build_dashscope_image_provider(
    settings: Settings,
    route: ResolvedProviderRoute,
    selection: ResolvedModelSelection,
) -> tuple[BaseImageProvider, ResolvedProviderRoute, str, ResolvedModelSelection]:
    """构建 DashScope 图片链路，并按需接通 image_edit 分支。"""
    edit_route = settings.resolve_image_edit_provider_route()
    edit_selection = settings.resolve_image_edit_model_selection()
    edit_provider: BaseImageProvider | None = None
    edit_status = "disabled"
    if settings.image_edit_enabled:
        if edit_route.alias == "dashscope":
            edit_provider = DashScopeImageEditProvider(settings)
            edit_status = "ready"
        elif edit_route.alias == "runapi":
            edit_provider = RunApiGeminiImageProvider(settings)
            edit_status = "ready"
        else:
            edit_status = "planned-not-wired"
            logger.warning("Image edit provider is not wired: alias=%s", edit_route.alias)
    logger.info(
        "Configured image generation routing: t2i_provider=%s, t2i_model=%s, image_edit_enabled=%s, image_edit_provider=%s, image_edit_model=%s, image_edit_status=%s",
        route.alias,
        selection.model_id,
        settings.image_edit_enabled,
        edit_route.alias,
        edit_selection.model_id,
        edit_status,
    )
    return (
        RoutedImageProvider(
            settings=settings,
            t2i_provider=DashScopeImageProvider(settings),
            t2i_route=route,
            t2i_model_selection=selection,
            image_edit_provider=edit_provider,
            image_edit_route=edit_route,
            image_edit_model_selection=edit_selection,
        ),
        route,
        "ready",
        selection,
    )


class _UnsupportedTextProvider(BaseTextProvider):
    def __init__(self, alias: str) -> None:
        self.alias = alias

    def generate_structured(self, prompt: str, response_model, *, system_prompt: str | None = None):
        raise RuntimeError(f"Text provider `{self.alias}` is routed but not implemented.")


class _UnsupportedVisionProvider(BaseVisionAnalysisProvider):
    def __init__(self, alias: str) -> None:
        self.alias = alias

    def generate_structured_from_assets(self, prompt: str, response_model, *, assets, system_prompt: str | None = None):
        raise RuntimeError(f"Vision provider `{self.alias}` is routed but not implemented.")


class _UnsupportedImageProvider(BaseImageProvider):
    def __init__(self, alias: str) -> None:
        self.alias = alias

    def generate_images(self, plan, *, output_dir, reference_assets=None):
        raise RuntimeError(f"Image provider `{self.alias}` is routed but not implemented.")
