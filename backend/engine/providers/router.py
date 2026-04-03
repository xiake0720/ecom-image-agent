"""Provider 总路由入口。

文件位置：
- `src/providers/router.py`

职责：
- 只保留新主链需要的文本与图片 provider 绑定
- 默认固定到 RunAPI 文本与 Gemini 3.1 图片模型
- 在 mock 模式下回退到本地占位 provider
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from backend.engine.core.config import ResolvedModelSelection, ResolvedProviderRoute, Settings
from backend.engine.providers.image.banana2_image import Banana2ImageProvider
from backend.engine.providers.image.base import BaseImageProvider
from backend.engine.providers.image.gemini_image import GeminiImageProvider
from backend.engine.providers.image.gemini_image import MockBanana2ImageProvider
from backend.engine.providers.image.runapi_gemini31_image import RunApiGemini31ImageProvider
from backend.engine.providers.llm.base import BaseTextProvider
from backend.engine.providers.llm.gemini_text import GeminiTextProvider
from backend.engine.providers.llm.runapi_openai_text import RunApiOpenAITextProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapabilityBindings:
    """workflow 运行时会消费的 provider 绑定结果。"""

    planning_provider: BaseTextProvider
    image_generation_provider: BaseImageProvider
    planning_provider_name: str
    image_provider_name: str
    planning_route: ResolvedProviderRoute
    image_route: ResolvedProviderRoute
    planning_provider_status: str
    image_provider_status: str
    planning_model_selection: ResolvedModelSelection
    image_model_selection: ResolvedModelSelection


def build_capability_bindings(settings: Settings) -> CapabilityBindings:
    """按配置构建文本与图片能力绑定。"""

    planning_provider, planning_route, planning_status, planning_selection = _build_planning_provider(settings)
    image_provider, image_route, image_status, image_selection = _build_image_provider(settings)
    logger.info(
        "Resolved providers: planning=%s[%s](%s), image=%s[%s](%s)",
        type(planning_provider).__name__,
        planning_route.alias,
        planning_selection.model_id,
        type(image_provider).__name__,
        image_route.alias,
        image_selection.model_id,
    )
    return CapabilityBindings(
        planning_provider=planning_provider,
        image_generation_provider=image_provider,
        planning_provider_name=type(planning_provider).__name__,
        image_provider_name=type(image_provider).__name__,
        planning_route=planning_route,
        image_route=image_route,
        planning_provider_status=planning_status,
        image_provider_status=image_status,
        planning_model_selection=planning_selection,
        image_model_selection=image_selection,
    )


def _build_planning_provider(
    settings: Settings,
) -> tuple[BaseTextProvider, ResolvedProviderRoute, str, ResolvedModelSelection]:
    route = settings.resolve_text_provider_route()
    selection = settings.resolve_text_model_selection()
    if route.mode != "real" or route.alias == "mock":
        return GeminiTextProvider(), route, "mock-local", selection
    if route.alias == "runapi_openai":
        return RunApiOpenAITextProvider(settings), route, "ready", selection
    raise RuntimeError(f"Unsupported text provider alias: {route.alias}")


def _build_image_provider(
    settings: Settings,
) -> tuple[BaseImageProvider, ResolvedProviderRoute, str, ResolvedModelSelection]:
    route = settings.resolve_image_provider_route()
    selection = settings.resolve_image_model_selection()
    if route.mode != "real" or route.alias == "mock":
        return MockBanana2ImageProvider(), route, "mock-local", selection
    if route.alias == "banana2":
        return Banana2ImageProvider(settings), route, "ready", selection
    if route.alias == "runapi_gemini31":
        return RunApiGemini31ImageProvider(settings), route, "ready", selection
    raise RuntimeError(f"Unsupported image provider alias: {route.alias}")
