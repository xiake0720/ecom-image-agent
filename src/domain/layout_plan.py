from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TextSafeZone = Literal[
    "top_left",
    "top_right",
    "right_center",
    "left_center",
    "bottom_left",
    "bottom_right",
]


class LayoutBlock(BaseModel):
    kind: Literal["title", "subtitle", "bullets", "cta"]
    x: int
    y: int
    width: int
    height: int
    font_size: int = 64
    align: Literal["left", "center"] = "left"


class SafeZoneScore(BaseModel):
    zone: TextSafeZone
    total_score: float
    distance_from_subject_score: float = 0.0
    background_uniformity_score: float = 0.0
    text_readability_score: float = 0.0
    label_overlap_penalty: float = 0.0
    composition_bias_score: float = 0.0
    rejection_reason: str = ""


class LayoutItem(BaseModel):
    shot_id: str
    canvas_width: int
    canvas_height: int
    text_safe_zone: TextSafeZone = "top_right"
    safe_zone_score_breakdown: list[SafeZoneScore] = Field(default_factory=list)
    rejected_zones: list[str] = Field(default_factory=list)
    selection_reason: str = ""
    blocks: list[LayoutBlock] = Field(default_factory=list)


class LayoutPlan(BaseModel):
    items: list[LayoutItem] = Field(default_factory=list)
