"""v2 质检节点。

文件位置：
- `src/workflows/nodes/run_qc.py`

职责：
- 只保留新主链需要的最小闭环 QC
- 检查图数、文件存在性、最终输出可读性与 overlay fallback 使用情况
- 落盘 `qc_report.json`
"""

from __future__ import annotations

from pathlib import Path

from backend.engine.core.paths import get_task_dir
from backend.engine.domain.qc_report import QCCheck, QCCheckSummary, QCReport
from backend.engine.workflows.state import WorkflowDependencies, WorkflowState


def run_qc(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """执行最小 v2 QC 并落盘。"""

    task = state["task"]
    prompt_plan = state.get("prompt_plan_v2")
    generation_result = state.get("generation_result_v2") or state.get("generation_result")
    if prompt_plan is None or generation_result is None:
        raise RuntimeError("run_qc requires prompt_plan_v2 and generation_result_v2")

    task_dir = Path(get_task_dir(task.task_id))
    expected_ids = [shot.shot_id for shot in prompt_plan.shots]
    actual_ids = [image.shot_id for image in generation_result.images]
    missing_ids = [shot_id for shot_id in expected_ids if shot_id not in actual_ids]
    checks: list[QCCheck] = [
        QCCheck(
            shot_id="task",
            check_name="shot_completeness_check",
            passed=not missing_ids and len(actual_ids) == len(expected_ids),
            status="failed" if missing_ids else "passed",
            details=f"expected={expected_ids}, actual={actual_ids}, missing={missing_ids}",
            related_shot_id="task",
        )
    ]

    overlay_fallback_used = False
    text_render_reports = state.get("text_render_reports", {})
    for image in generation_result.images:
        image_path = Path(image.image_path)
        exists = image_path.exists() and image_path.stat().st_size > 0
        checks.append(
            QCCheck(
                shot_id=image.shot_id,
                check_name="render_output_check",
                passed=exists,
                status="failed" if not exists else "passed",
                details=str(image_path),
                related_shot_id=image.shot_id,
            )
        )
        report = text_render_reports.get(image.shot_id) or {}
        if bool(report.get("overlay_applied")):
            overlay_fallback_used = True

    checks.append(
        QCCheck(
            shot_id="task",
            check_name="overlay_fallback_check",
            passed=True,
            status="warning" if overlay_fallback_used else "passed",
            details=f"overlay_fallback_used={overlay_fallback_used}",
            related_shot_id="task",
        )
    )

    report = _build_qc_report(checks)
    deps.storage.save_json_artifact(task.task_id, "qc_report.json", report)
    checks.append(
        QCCheck(
            shot_id="task",
            check_name="qc_report_exists",
            passed=(task_dir / "qc_report.json").exists(),
            details=str(task_dir / "qc_report.json"),
            related_shot_id="task",
        )
    )
    report = _build_qc_report(checks)
    deps.storage.save_json_artifact(task.task_id, "qc_report.json", report)
    return {
        "qc_report": report,
        "qc_report_v2": report,
        "logs": [
            *state.get("logs", []),
            f"[run_qc] completed passed={report.passed} review_required={report.review_required} checks={len(report.checks)}",
            "[run_qc] saved qc_report.json",
        ],
    }


def _build_qc_report(checks: list[QCCheck]) -> QCReport:
    """汇总 QC 报告。"""

    has_failed = any(check.status == "failed" for check in checks)
    review_required = any(check.status in {"warning", "failed"} for check in checks)
    return QCReport(
        passed=not has_failed,
        review_required=review_required,
        checks=checks,
        shot_completeness_check=_build_summary_items(checks, "shot_completeness_check"),
        render_output_check=_build_summary_items(checks, "render_output_check"),
        overlay_fallback_check=_build_summary_items(checks, "overlay_fallback_check"),
    )


def _build_summary_items(checks: list[QCCheck], check_name: str) -> list[QCCheckSummary]:
    """把 checks 投影成根级摘要。"""

    return [
        QCCheckSummary(
            status=check.status or ("passed" if check.passed else "failed"),
            details=check.details,
            related_shot_id=check.related_shot_id or check.shot_id,
        )
        for check in checks
        if check.check_name == check_name
    ]
