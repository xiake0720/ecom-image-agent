from __future__ import annotations

from pydantic import BaseModel, Field


class ProductAnalysis(BaseModel):
    category: str
    product_type: str
    selling_points: list[str] = Field(default_factory=list)
    visual_style_keywords: list[str] = Field(default_factory=list)
    recommended_focuses: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)

