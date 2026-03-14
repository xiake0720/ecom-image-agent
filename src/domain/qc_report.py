from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class QCCheck(BaseModel):
    shot_id: str
    check_name: str
    passed: bool
    status: Literal["passed", "warning", "failed"] | None = None
    details: str

    @model_validator(mode="after")
    def _normalize_status(self) -> "QCCheck":
        if self.status is None:
            self.status = "passed" if self.passed else "failed"
        self.passed = self.status != "failed"
        return self


class QCReport(BaseModel):
    passed: bool
    review_required: bool = False
    checks: list[QCCheck] = Field(default_factory=list)
