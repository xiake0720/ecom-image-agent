"""图片 provider 抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.domain.asset import Asset
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan


class BaseImageProvider(ABC):
    """图片 provider 最小能力接口。"""

    @abstractmethod
    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
        background_style_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """按兼容层 prompt plan 生成图片并写入输出目录。"""
