"""Mock Banana2 图片 provider。"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from backend.engine.domain.asset import Asset
from backend.engine.domain.generation_result import GeneratedImage, GenerationResult
from backend.engine.domain.image_prompt_plan import ImagePromptPlan
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2
from backend.engine.providers.image.base import BaseImageProvider

MOCK_IMAGE_ROOT = Path("assets/mock/banana2")


class MockBanana2ImageProvider(BaseImageProvider):
    """返回固定样张文件的 mock provider。

    这里不在运行时本地拼图，只把预置的 mock 样张复制到任务输出目录，
    以验证 detail graph 的真实落盘、轮询与下载链路。
    """

    provider_alias = "mock_banana2"
    model_id = "mock-banana2"

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """兼容旧版 prompt 计划，逐张复制固定样张。"""

        del reference_assets, background_style_assets
        output_dir.mkdir(parents=True, exist_ok=True)
        images: list[GeneratedImage] = []
        for index, prompt in enumerate(plan.prompts, start=1):
            sample = self._resolve_sample_path(index=index)
            output_path = output_dir / f"{index:02d}_{prompt.shot_id}.png"
            width, height = self._copy_sample(sample, output_path)
            images.append(
                GeneratedImage(
                    shot_id=prompt.shot_id,
                    image_path=str(output_path),
                    preview_path=str(output_path),
                    width=width,
                    height=height,
                )
            )
        return GenerationResult(images=images)

    def generate_images_v2(
        self,
        prompt_plan: PromptPlanV2,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """兼容 v2 prompt 计划，逐张复制固定样张。"""

        del reference_assets, background_style_assets
        output_dir.mkdir(parents=True, exist_ok=True)
        images: list[GeneratedImage] = []
        for index, shot in enumerate(prompt_plan.shots, start=1):
            sample = self._resolve_sample_path(index=index)
            output_path = output_dir / f"{index:02d}_{shot.shot_id}.png"
            width, height = self._copy_sample(sample, output_path)
            images.append(
                GeneratedImage(
                    shot_id=shot.shot_id,
                    image_path=str(output_path),
                    preview_path=str(output_path),
                    width=width,
                    height=height,
                )
            )
        return GenerationResult(images=images)

    def resolve_generation_context(
        self,
        *,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> object:
        """提供与真实 provider 相同的最小上下文。"""

        del reference_assets, background_style_assets
        return type(
            "MockGenerationContext",
            (),
            {
                "generation_mode": "mock_file_copy",
                "provider_alias": self.provider_alias,
                "model_id": self.model_id,
                "reference_asset_ids": [],
                "background_style_asset_ids": [],
            },
        )()

    def _resolve_sample_path(self, *, index: int) -> Path:
        sample_dir = MOCK_IMAGE_ROOT
        candidates = sorted(sample_dir.glob("*.png"))
        if not candidates:
            raise RuntimeError(f"Mock Banana2 assets are missing under: {sample_dir}")
        return candidates[(index - 1) % len(candidates)]

    def _copy_sample(self, sample: Path, output_path: Path) -> tuple[int, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sample, output_path)
        with Image.open(output_path) as image:
            width, height = image.size
        return width, height


class GeminiImageProvider(MockBanana2ImageProvider):
    """兼容旧类名，避免仓库内历史引用失效。"""
