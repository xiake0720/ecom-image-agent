from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PackagingStructure(BaseModel):
    primary_container: str
    has_outer_box: str
    has_visible_lid: str
    container_count: str


class VisualIdentity(BaseModel):
    dominant_colors: list[str] = Field(default_factory=list)
    label_position: str
    label_ratio: str
    style_impression: list[str] = Field(default_factory=list)
    must_preserve: list[str] = Field(default_factory=list)


class MaterialGuess(BaseModel):
    container_material: str
    label_material: str


class VisualConstraints(BaseModel):
    recommended_style_direction: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class ProductAnalysis(BaseModel):
    analysis_scope: Literal["sku_level"] = "sku_level"
    intended_for: Literal["all_future_shots"] = "all_future_shots"
    category: str
    subcategory: str
    product_type: str
    product_form: str
    packaging_structure: PackagingStructure
    visual_identity: VisualIdentity
    material_guess: MaterialGuess
    visual_constraints: VisualConstraints
    selling_points: list[str] = Field(default_factory=list)
    visual_style_keywords: list[str] = Field(default_factory=list)
    recommended_focuses: list[str] = Field(default_factory=list)
    source_asset_ids: list[str] = Field(default_factory=list)

