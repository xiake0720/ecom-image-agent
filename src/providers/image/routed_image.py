"""图片生成模式路由适配层。

文件位置：
- `src/providers/image/routed_image.py`

核心职责：
- 在同一个图片 provider 外观下，自动分流 `t2i` 和 `image_edit`
- 记录本次真实使用的 generation mode、model_id、参考图 ID

主要调用方：
- `src/providers/router.py` 会实例化本类
- `render_images` 会通过统一接口调用本类

关键输入/输出：
- 输入：`ImagePromptPlan`、输出目录、参考图列表
- 输出：`GenerationResult`
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from src.core.config import ResolvedModelSelection, ResolvedProviderRoute, Settings
from src.domain.asset import Asset
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.providers.image.base import BaseImageProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageGenerationContext:
    """一次图片生成最终采用的真实上下文。"""

    generation_mode: str
    provider_alias: str
    model_id: str
    reference_asset_ids: list[str]
    selected_reference_assets: list[Asset]


class RoutedImageProvider(BaseImageProvider):
    """统一图片生成入口。

    为什么需要这个类：
    - workflow 只想调用一个 `generate_images()`
    - 但实际图片生成存在 `t2i` 和 `image_edit` 两条链路
    - 这里负责把参考图、配置和 provider 能力综合判断成最终执行路径
    """

    def __init__(
        self,
        *,
        settings: Settings,
        t2i_provider: BaseImageProvider,
        t2i_route: ResolvedProviderRoute,
        t2i_model_selection: ResolvedModelSelection,
        image_edit_provider: BaseImageProvider | None = None,
        image_edit_route: ResolvedProviderRoute | None = None,
        image_edit_model_selection: ResolvedModelSelection | None = None,
    ) -> None:
        self.settings = settings
        self.t2i_provider = t2i_provider
        self.t2i_route = t2i_route
        self.t2i_model_selection = t2i_model_selection
        self.image_edit_provider = image_edit_provider
        self.image_edit_route = image_edit_route
        self.image_edit_model_selection = image_edit_model_selection
        self.last_generation_context = ImageGenerationContext(
            generation_mode="t2i",
            provider_alias=t2i_route.alias,
            model_id=t2i_model_selection.model_id,
            reference_asset_ids=[],
            selected_reference_assets=[],
        )

    def resolve_generation_context(self, *, reference_assets: list[Asset] | None = None) -> ImageGenerationContext:
        """解析当前应走哪条图片生成链路。"""
        prepared_assets = self._prepare_reference_assets(reference_assets)
        if prepared_assets and self.settings.image_edit_enabled and self.image_edit_provider is not None:
            route = self.image_edit_route or self.t2i_route
            selection = self.image_edit_model_selection or self.t2i_model_selection
            return ImageGenerationContext(
                generation_mode="image_edit",
                provider_alias=route.alias,
                model_id=selection.model_id,
                reference_asset_ids=[asset.asset_id for asset in prepared_assets],
                selected_reference_assets=prepared_assets,
            )
        return ImageGenerationContext(
            generation_mode="t2i",
            provider_alias=self.t2i_route.alias,
            model_id=self.t2i_model_selection.model_id,
            reference_asset_ids=[],
            selected_reference_assets=[],
        )

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """根据参考图和配置分流到真实 provider。"""
        context = self.resolve_generation_context(reference_assets=reference_assets)
        self.last_generation_context = context
        provider = self.image_edit_provider if context.generation_mode == "image_edit" else self.t2i_provider
        logger.info(
            "Image generation route selected: mode=%s, provider=%s, model_id=%s, reference_asset_ids=%s, output_dir=%s",
            context.generation_mode,
            context.provider_alias,
            context.model_id,
            context.reference_asset_ids,
            output_dir,
        )
        if reference_assets and context.generation_mode != "image_edit":
            logger.info(
                "Reference assets were provided but image edit was not used: enabled=%s, edit_provider_ready=%s",
                self.settings.image_edit_enabled,
                self.image_edit_provider is not None,
            )
        adapted_plan = self._adapt_plan_for_generation_mode(plan, context.generation_mode)
        return provider.generate_images(
            adapted_plan,
            output_dir=output_dir,
            reference_assets=context.selected_reference_assets,
        )

    def _prepare_reference_assets(self, reference_assets: list[Asset] | None) -> list[Asset]:
        """按配置裁剪参考图数量，并过滤掉没有本地路径的资产。"""
        if not reference_assets:
            return []
        max_images = self.settings.resolve_image_edit_max_reference_images()
        if not self.settings.image_edit_prefer_multi_image:
            max_images = 1
        prepared: list[Asset] = []
        for asset in reference_assets:
            if not asset.local_path:
                continue
            prepared.append(asset)
            if len(prepared) >= max_images:
                break
        return prepared

    def _adapt_plan_for_generation_mode(self, plan: ImagePromptPlan, generation_mode: str) -> ImagePromptPlan:
        """让 `ImagePromptPlan` 和真实 generation mode 保持一致。

        关键点：
        - image_edit 时优先使用 `edit_instruction`
        - t2i 时继续使用 `prompt`
        """
        adapted_prompts: list[ImagePrompt] = []
        for prompt in plan.prompts:
            effective_prompt = prompt.prompt
            if generation_mode == "image_edit" and prompt.edit_instruction:
                effective_prompt = prompt.edit_instruction
            adapted_prompts.append(
                prompt.model_copy(
                    update={
                        "generation_mode": generation_mode,
                        "prompt": effective_prompt,
                    }
                )
            )
        return plan.model_copy(
            update={
                "generation_mode": generation_mode,
                "prompts": adapted_prompts,
            }
        )
