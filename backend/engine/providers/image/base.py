from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from backend.engine.domain.asset import Asset
from backend.engine.domain.generation_result import GenerationResult
from backend.engine.domain.image_prompt_plan import ImagePromptPlan
from backend.engine.domain.usage import ProviderUsageSnapshot


class BaseImageProvider(ABC):
    """图片 provider 最小能力接口。"""

    last_usage: ProviderUsageSnapshot | None = None

    def get_last_usage(self) -> ProviderUsageSnapshot | None:
        """返回最近一次图片调用的 usage 快照。"""

        if self.last_usage is None:
            return None
        return self.last_usage.model_copy()

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
