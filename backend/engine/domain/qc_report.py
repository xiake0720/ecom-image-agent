"""质检报告 contract。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class QCCheck(BaseModel):
    """单项 QC 结果。"""

    shot_id: str
    check_name: str
    passed: bool
    status: Literal["passed", "warning", "failed"] | None = None
    details: str
    related_shot_id: str = ""

    @model_validator(mode="after")
    def _normalize(self) -> "QCCheck":
        """补齐 status 与 related_shot_id。"""

        if self.status is None:
            self.status = "passed" if self.passed else "failed"
        self.passed = self.status != "failed"
        if not self.related_shot_id:
            self.related_shot_id = self.shot_id
        return self


class QCCheckSummary(BaseModel):
    """按检查类型聚合后的摘要。"""

    status: Literal["passed", "warning", "failed"]
    details: str
    related_shot_id: str = ""


class QCReport(BaseModel):
    """任务级 QC 汇总结果。"""

    passed: bool
    review_required: bool = False
    checks: list[QCCheck] = Field(default_factory=list)
    shot_completeness_check: list[QCCheckSummary] = Field(default_factory=list)
    render_output_check: list[QCCheckSummary] = Field(default_factory=list)
    overlay_fallback_check: list[QCCheckSummary] = Field(default_factory=list)
