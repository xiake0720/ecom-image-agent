"""QC 报告 contract。

文件位置：
- `src/domain/qc_report.py`

核心职责：
- 定义 `run_qc` 节点输出的数据结构。
- 统一表达 `passed / warning / failed` 三态检查项。
- 为结果页、导出链路和人工复核提供结构化调试信息。

关键输入/输出：
- 输入来自各类 QC 检查函数。
- 输出落盘为 `qc_report.json` 或 `qc_report_preview.json`。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class QCCheck(BaseModel):
    """单项 QC 检查结果。"""

    shot_id: str
    check_name: str
    passed: bool
    status: Literal["passed", "warning", "failed"] | None = None
    details: str
    related_shot_id: str = ""
    evidence_completeness: Literal["full", "partial", "missing"] | None = None

    @model_validator(mode="after")
    def _normalize_status(self) -> "QCCheck":
        """兼容旧代码继续只传 `passed` 的情况，并补齐 `related_shot_id`。"""
        if self.status is None:
            self.status = "passed" if self.passed else "failed"
        self.passed = self.status != "failed"
        if not self.related_shot_id:
            self.related_shot_id = self.shot_id
        return self


class QCCheckSummary(BaseModel):
    """按检查类型归并后的轻量摘要。"""

    status: Literal["passed", "warning", "failed"]
    details: str
    related_shot_id: str = ""
    evidence_completeness: Literal["full", "partial", "missing"] | None = None


class QCReport(BaseModel):
    """整组任务的 QC 汇总结 果。

    兼容说明：
    - `checks` 保留原有明细列表，便于现有调用继续工作。
    - 新增三类根级别字段，便于 UI、导出和人工快速定位图像层核心风险。
    """

    passed: bool
    review_required: bool = False
    checks: list[QCCheck] = Field(default_factory=list)
    shot_completeness_check: list[QCCheckSummary] = Field(default_factory=list)
    product_consistency_check: list[QCCheckSummary] = Field(default_factory=list)
    shot_type_match_check: list[QCCheckSummary] = Field(default_factory=list)
<<<<<<< HEAD
=======
    visual_shot_diversity_check: list[QCCheckSummary] = Field(default_factory=list)
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    text_safe_zone_check: list[QCCheckSummary] = Field(default_factory=list)
    text_readability_check: list[QCCheckSummary] = Field(default_factory=list)
