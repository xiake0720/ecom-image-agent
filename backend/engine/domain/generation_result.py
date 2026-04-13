from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.engine.domain.usage import ProviderUsageSnapshot


class GeneratedImage(BaseModel):
    shot_id: str
    image_path: str
    preview_path: str
    width: int
    height: int
    status: Literal["generated", "finalized"] = "generated"


class GenerationResult(BaseModel):
    images: list[GeneratedImage] = Field(default_factory=list)
    usage: ProviderUsageSnapshot = Field(default_factory=ProviderUsageSnapshot.empty)

