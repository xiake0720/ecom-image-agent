from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LayoutBlock(BaseModel):
    kind: Literal["title", "subtitle", "bullets", "cta"]
    x: int
    y: int
    width: int
    height: int
    font_size: int = 64
    align: Literal["left", "center"] = "left"


class LayoutItem(BaseModel):
    shot_id: str
    canvas_width: int
    canvas_height: int
    blocks: list[LayoutBlock] = Field(default_factory=list)


class LayoutPlan(BaseModel):
    items: list[LayoutItem] = Field(default_factory=list)

