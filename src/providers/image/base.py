from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.domain.asset import Asset
from src.domain.generation_result import GenerationResult
from src.domain.image_prompt_plan import ImagePromptPlan


class BaseImageProvider(ABC):
    @abstractmethod
    def generate_images(
        self,
        plan: ImagePromptPlan,
        *,
        output_dir: Path,
        reference_assets: list[Asset] | None = None,
    ) -> GenerationResult:
        """Generate images for the given prompt plan and save them to output_dir."""
