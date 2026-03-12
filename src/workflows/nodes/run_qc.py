"""基础质检节点。

该节点负责：
- 检查输出尺寸
- 调用 OCR 占位服务做基础文本校验
- 汇总为 `qc_report.json`

当前阶段重点是保证链路可检查，而不是生产级视觉质检。
"""

from __future__ import annotations

import logging

from src.domain.qc_report import QCReport
from src.services.qc.image_qc import build_dimension_check
from src.services.qc.ocr_qc import build_ocr_check
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def run_qc(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """执行基础质检并落盘 `qc_report.json`。"""
    logs = [*state.get("logs", []), f"[run_qc] 开始执行基础质检，图片数={len(state['generation_result'].images)}。"]
    checks = []
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    for image in state["generation_result"].images:
        checks.append(build_dimension_check(image))
        checks.append(build_ocr_check(deps.ocr_service, image.image_path, copy_map[image.shot_id]))
    passed = all(check.passed for check in checks)
    report = QCReport(passed=passed, review_required=not passed, checks=checks)
    deps.storage.save_json_artifact(state["task"].task_id, "qc_report.json", report)
    failed_checks = [check.check_name for check in checks if not check.passed]
    logger.info(
        "基础质检完成，passed=%s，review_required=%s，检查项数量=%s，失败项=%s",
        report.passed,
        report.review_required,
        len(report.checks),
        failed_checks,
    )
    logs.extend(
        [
            (
                "[run_qc] 基础质检完成，"
                f"passed={report.passed}, review_required={report.review_required}, "
                f"checks={len(report.checks)}, failed={failed_checks}。"
            ),
            "[run_qc] 已写入 qc_report.json。",
        ]
    )
    return {"qc_report": report, "logs": logs}
