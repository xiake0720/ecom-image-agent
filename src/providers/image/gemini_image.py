from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from src.domain.asset import Asset
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan
from src.providers.image.base import BaseImageProvider

logger = logging.getLogger(__name__)


class GeminiImageProvider(BaseImageProvider):
    def __init__(self) -> None:
        pass

    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        logger.info(
            "当前图片 provider 模式为 mock，开始生成占位图，数量=%s，输出目录=%s",
            len(plan.prompts),
            output_dir,
        )
        # TODO: Replace this mock canvas renderer with a real image model provider after MVP approval.
        output_dir.mkdir(parents=True, exist_ok=True)
        images: list[GeneratedImage] = []
        for index, prompt in enumerate(plan.prompts, start=1):
            width, height = [int(value) for value in prompt.output_size.split("x", maxsplit=1)]
            output_path = output_dir / f"{index:02d}_{prompt.shot_id}.png"
            self._render_placeholder(width, height, prompt.prompt, output_path)
            images.append(
                GeneratedImage(
                    shot_id=prompt.shot_id,
                    image_path=str(output_path),
                    preview_path=str(output_path),
                    width=width,
                    height=height,
                )
            )
        logger.info("mock 图片生成完成，输出文件数=%s", len(images))
        return GenerationResult(images=images)

    def _render_placeholder(self, width: int, height: int, prompt: str, output_path: Path) -> None:
        image = Image.new("RGB", (width, height), color=(236, 244, 232))
        draw = ImageDraw.Draw(image)
        accent_width = max(80, width // 8)
        draw.rectangle((width - accent_width, 0, width, height), fill=(32, 80, 58))
        draw.ellipse((width // 2, height // 5, width - 120, height - 220), fill=(199, 219, 181))
        draw.rounded_rectangle((80, height - 320, width - 80, height - 120), radius=40, fill=(255, 255, 255))
        draw.text((120, height - 285), prompt[:96], fill=(30, 48, 34))
        image.save(output_path)
