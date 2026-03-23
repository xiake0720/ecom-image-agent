"""质检节点。

文件位置：
- `src/workflows/nodes/run_qc.py`

核心职责：
<<<<<<< HEAD
- 对最终图片执行工程检查和最小业务可用性检查
- 保留 v1 QC 行为
- 为 v2 增加图内文案匹配、产品一致性和 overlay fallback 需求识别
=======
- 对最终图片执行工程检查和轻量商业可用性检查。
- 为茶叶 Phase 1 固定五图链路增加图像层合同检查。
- 输出 `qc_report.json` 或 `qc_report_preview.json`。

节点前后关系：
- 上游节点：`overlay_text`
- 下游节点：`finalize`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.paths import get_task_dir
from src.domain.qc_report import QCCheck, QCCheckSummary, QCReport
from src.services.qc.image_qc import build_dimension_check
from src.services.qc.ocr_qc import build_ocr_check
from src.services.qc.task_qc import (
    build_dir_exists_check,
    build_file_exists_check,
    build_product_consistency_check,
    build_safe_zone_overlap_risk_check,
    build_shot_completeness_check,
    build_shot_type_match_check,
    build_task_output_dimension_check,
    build_text_readability_check,
    build_text_safe_zone_check,
    build_text_area_complexity_check,
    build_text_background_contrast_check,
    build_text_overflow_risk_check,
<<<<<<< HEAD
=======
    build_visual_shot_diversity_check,
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
)
from src.workflows.state import WorkflowDependencies, WorkflowState


def run_qc(state: WorkflowState, deps: WorkflowDependencies) -> dict:
<<<<<<< HEAD
    """执行 QC 并落盘报告。"""
    workflow_version = _resolve_workflow_version(state)
    if workflow_version == "v2" and state.get("prompt_plan_v2") is not None:
        return _run_qc_v2(state, deps)
    return _run_qc_v1(state, deps)


def _run_qc_v1(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """保留现有 v1 QC 逻辑。"""
=======
    """执行 QC 并落盘报告。

    关键副作用：
    - 写出 `qc_report.json` 或 `qc_report_preview.json`。
    - 记录图像层合同检查日志，便于定位缺图、商品漂移和图位不匹配问题。
    """
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    render_variant = str(state.get("render_variant") or "final")
    task = state["task"]
    task_dir = get_task_dir(task.task_id)
    generation_result = state["generation_result"]
    logs = [
        *state.get("logs", []),
<<<<<<< HEAD
        f"[run_qc] start workflow_version=v1 render_variant={render_variant} image_count={len(generation_result.images)}",
=======
        f"[run_qc] start render_variant={render_variant} image_count={len(generation_result.images)}",
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    ]
    checks: list[QCCheck] = []

    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    shot_map = {item.shot_id: item for item in state["shot_plan"].shots}
    prompt_map = {item.shot_id: item for item in state["image_prompt_plan"].prompts}
    shot_prompt_spec_map = {
        item.shot_id: item
        for item in getattr(state.get("shot_prompt_specs"), "specs", [])
    }
    text_render_report_map = _resolve_text_render_reports(state=state, task_dir=task_dir, render_variant=render_variant)

<<<<<<< HEAD
    checks.extend(_build_task_structure_checks_v1(task_dir=task_dir, render_variant=render_variant))
=======
    checks.extend(_build_task_structure_checks(task_dir=task_dir, render_variant=render_variant))

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    shot_completeness_check = build_shot_completeness_check(
        render_variant=render_variant,
        generation_result=generation_result,
        shot_plan=state["shot_plan"],
        product_analysis=state.get("product_analysis"),
    )
    checks.append(shot_completeness_check)
    logs.append(f"[run_qc] shot_count_summary={shot_completeness_check.details}")
<<<<<<< HEAD
=======
    hero_reference_image_path = _resolve_hero_reference_image_path(
        generation_result=generation_result,
        shot_plan=state["shot_plan"],
    )
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c

    for image in generation_result.images:
        checks.append(build_dimension_check(image))
        if render_variant == "final":
            checks.append(build_task_output_dimension_check(image, expected_size=task.output_size))

        copy_item = copy_map[image.shot_id]
        layout_item = layout_map[image.shot_id]
        shot_item = shot_map.get(image.shot_id)
        prompt_item = prompt_map[image.shot_id]
        shot_prompt_spec = shot_prompt_spec_map.get(image.shot_id)
        expected_generation_mode = str(
            getattr(prompt_item, "generation_mode", "") or state["image_prompt_plan"].generation_mode or "t2i"
        )
        actual_generation_mode = str(state.get("render_generation_mode") or "t2i")

        checks.append(build_text_overflow_risk_check(copy_item, layout_item))
        checks.append(build_text_background_contrast_check(image, layout_item))
        checks.append(build_text_area_complexity_check(image, layout_item))
        checks.append(build_safe_zone_overlap_risk_check(layout_item, shot_item))
        checks.append(build_ocr_check(deps.ocr_service, image.image_path, copy_item))
        text_render_report = text_render_report_map.get(image.shot_id)

        text_safe_zone_check = build_text_safe_zone_check(
            shot_id=image.shot_id,
            layout_item=layout_item,
            shot=shot_item,
            text_render_report=text_render_report,
        )
        checks.append(text_safe_zone_check)
<<<<<<< HEAD
=======
        logs.append(
            f"[run_qc] text_safe_zone_summary shot_id={image.shot_id} status={text_safe_zone_check.status} details={text_safe_zone_check.details}"
        )

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        text_readability_check = build_text_readability_check(
            image=image,
            shot_id=image.shot_id,
            copy_item=copy_item,
            layout_item=layout_item,
            text_render_report=text_render_report,
        )
        checks.append(text_readability_check)
<<<<<<< HEAD
=======
        logs.append(
            f"[run_qc] text_readability_summary shot_id={image.shot_id} status={text_readability_check.status} details={text_readability_check.details}"
        )

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        product_consistency_check = build_product_consistency_check(
            image=image,
            product_analysis=state.get("product_analysis"),
            expected_generation_mode=expected_generation_mode,
            actual_generation_mode=actual_generation_mode,
            reference_asset_ids=list(state.get("render_reference_asset_ids", [])),
            prompt_generation_mode=str(
                getattr(prompt_item, "generation_mode", "") or state["image_prompt_plan"].generation_mode or "t2i"
            ),
            ocr_service=deps.ocr_service,
            render_variant=render_variant,
        )
        checks.append(product_consistency_check)
<<<<<<< HEAD
=======
        logs.append(
            f"[run_qc] product_consistency_summary shot_id={image.shot_id} "
            f"status={product_consistency_check.status} "
            f"evidence_completeness={product_consistency_check.evidence_completeness or '-'} "
            f"details={product_consistency_check.details}"
        )

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        shot_type_match_check = build_shot_type_match_check(
            image=image,
            shot=shot_item,
            shot_prompt_spec=shot_prompt_spec,
<<<<<<< HEAD
        )
        checks.append(shot_type_match_check)

    filename = "qc_report_preview.json" if render_variant == "preview" else "qc_report.json"
    report = _build_qc_report(checks)
    deps.storage.save_json_artifact(task.task_id, filename, report)
    final_checks = [
        *checks,
        build_file_exists_check(shot_id="task", path=task_dir / filename, check_name=filename.replace(".json", "_exists")),
    ]
    report = _build_qc_report(final_checks)
    deps.storage.save_json_artifact(task.task_id, filename, report)

    updates = {
        "qc_report": report,
        "logs": [
            *logs,
            f"[run_qc] completed workflow_version=v1 render_variant={render_variant} passed={report.passed} checks={len(report.checks)}",
            f"[run_qc] saved {filename}",
        ],
    }
    if render_variant == "preview":
        updates["preview_qc_report"] = report
    return updates


def _run_qc_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """执行 v2 最小 QC 闭环。

    这里刻意保持“轻实现”：
    - 不引入新的重型 AI 审查
    - 只围绕图位完整性、文字大致匹配、产品一致性和 fallback 需求判断
    - 先把数据流打通，再逐步增强策略
    """
    render_variant = str(state.get("render_variant") or "final")
    task = state["task"]
    task_dir = get_task_dir(task.task_id)
    generation_result = state.get("generation_result_v2") or state["generation_result"]
    prompt_shot_map = {shot.shot_id: shot for shot in state["prompt_plan_v2"].shots}
    text_render_report_map = _resolve_text_render_reports(state=state, task_dir=task_dir, render_variant=render_variant)
    logs = [
        *state.get("logs", []),
        f"[run_qc] start workflow_version=v2 render_variant={render_variant} image_count={len(generation_result.images)}",
    ]
    checks: list[QCCheck] = []
    checks.extend(_build_task_structure_checks_v2(task_dir=task_dir, render_variant=render_variant))
    checks.append(_build_v2_shot_completeness_check(prompt_shot_map=prompt_shot_map, generation_result=generation_result, render_variant=render_variant))

    merged_candidates = {
        str(item.get("shot_id")): dict(item)
        for item in state.get("overlay_fallback_candidates", []) or []
        if item.get("shot_id")
    }
    # 这里做“合并”而不是覆盖，原因是 render 阶段和 QC 阶段都可能发现
    # 需要 fallback 的图片；最终要把两边线索汇总起来。
    for image in generation_result.images:
        checks.append(build_dimension_check(image))
        prompt_shot = prompt_shot_map.get(image.shot_id)
        if prompt_shot is None:
            checks.append(
                QCCheck(
                    shot_id=image.shot_id,
                    check_name="text_readability_check",
                    passed=False,
                    status="failed",
                    details="prompt_plan_v2 entry missing",
                    related_shot_id=image.shot_id,
                )
            )
            continue

        overlay_applied = bool((text_render_report_map.get(image.shot_id) or {}).get("overlay_applied"))
        text_check, fallback_reason = _build_v2_text_check(
            image=image,
            prompt_shot=prompt_shot,
            ocr_service=deps.ocr_service,
            overlay_applied=overlay_applied,
        )
        checks.append(text_check)
        if fallback_reason:
            # QC 发现问题后，继续沿用和 render 阶段相同的数据结构，
            # 这样 overlay_text/finalize/result_view 不需要再区分来源。
            merged_candidates[image.shot_id] = {
                "shot_id": image.shot_id,
                "shot_role": prompt_shot.shot_role,
                "generated_image_path": image.image_path,
                "title_copy": prompt_shot.title_copy,
                "subtitle_copy": prompt_shot.subtitle_copy,
                "layout_hint": prompt_shot.layout_hint,
                "reason": fallback_reason,
                "fallback_stage": "run_qc",
            }

        product_consistency_check = build_product_consistency_check(
            image=image,
            product_analysis=state.get("product_analysis"),
            expected_generation_mode="t2i",
            actual_generation_mode=str(state.get("render_generation_mode") or "t2i"),
            reference_asset_ids=list(state.get("render_reference_asset_ids", [])),
            prompt_generation_mode="t2i",
            ocr_service=deps.ocr_service,
            render_variant=render_variant,
        )
        checks.append(product_consistency_check)
        logs.append(
            f"[run_qc] v2 shot_id={image.shot_id} text_status={text_check.status} product_status={product_consistency_check.status}"
        )

    filename = "qc_report_preview.json" if render_variant == "preview" else "qc_report.json"
    report = _build_qc_report(checks)
    deps.storage.save_json_artifact(task.task_id, filename, report)
=======
            hero_reference_image_path=hero_reference_image_path,
        )
        checks.append(shot_type_match_check)
        logs.append(
            f"[run_qc] shot_type_match_summary shot_id={image.shot_id} status={shot_type_match_check.status} details={shot_type_match_check.details}"
        )

    diversity_check = build_visual_shot_diversity_check(
        generation_result=generation_result,
        shot_plan=state["shot_plan"],
        product_analysis=state.get("product_analysis"),
    )
    checks.append(diversity_check)
    logs.append(
        f"[run_qc] visual_shot_diversity_summary status={diversity_check.status} details={diversity_check.details}"
    )

    filename = "qc_report_preview.json" if render_variant == "preview" else "qc_report.json"
    report = _build_qc_report(checks)
    deps.storage.save_json_artifact(task.task_id, filename, report)

    # 报告先写一次，再把“报告文件自己是否存在”纳入检查项，保证最终报告能覆盖自身产物完整性。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    final_checks = [
        *checks,
        build_file_exists_check(shot_id="task", path=task_dir / filename, check_name=filename.replace(".json", "_exists")),
    ]
    report = _build_qc_report(final_checks)
    deps.storage.save_json_artifact(task.task_id, filename, report)

<<<<<<< HEAD
    overlay_candidates = list(merged_candidates.values())
    updates = {
        "qc_report": report,
        "qc_report_v2": report,
        "needs_overlay_fallback": bool(overlay_candidates),
        "overlay_fallback_candidates": overlay_candidates,
        "logs": [
            *logs,
            f"[run_qc] completed workflow_version=v2 render_variant={render_variant} passed={report.passed} checks={len(report.checks)}",
            f"[run_qc] needs_overlay_fallback={str(bool(overlay_candidates)).lower()}",
=======
    updates = {
        "qc_report": report,
        "logs": [
            *logs,
            f"[run_qc] completed render_variant={render_variant} passed={report.passed} checks={len(report.checks)}",
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
            f"[run_qc] saved {filename}",
        ],
    }
    if render_variant == "preview":
        updates["preview_qc_report"] = report
    return updates


<<<<<<< HEAD
def _build_v2_text_check(*, image, prompt_shot, ocr_service, overlay_applied: bool) -> tuple[QCCheck, str | None]:
    """用 OCR 做 v2 图内文案的最小可用检查。

    判定原则：
    - 标题命中，且副标题命中或副标题为空：通过
    - OCR 完全没有文字：warning，并建议 fallback
    - OCR 有文字但与预期不匹配：warning，并建议 fallback

    这里故意不做严格逐字校验，因为当前 OCR 能力和图片模型直出稳定性
    还不足以支撑更强判断。
    """
    ocr_texts = list(getattr(ocr_service, "read_text", lambda _: [])(image.image_path) or [])
    normalized_ocr = " ".join(_normalize_text(item).lower() for item in ocr_texts if _normalize_text(item))
    title = _normalize_text(prompt_shot.title_copy)
    subtitle = _normalize_text(prompt_shot.subtitle_copy)
    title_matched = bool(title and title.lower() in normalized_ocr)
    subtitle_matched = bool(subtitle and subtitle.lower() in normalized_ocr)
    if title_matched and (subtitle_matched or not subtitle):
        status = "passed"
        fallback_reason = None
    elif not ocr_texts:
        status = "warning"
        fallback_reason = "ocr_no_text_detected_for_direct_text_image"
    else:
        status = "warning"
        fallback_reason = "ocr_text_mismatch_with_expected_copy"
    details = (
        f"expected_title={title or '-'},expected_subtitle={subtitle or '-'},"
        f"ocr_texts={ocr_texts[:6] or ['none']},"
        f"title_matched={title_matched},subtitle_matched={subtitle_matched},"
        f"overlay_applied={overlay_applied}"
    )
    return (
        QCCheck(
            shot_id=image.shot_id,
            check_name="text_readability_check",
            passed=status == "passed",
            status=status,
            details=details,
            related_shot_id=image.shot_id,
        ),
        fallback_reason,
    )


def _build_v2_shot_completeness_check(*, prompt_shot_map: dict[str, object], generation_result, render_variant: str) -> QCCheck:
    """按 v2 prompt_plan_v2 的目标图位检查出图完整性。"""
    expected_ids = list(prompt_shot_map.keys())
    actual_ids = [image.shot_id for image in generation_result.images]
    missing_ids = [shot_id for shot_id in expected_ids if shot_id not in actual_ids]
    unexpected_ids = [shot_id for shot_id in actual_ids if shot_id not in expected_ids]
    if not missing_ids and not unexpected_ids:
        return QCCheck(
            shot_id="task",
            check_name="shot_completeness_check",
            passed=True,
            details=f"render_variant={render_variant}, image_count={len(actual_ids)}, missing_shots=[]",
            related_shot_id="task",
        )
    status = "failed" if render_variant == "final" else "warning"
    return QCCheck(
        shot_id="task",
        check_name="shot_completeness_check",
        passed=status == "passed",
        status=status,
        details=f"render_variant={render_variant}, missing_shots={missing_ids}, unexpected_shots={unexpected_ids}",
        related_shot_id="task",
    )


def _build_task_structure_checks_v1(*, task_dir: Path, render_variant: str) -> list[QCCheck]:
    """构建 v1 任务目录完整性检查。"""
=======
def _build_task_structure_checks(*, task_dir: Path, render_variant: str) -> list[QCCheck]:
    """构建任务目录完整性检查。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    checks = [
        build_file_exists_check(shot_id="task", path=task_dir / "task.json", check_name="task_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "product_analysis.json", check_name="product_analysis_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "style_architecture.json", check_name="style_architecture_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "shot_plan.json", check_name="shot_plan_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "copy_plan.json", check_name="copy_plan_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "layout_plan.json", check_name="layout_plan_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "shot_prompt_specs.json", check_name="shot_prompt_specs_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "image_prompt_plan.json", check_name="image_prompt_plan_json_exists"),
    ]
<<<<<<< HEAD
    checks.extend(_build_render_variant_structure_checks(task_dir=task_dir, render_variant=render_variant))
    return checks


def _build_task_structure_checks_v2(*, task_dir: Path, render_variant: str) -> list[QCCheck]:
    """构建 v2 任务目录完整性检查。"""
    checks = [
        build_file_exists_check(shot_id="task", path=task_dir / "task.json", check_name="task_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "director_output.json", check_name="director_output_json_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "prompt_plan_v2.json", check_name="prompt_plan_v2_json_exists"),
    ]
    checks.extend(_build_render_variant_structure_checks(task_dir=task_dir, render_variant=render_variant))
    return checks


def _build_render_variant_structure_checks(*, task_dir: Path, render_variant: str) -> list[QCCheck]:
    """按 preview/final 追加输出目录检查。"""
    if render_variant == "preview":
        return [
            build_dir_exists_check(shot_id="task", path=task_dir / "generated_preview", check_name="generated_preview_dir_exists"),
            build_dir_exists_check(shot_id="task", path=task_dir / "final_preview", check_name="final_preview_dir_exists"),
            build_file_exists_check(shot_id="task", path=task_dir / "preview_text_regions.json", check_name="preview_text_regions_json_exists"),
            build_dir_exists_check(shot_id="task", path=task_dir / "previews", check_name="previews_dir_exists"),
            build_dir_exists_check(shot_id="task", path=task_dir / "exports", check_name="exports_dir_exists"),
        ]
    return [
        build_dir_exists_check(shot_id="task", path=task_dir / "generated", check_name="generated_dir_exists"),
        build_dir_exists_check(shot_id="task", path=task_dir / "final", check_name="final_dir_exists"),
        build_file_exists_check(shot_id="task", path=task_dir / "final_text_regions.json", check_name="final_text_regions_json_exists"),
        build_dir_exists_check(shot_id="task", path=task_dir / "previews", check_name="previews_dir_exists"),
        build_dir_exists_check(shot_id="task", path=task_dir / "exports", check_name="exports_dir_exists"),
    ]
=======
    if render_variant == "preview":
        checks.extend(
            [
                build_dir_exists_check(shot_id="task", path=task_dir / "generated_preview", check_name="generated_preview_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "final_preview", check_name="final_preview_dir_exists"),
                build_file_exists_check(shot_id="task", path=task_dir / "preview_text_regions.json", check_name="preview_text_regions_json_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "previews", check_name="previews_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "exports", check_name="exports_dir_exists"),
            ]
        )
    else:
        checks.extend(
            [
                build_dir_exists_check(shot_id="task", path=task_dir / "generated", check_name="generated_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "final", check_name="final_dir_exists"),
                build_file_exists_check(shot_id="task", path=task_dir / "final_text_regions.json", check_name="final_text_regions_json_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "previews", check_name="previews_dir_exists"),
                build_dir_exists_check(shot_id="task", path=task_dir / "exports", check_name="exports_dir_exists"),
            ]
        )
    return checks
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c


def _build_qc_report(checks: list[QCCheck]) -> QCReport:
    """根据单项检查汇总整体 QC 结果。"""
    has_failed = any(check.status == "failed" for check in checks)
    review_required = any(check.status in {"warning", "failed"} for check in checks)
    return QCReport(
        passed=not has_failed,
        review_required=review_required,
        checks=checks,
        shot_completeness_check=_build_summary_items(checks, {"shot_completeness_check"}),
        product_consistency_check=_build_summary_items(checks, {"product_consistency_check"}),
        shot_type_match_check=_build_summary_items(checks, {"shot_type_match_check"}),
<<<<<<< HEAD
=======
        visual_shot_diversity_check=_build_summary_items(checks, {"visual_shot_diversity_check"}),
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        text_safe_zone_check=_build_summary_items(checks, {"text_safe_zone_check"}),
        text_readability_check=_build_summary_items(checks, {"text_readability_check"}),
    )


def _build_summary_items(checks: list[QCCheck], names: set[str]) -> list[QCCheckSummary]:
<<<<<<< HEAD
    """把 checks 列表投影成结果页更容易读取的根级摘要字段。"""
=======
    """把 checks 列表投影成结果页更容易读取的根级别摘要字段。"""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    return [
        QCCheckSummary(
            status=check.status or ("passed" if check.passed else "failed"),
            details=check.details,
            related_shot_id=check.related_shot_id or check.shot_id,
            evidence_completeness=check.evidence_completeness,
        )
        for check in checks
        if check.check_name in names
    ]


def _resolve_text_render_reports(*, state: WorkflowState, task_dir: Path, render_variant: str) -> dict[str, dict]:
    """优先从 state 读取真实文本区域，没有再从落盘 JSON 恢复。"""
    state_reports = dict(state.get("text_render_reports") or {})
    if state_reports:
        return state_reports
    text_regions_path = task_dir / ("preview_text_regions.json" if render_variant == "preview" else "final_text_regions.json")
    if not text_regions_path.exists():
        return {}
    payload = json.loads(text_regions_path.read_text(encoding="utf-8"))
<<<<<<< HEAD
    return {
        str(item.get("shot_id")): item
        for item in payload.get("shots", [])
=======
    shots = payload.get("shots", [])
    return {
        str(item.get("shot_id")): item
        for item in shots
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        if item.get("shot_id")
    }


<<<<<<< HEAD
def _resolve_workflow_version(state: WorkflowState) -> str:
    """优先使用 state.workflow_version，缺失时回退到 v1。"""
    explicit_value = str(state.get("workflow_version") or "").strip().lower()
    if explicit_value in {"v1", "v2"}:
        return explicit_value
    return "v1"


def _normalize_text(value: str) -> str:
    """统一规整 OCR 文本和预期文案。"""
    return " ".join(str(value or "").split())
=======
def _resolve_hero_reference_image_path(*, generation_result, shot_plan) -> str:
    """解析 hero_brand 对应成图路径，供其他 shot 做轻量相似度对比。"""
    hero_shot_ids = [shot.shot_id for shot in shot_plan.shots if shot.shot_type == "hero_brand"]
    if not hero_shot_ids:
        return ""
    image_map = {image.shot_id: image.image_path for image in generation_result.images}
    for shot_id in hero_shot_ids:
        image_path = image_map.get(shot_id)
        if image_path:
            return str(image_path)
    return ""
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
