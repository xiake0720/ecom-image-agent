from __future__ import annotations

from pydantic import BaseModel, Field


class QCCheck(BaseModel):
    shot_id: str
    check_name: str
    passed: bool
    details: str


class QCReport(BaseModel):
    passed: bool
    review_required: bool = False
    checks: list[QCCheck] = Field(default_factory=list)

