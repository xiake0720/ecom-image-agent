from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from backend.engine.domain.usage import ProviderUsageSnapshot

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class BaseTextProvider(ABC):
    """文本 provider 最小能力接口。"""

    last_usage: ProviderUsageSnapshot | None = None

    def get_last_usage(self) -> ProviderUsageSnapshot | None:
        """返回最近一次调用的 usage 快照。"""

        if self.last_usage is None:
            return None
        return self.last_usage.model_copy()

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModel],
        *,
        system_prompt: str | None = None,
    ) -> StructuredModel:
        """Return structured data that conforms to the requested Pydantic schema."""

