from __future__ import annotations

from pydantic import BaseModel, Field


class CopyItem(BaseModel):
    shot_id: str
    title: str
    subtitle: str
    bullets: list[str] = Field(default_factory=list)
    cta: str | None = None


class CopyPlan(BaseModel):
    items: list[CopyItem] = Field(default_factory=list)

