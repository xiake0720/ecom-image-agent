from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from src.domain.asset import Asset

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class BaseVisionAnalysisProvider(ABC):
    @abstractmethod
    def generate_structured_from_assets(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        assets: list[Asset],
        system_prompt: str | None = None,
    ) -> StructuredModel:
        """根据商品图片返回结构化视觉分析结果。"""
