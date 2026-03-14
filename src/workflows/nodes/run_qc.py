"""基础质检节点。"""

from __future__ import annotations

from pathlib import Path

from src.core.paths import get_task_dir
from src.domain.qc_report import QCReport
from src.services.qc.image_qc import build_dimension_check
from src.services.qc.ocr_qc import build_ocr_check
from src.services.qc.task_qc import (
    build_dir_exists_check,
    build_file_exists_check,
    build_product_consistency_risk_check,
    build_safe_zone_overlap_risk_check,
    build_task_output_dimension_check,
    build_text_area_complexity_check,
    build_text_background_contrast_check,
    build_text_overflow_risk_check,
)
from src.workflows.state import WorkflowDependencies, WorkflowState


def run_qc(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """执行基础质检并落盘报告。"""
    render_variant = str(state.get("render_variant") or "final")
    task = state["task"]
    task_dir = get_task_dir(task.task_id)
    logs = [*state.get("logs", []), f"[run_qc] 开始执行基础质检，render_variant={render_variant}，图片数={len(state['generation_result'].images)}。"]
    checks = []
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    shot_map = {item.shot_id: item for item in state["shot_plan"].shots}
    prompt_map = {item.shot_id: item for item in state["image_prompt_plan"].prompts}

    checks.extend(_build_task_structure_checks(task_dir=task_dir, render_variant=render_variant))
    for image in state["generation_result"].images:
        checks.append(build_dimension_check(image))
        if render_variant == "final":
            checks.append(build_task_output_dimension_check(image, expected_size=task.output_size))
        copy_item = copy_map[image.shot_id]
        layout_item = layout_map[image.shot_id]
        prompt_item = prompt_map[image.shot_id]
        expected_generation_mode = str(getattr(prompt_item, "generation_mode", "") or state["image_prompt_plan"].generation_mode or "t2i")
        actual_generation_mode = str(state.get("render_generation_mode") or "t2i")
        checks.append(build_text_overflow_risk_check(copy_item, layout_item))
        checks.append(build_text_background_contrast_check(image, layout_item))
        checks.append(build_text_area_complexity_check(image, layout_item))
        checks.append(build_safe_zone_overlap_risk_check(layout_item, shot_map.get(image.shot_id)))
        checks.append(
            build_product_consistency_risk_check(
                shot_id=image.shot_id,
                expected_generation_mode=expected_generation_mode,
                actual_generation_mode=actual_generation_mode,
                reference_asset_ids=list(state.get("render_reference_asset_ids", [])),
                prompt_generation_mode=str(getattr(prompt_item, "generation_mode", "") or state["image_prompt_plan"].generation_mode or "t2i"),
            )
        )
        checks.append(build_ocr_check(deps.ocr_service, image.image_path, copy_item))

    filename = "qc_report_preview.json" if render_variant == "preview" else "qc_report.json"
    report = _build_qc_report(checks)
    deps.storage.save_json_artifact(task.task_id, filename, report)

    # 保存后再做一次报告文件存在性检查，确保最终报告里包含自身产物检查。
    final_checks = [*checks, build_file_exists_check(shot_id="task", path=task_dir / filename, check_name=filename.replace(".json", "_exists"))]
    report = _build_qc_report(final_checks)
    deps.storage.save_json_artifact(task.task_id, filename, report)

    updates = {
        "qc_report": report,
        "logs": [
            *logs,
            f"[run_qc] 基础质检完成，render_variant={render_variant}，passed={report.passed}，checks={len(report.checks)}。",
            f"[run_qc] 已写入 {filename}。",
        ],
    }
    if render_variant == "preview":
        updates["preview_qc_report"] = report
    return updates


def _build_task_structure_checks(*, task_dir: Path, render_variant: str) -> list:
    checks = [
        build_file_exists_check(shot_id="task", path=task_dir / "task.json", check_name="task_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "product_analysis.json", check_name="product_analysis_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "shot_plan.json", check_name="shot_plan_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "copy_plan.json", check_name="copy_plan_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "layout_plan.json", check_name="layout_plan_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "image_prompt_plan.json", check_name="image_prompt_plan_json_exists"),
    ]
    if render_variant == "preview":
        checks.extend(
            [
                build_dir_exists_check(shot_id="task", path=task_dir / "generated_preview", check_name="generated_preview_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "final_preview", check_name="final_preview_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "previews", check_name="previews_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "exports", check_name="exports_dir_exists"),
            ]
        )
    else:
        checks.extend(
            [
                build_dir_exists_check(shot_id="task", path=task_dir / "generated", check_name="generated_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "final", check_name="final_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "previews", check_name="previews_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "exports", check_name="exports_dir_exists"),
            ]
        )
    return checks


def _build_qc_report(checks: list) -> QCReport:
    has_failed = any(getattr(check, "status", None) == "failed" for check in checks)
    review_required = any(getattr(check, "status", None) in {"warning", "failed"} for check in checks)
    return QCReport(
        passed=not has_failed,
        review_required=review_required,
        checks=checks,
    )
