from __future__ import annotations

from pydantic import BaseModel, Field


class ShotSpec(BaseModel):
    shot_id: str
    title: str
    purpose: str
    composition_hint: str
    copy_goal: str


class ShotPlan(BaseModel):
    shots: list[ShotSpec] = Field(default_factory=list)

