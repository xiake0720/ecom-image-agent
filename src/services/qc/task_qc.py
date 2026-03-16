"""任务级 QC 规则集合。

文件位置：
- `src/services/qc/task_qc.py`

核心职责：
- 提供 `run_qc` 节点使用的轻量规则检查函数。
- 当前重点覆盖工程检查、文字可读性检查，以及茶叶 Phase 1 的图像层合同检查。

设计原则：
- 不引入重型视觉模型。
- 优先做规则化、可解释、可测试的检查。
- 所有检查都必须输出足够明确的 `details`，便于后续人工定位问题。
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path
import re

from PIL import Image, ImageFilter, ImageStat

from src.domain.copy_plan import CopyItem
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.domain.product_analysis import ProductAnalysis
from src.domain.qc_report import QCCheck
from src.domain.shot_plan import ShotPlan, ShotSpec
from src.services.planning.tea_shot_planner import TEA_PHASE1_SHOTS, get_tea_template_shot_pairs


TEA_CATEGORY_FAMILY = {"tea", "tea_gift_box", "tea_packaging"}
MIN_COMMERCIAL_FONT_SIZES = {
    "title": 40,
    "subtitle": 24,
    "bullets": 22,
    "cta": 22,
}
SEVERE_MIN_FONT_SCALE = 0.8
MIN_TEXT_REGION_RATIO_WARNING = 0.012
MIN_TEXT_REGION_RATIO_FAILED = 0.006
VISUAL_SIMILARITY_WARNING_THRESHOLD = 0.94


def build_file_exists_check(*, shot_id: str, path: Path, check_name: str) -> QCCheck:
    """检查单个文件是否存在。"""
    return QCCheck(
        shot_id=shot_id,
        check_name=check_name,
        passed=path.exists(),
        details=str(path),
    )


def build_dir_exists_check(*, shot_id: str, path: Path, check_name: str) -> QCCheck:
    """检查目录是否存在。"""
    return QCCheck(
        shot_id=shot_id,
        check_name=check_name,
        passed=path.exists() and path.is_dir(),
        details=str(path),
    )


def build_task_output_dimension_check(image: GeneratedImage, *, expected_size: str) -> QCCheck:
    """检查最终图片尺寸是否匹配任务要求。"""
    expected_width, expected_height = [int(value) for value in expected_size.split("x", maxsplit=1)]
    with Image.open(image.image_path) as payload:
        width, height = payload.size
    passed = width == expected_width and height == expected_height
    return QCCheck(
        shot_id=image.shot_id,
        check_name="task_output_dimension",
        passed=passed,
        details=f"expected={expected_width}x{expected_height}, actual={width}x{height}",
    )


def build_text_overflow_risk_check(copy_item: CopyItem, layout_item: LayoutItem) -> QCCheck:
    """用静态规则估算文字是否存在溢出风险。"""
    block_map = {block.kind: block for block in layout_item.blocks}
    details: list[str] = []
    passed = True
    for kind, text in _iter_copy_texts(copy_item):
        block = block_map.get(kind)
        if block is None:
            details.append(f"{kind}:missing_block")
            continue
        estimated_height = _estimate_text_height(text, block)
        risk = estimated_height > int(block.height * 1.1)
        if risk:
            passed = False
        details.append(
            f"{kind}:len={len(text)},block={block.width}x{block.height},estimated_height={estimated_height},risk={risk}"
        )
    return QCCheck(
        shot_id=copy_item.shot_id,
        check_name="text_overflow_static_risk",
        passed=passed,
        details="; ".join(details) if details else "no_text_blocks",
    )


def build_text_background_contrast_check(image: GeneratedImage, layout_item: LayoutItem) -> QCCheck:
    """检查文字区域背景是否具备基本可读性。"""
    with Image.open(image.image_path) as payload:
        region = _crop_text_region(payload, layout_item)
        grayscale = region.convert("L")
        stat = ImageStat.Stat(grayscale)
        luma_mean = stat.mean[0]
        luma_stddev = stat.stddev[0]
        luma_range = grayscale.getextrema()[1] - grayscale.getextrema()[0]
    contrast_score = min(1.0, ((luma_range / 255.0) * 0.65) + (min(luma_stddev / 64.0, 1.0) * 0.35))
    status = "warning" if contrast_score < 0.28 else "passed"
    details = (
        f"contrast_score={contrast_score:.3f},luma_mean={luma_mean:.1f},"
        f"luma_stddev={luma_stddev:.1f},luma_range={luma_range},"
        f"region={region.width}x{region.height}"
    )
    return QCCheck(
        shot_id=image.shot_id,
        check_name="text_background_contrast",
        passed=status == "passed",
        status=status,
        details=details,
    )


def build_text_area_complexity_check(image: GeneratedImage, layout_item: LayoutItem) -> QCCheck:
    """检查文字区是否过于复杂，导致贴字不稳。"""
    with Image.open(image.image_path) as payload:
        region = _crop_text_region(payload, layout_item, padding_ratio=0.12)
        grayscale = region.convert("L")
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        edge_density = edge_stat.mean[0] / 255.0
        texture_stddev = ImageStat.Stat(grayscale).stddev[0]
    complexity_score = min(1.0, (edge_density * 0.7) + (min(texture_stddev / 80.0, 1.0) * 0.3))
    status = "warning" if complexity_score > 0.22 else "passed"
    details = (
        f"complexity_score={complexity_score:.3f},edge_density={edge_density:.3f},"
        f"texture_stddev={texture_stddev:.1f},region={region.width}x{region.height}"
    )
    return QCCheck(
        shot_id=image.shot_id,
        check_name="text_area_complexity",
        passed=status == "passed",
        status=status,
        details=details,
    )


def build_safe_zone_overlap_risk_check(layout_item: LayoutItem, shot: ShotSpec | None) -> QCCheck:
    """检查文字安全区是否过于接近主体高权重区域。"""
    text_rect = _text_rect_from_layout(layout_item)
    focus_rect = _estimate_subject_focus_rect(layout_item=layout_item, shot=shot)
    overlap_ratio = _intersection_area(text_rect, focus_rect) / max(text_rect[2] * text_rect[3], 1)
    center_distance = math.dist(
        (text_rect[0] + (text_rect[2] / 2), text_rect[1] + (text_rect[3] / 2)),
        (focus_rect[0] + (focus_rect[2] / 2), focus_rect[1] + (focus_rect[3] / 2)),
    )
    canvas_diagonal = math.dist((0, 0), (layout_item.canvas_width, layout_item.canvas_height))
    proximity_score = 1.0 - min(1.0, center_distance / max(canvas_diagonal * 0.42, 1))
    risk_score = min(1.0, (overlap_ratio * 0.7) + (proximity_score * 0.3))
    status = "warning" if risk_score > 0.28 else "passed"
    details = (
        f"risk_score={risk_score:.3f},overlap_ratio={overlap_ratio:.3f},"
        f"proximity_score={proximity_score:.3f},text_rect={text_rect},focus_rect={focus_rect}"
    )
    return QCCheck(
        shot_id=layout_item.shot_id,
        check_name="safe_zone_overlap_risk",
        passed=status == "passed",
        status=status,
        details=details,
    )


def build_text_safe_zone_check(
    *,
    shot_id: str,
    layout_item: LayoutItem,
    shot: ShotSpec | None,
    text_render_report: dict | None = None,
) -> QCCheck:
    """检查实际文字区域是否明显压到主体高权重区域。"""
    text_rect, region_source = _resolve_text_rect(text_render_report=text_render_report, layout_item=layout_item)
    focus_rect = _estimate_subject_focus_rect(layout_item=layout_item, shot=shot)
    overlap_ratio = _intersection_area(text_rect, focus_rect) / max(text_rect[2] * text_rect[3], 1)
    center_distance = math.dist(
        (text_rect[0] + (text_rect[2] / 2), text_rect[1] + (text_rect[3] / 2)),
        (focus_rect[0] + (focus_rect[2] / 2), focus_rect[1] + (focus_rect[3] / 2)),
    )
    canvas_diagonal = math.dist((0, 0), (layout_item.canvas_width, layout_item.canvas_height))
    proximity_score = 1.0 - min(1.0, center_distance / max(canvas_diagonal * 0.42, 1))
    risk_score = min(1.0, (overlap_ratio * 0.75) + (proximity_score * 0.25))
    if overlap_ratio >= 0.18 or risk_score >= 0.48:
        status = "failed"
    elif overlap_ratio >= 0.08 or risk_score >= 0.28:
        status = "warning"
    else:
        status = "passed"
    return QCCheck(
        shot_id=shot_id,
        check_name="text_safe_zone_check",
        passed=status == "passed",
        status=status,
        details=(
            f"text_safe_zone={layout_item.text_safe_zone},"
            f"overlap_ratio={overlap_ratio:.3f},"
            f"proximity_score={proximity_score:.3f},"
            f"risk_score={risk_score:.3f},"
            f"text_rect={text_rect},"
            f"focus_rect={focus_rect},"
            f"actual_render_region={'yes' if region_source == 'actual' else 'no'},"
            f"region_source={region_source}"
        ),
        related_shot_id=shot_id,
    )


def build_text_readability_check(
    *,
    image: GeneratedImage,
    shot_id: str,
    copy_item: CopyItem,
    layout_item: LayoutItem,
    text_render_report: dict | None = None,
) -> QCCheck:
    """检查文字区域是否具备基本可读性。"""
    contrast_score, complexity_score = _calculate_text_region_metrics(
        image_path=image.image_path,
        layout_item=layout_item,
        text_render_report=text_render_report,
    )
    overflow_detected = _has_text_overflow(text_render_report=text_render_report)
    min_font_size_hit = _has_min_font_size_hit(text_render_report=text_render_report)
    density_ratio = _resolve_text_density_ratio(text_render_report=text_render_report, copy_item=copy_item, layout_item=layout_item)
    hierarchy_ok = _has_basic_text_hierarchy(text_render_report=text_render_report, layout_item=layout_item)
    used_font_sizes, font_size_source = _resolve_used_font_sizes(text_render_report=text_render_report, layout_item=layout_item)
    small_font_issues, severe_small_font = _evaluate_min_readable_font_issues(used_font_sizes)
    merged_text_region_ratio, region_ratio_source = _resolve_merged_text_region_ratio(
        text_render_report=text_render_report,
        layout_item=layout_item,
    )
    font_source = str((text_render_report or {}).get("font_source", "-"))
    fallback_used = bool((text_render_report or {}).get("fallback_used", False))

    issues: list[str] = []
    if overflow_detected:
        issues.append("text_overflow_detected")
    if contrast_score < 0.28:
        issues.append("low_contrast")
    if complexity_score > 0.22:
        issues.append("background_too_busy")
    if density_ratio > 0.92:
        issues.append("text_too_dense")
    if not hierarchy_ok:
        issues.append("title_subtitle_hierarchy_weak")
    issues.extend(small_font_issues)
    if merged_text_region_ratio < MIN_TEXT_REGION_RATIO_FAILED:
        issues.append("merged_text_region_too_small")
    elif merged_text_region_ratio < MIN_TEXT_REGION_RATIO_WARNING:
        issues.append("merged_text_region_small")

    if overflow_detected or severe_small_font or merged_text_region_ratio < MIN_TEXT_REGION_RATIO_FAILED:
        status = "failed"
    elif issues:
        status = "warning"
    else:
        status = "passed"
    return QCCheck(
        shot_id=shot_id,
        check_name="text_readability_check",
        passed=status == "passed",
        status=status,
        details=(
            f"contrast_score={contrast_score:.3f},"
            f"complexity_score={complexity_score:.3f},"
            f"density_ratio={density_ratio:.3f},"
            f"merged_text_region_ratio={merged_text_region_ratio:.4f},"
            f"region_ratio_source={region_ratio_source},"
            f"hierarchy_ok={hierarchy_ok},"
            f"min_font_size_hit={min_font_size_hit},"
            f"font_size_source={font_size_source},"
            f"used_font_sizes={used_font_sizes},"
            f"min_readable_thresholds={MIN_COMMERCIAL_FONT_SIZES},"
            f"overflow_detected={overflow_detected},"
            f"font_source={font_source},"
            f"fallback_used={fallback_used},"
            f"issues={issues or ['none']}"
        ),
        related_shot_id=shot_id,
    )


def build_shot_completeness_check(
    *,
    render_variant: str,
    generation_result: GenerationResult,
    shot_plan: ShotPlan,
    product_analysis: ProductAnalysis | None,
) -> QCCheck:
    """检查茶叶 Phase 1 五图是否完整。

    规则：
    - final 必须完整 5 张，否则直接 failed。
    - preview 允许不满 5 张，但要明确标记为 preview warning。
    - 非茶叶固定五图链路返回 passed，并说明 not_applicable。
    """
    if not _is_tea_phase1(product_analysis=product_analysis, shot_plan=shot_plan):
        return QCCheck(
            shot_id="task",
            check_name="shot_completeness_check",
            passed=True,
            details=f"render_variant={render_variant}, scope=non_tea_or_not_fixed_phase1",
            related_shot_id="task",
        )

    # 茶叶模板现在按包装族分流，QC 不能再写死礼盒模板，必须以当前 shot_plan 为准。
    expected_pairs = (
        get_tea_template_shot_pairs(product_analysis)
        if product_analysis is not None
        else tuple((shot.shot_id, shot.shot_type) for shot in shot_plan.shots)
    )
    actual_ids = [image.shot_id for image in generation_result.images]
    actual_id_set = set(actual_ids)
    missing_pairs = [f"{shot_id}:{shot_type}" for shot_id, shot_type in expected_pairs if shot_id not in actual_id_set]
    unexpected_ids = [shot_id for shot_id in actual_ids if shot_id not in {item[0] for item in expected_pairs}]
    duplicate_ids = sorted({shot_id for shot_id in actual_ids if actual_ids.count(shot_id) > 1})

    issues = []
    if len(generation_result.images) != len(expected_pairs):
        issues.append(f"image_count={len(generation_result.images)} expected={len(expected_pairs)}")
    if missing_pairs:
        issues.append(f"missing_shots={missing_pairs}")
    if unexpected_ids:
        issues.append(f"unexpected_shots={unexpected_ids}")
    if duplicate_ids:
        issues.append(f"duplicate_shots={duplicate_ids}")

    if not issues:
        return QCCheck(
            shot_id="task",
            check_name="shot_completeness_check",
            passed=True,
            details=f"render_variant={render_variant}, image_count=5, missing_shots=[]",
            related_shot_id="task",
        )

    status = "failed" if render_variant == "final" else "warning"
    return QCCheck(
        shot_id="task",
        check_name="shot_completeness_check",
        passed=status == "passed",
        status=status,
        details=f"render_variant={render_variant}, {'; '.join(issues)}",
        related_shot_id="task",
    )


def build_visual_shot_diversity_check(
    *,
    generation_result: GenerationResult,
    shot_plan: ShotPlan,
    product_analysis: ProductAnalysis | None,
) -> QCCheck:
    """检查整组结果图是否过度趋同，尤其是多张图退化成同类 hero packshot。"""
    if not _is_tea_phase1(product_analysis=product_analysis, shot_plan=shot_plan):
        return QCCheck(
            shot_id="task",
            check_name="visual_shot_diversity_check",
            passed=True,
            details="scope=non_tea_or_not_fixed_phase1",
            related_shot_id="task",
        )
    if len(generation_result.images) < 3:
        return QCCheck(
            shot_id="task",
            check_name="visual_shot_diversity_check",
            passed=True,
            details=f"image_count={len(generation_result.images)}, scope=not_enough_images",
            related_shot_id="task",
        )

    shot_type_map = {shot.shot_id: shot.shot_type for shot in shot_plan.shots}
    signatures = {
        image.shot_id: _compute_image_signature(image.image_path)
        for image in generation_result.images
    }
    similar_pairs: list[str] = []
    hero_like_shots: list[str] = []
    hero_shot_id = next((shot.shot_id for shot in shot_plan.shots if shot.shot_type == "hero_brand"), "")
    for index, left_image in enumerate(generation_result.images):
        left_signature = signatures[left_image.shot_id]
        for right_image in generation_result.images[index + 1:]:
            right_signature = signatures[right_image.shot_id]
            similarity_score = _calculate_signature_similarity(left_signature, right_signature)
            if similarity_score < VISUAL_SIMILARITY_WARNING_THRESHOLD:
                continue
            pair_label = (
                f"{left_image.shot_id}:{shot_type_map.get(left_image.shot_id, '-')}~"
                f"{right_image.shot_id}:{shot_type_map.get(right_image.shot_id, '-')}="
                f"{similarity_score:.3f}"
            )
            similar_pairs.append(pair_label)
            if hero_shot_id and left_image.shot_id == hero_shot_id:
                hero_like_shots.append(right_image.shot_id)
            elif hero_shot_id and right_image.shot_id == hero_shot_id:
                hero_like_shots.append(left_image.shot_id)

    if similar_pairs:
        return QCCheck(
            shot_id="task",
            check_name="visual_shot_diversity_check",
            passed=False,
            status="warning",
            details=(
                f"image_count={len(generation_result.images)},"
                f"hero_shot_id={hero_shot_id or '-'},"
                f"hero_like_shots={sorted(set(hero_like_shots)) or ['none']},"
                f"similar_pairs={similar_pairs}"
            ),
            related_shot_id="task",
        )

    return QCCheck(
        shot_id="task",
        check_name="visual_shot_diversity_check",
        passed=True,
        details=f"image_count={len(generation_result.images)}, similar_pairs=[]",
        related_shot_id="task",
    )


def build_product_consistency_check(
    *,
    image: GeneratedImage,
    product_analysis: ProductAnalysis | None,
    expected_generation_mode: str,
    actual_generation_mode: str,
    reference_asset_ids: list[str],
    prompt_generation_mode: str,
    ocr_service,
    render_variant: str,
) -> QCCheck:
    """检查当前生成结果是否还保留商品锚点信息。

    轻量规则包括：
    - image_edit 是否真的拿到了参考图
    - generation_mode 期望/实际是否一致
    - OCR 是否还能读到关键品牌字样
    - 主色锚点是否还能在图片里检测到
    - 中心主体是否存在基本视觉信号
    """
    warnings: list[str] = []
    failures: list[str] = []

    if expected_generation_mode == "image_edit" and not reference_asset_ids:
        issue = "image_edit_expected_but_reference_assets_missing"
        if render_variant == "final":
            failures.append(issue)
        else:
            warnings.append(issue)
    if actual_generation_mode == "image_edit" and not reference_asset_ids:
        issue = "image_edit_actual_but_reference_assets_missing"
        if render_variant == "final":
            failures.append(issue)
        else:
            warnings.append(issue)
    if actual_generation_mode != expected_generation_mode:
        warnings.append(f"expected_{expected_generation_mode}_but_actual_{actual_generation_mode}")
    if prompt_generation_mode != expected_generation_mode:
        warnings.append(f"prompt_generation_mode_{prompt_generation_mode}_mismatch")

    ocr_texts = list(getattr(ocr_service, "read_text", lambda _: [])(image.image_path) or [])
    valid_ocr_texts = _filter_effective_texts(ocr_texts)
    target_brand_texts = _collect_brand_anchor_texts(product_analysis)
    valid_brand_targets = _filter_effective_texts(target_brand_texts)
    text_anchor_source = str(getattr(product_analysis, "text_anchor_source", "") or "none")
    text_anchor_status = str(getattr(product_analysis, "text_anchor_status", "") or "unreadable")
    brand_text_matched = True
    text_anchor_consistency = "no_text_anchor"
    if valid_brand_targets and valid_ocr_texts:
        normalized_ocr = " ".join(_normalize_text(item).lower() for item in valid_ocr_texts)
        brand_text_matched = any(_normalize_text(item).lower() in normalized_ocr for item in valid_brand_targets)
        if not brand_text_matched:
            warnings.append("brand_text_anchor_not_detected")
            text_anchor_consistency = "mismatch"
        else:
            text_anchor_consistency = "matched"
    elif valid_brand_targets and not valid_ocr_texts:
        warnings.append("ocr_missing_for_text_anchor_compare")
        brand_text_matched = False
        text_anchor_consistency = "ocr_missing"

    primary_color_value = getattr(product_analysis, "primary_color", "")
    primary_color_detected = _detect_primary_color_presence(image.image_path, primary_color_value)
    if primary_color_detected is False:
        warnings.append("primary_color_anchor_weak")

    subject_signal_present = _detect_center_subject_signal(image.image_path)
    if not subject_signal_present:
        warnings.append("package_subject_signal_weak")
    visual_consistency = _resolve_visual_consistency_label(
        expected_generation_mode=expected_generation_mode,
        actual_generation_mode=actual_generation_mode,
        reference_asset_ids=reference_asset_ids,
        primary_color_detected=primary_color_detected,
        subject_signal_present=subject_signal_present,
    )

    # 商品一致性检查必须建立在“有证据”的前提上。
    # 如果品牌文字、OCR、主色或 image_edit 参考图这些基础证据缺失，就不能默认放行。
    evidence_issues: list[str] = []
    if not valid_brand_targets:
        evidence_issues.append("brand_text_targets_missing")
    if not valid_ocr_texts:
        evidence_issues.append("ocr_texts_missing")
    if primary_color_detected is None:
        evidence_issues.append("primary_color_detected_missing")
    if expected_generation_mode == "image_edit" and not reference_asset_ids:
        evidence_issues.append("reference_asset_ids_missing_for_expected_image_edit")
    if actual_generation_mode == "image_edit" and not reference_asset_ids:
        evidence_issues.append("reference_asset_ids_missing_for_actual_image_edit")

    evidence_completeness = _classify_evidence_completeness(evidence_issues=evidence_issues)
    decision_reason = "all_required_evidence_present"
    if evidence_completeness == "missing":
        decision_reason = "no_reliable_product_evidence_available"
        if render_variant == "final" or expected_generation_mode == "image_edit" or actual_generation_mode == "image_edit":
            failures.append("product_consistency_evidence_missing")
        else:
            warnings.append("product_consistency_evidence_missing")
    elif evidence_completeness == "partial":
        decision_reason = "partial_product_evidence_only"
        warnings.append("product_consistency_evidence_partial")

    if failures:
        status = "failed"
        if decision_reason == "all_required_evidence_present":
            decision_reason = "hard_consistency_rule_failed"
    elif warnings:
        status = "warning"
        if decision_reason == "all_required_evidence_present":
            decision_reason = "consistency_risk_detected"
    else:
        status = "passed"

    return QCCheck(
        shot_id=image.shot_id,
        check_name="product_consistency_check",
        passed=status == "passed",
        status=status,
        evidence_completeness=evidence_completeness,
        details=(
            f"expected_generation_mode={expected_generation_mode},"
            f"actual_generation_mode={actual_generation_mode},"
            f"prompt_generation_mode={prompt_generation_mode},"
            f"reference_asset_ids={reference_asset_ids},"
            f"brand_text_targets={valid_brand_targets or ['none']},"
            f"text_anchor_source={text_anchor_source},"
            f"text_anchor_status={text_anchor_status},"
            f"text_anchor_count={len(valid_brand_targets)},"
            f"ocr_texts={valid_ocr_texts[:5] or ['none']},"
            f"brand_text_matched={brand_text_matched},"
            f"text_anchor_consistency={text_anchor_consistency},"
            f"visual_consistency={visual_consistency},"
            f"primary_color={primary_color_value or '-'},"
            f"primary_color_detected={primary_color_detected},"
            f"subject_signal_present={subject_signal_present},"
            f"evidence_completeness={evidence_completeness},"
            f"evidence_issues={evidence_issues or ['none']},"
            f"decision_reason={decision_reason},"
            f"warnings={warnings or ['none']},"
            f"failures={failures or ['none']}"
        ),
        related_shot_id=image.shot_id,
    )


def build_shot_type_match_check(
    *,
    image: GeneratedImage,
    shot: ShotSpec | None,
    shot_prompt_spec=None,
    hero_reference_image_path: str = "",
) -> QCCheck:
    """检查当前 shot 的结构化描述是否与既定图位类型一致。

    这里先做 metadata-based 规则：
    - 不尝试用重型 CV 分类图片内容。
    - 优先检查 shot_type、goal、focus、scene_direction、composition_direction、required_subjects、
      render_constraints 这些元数据是否满足该图位的最小要求。
    """
    if shot is None:
        return QCCheck(
            shot_id=image.shot_id,
            check_name="shot_type_match_check",
            passed=False,
            status="failed",
            details="shot_plan_entry_missing",
            related_shot_id=image.shot_id,
        )

    combined_text = _build_shot_type_evidence_text(shot=shot, shot_prompt_spec=shot_prompt_spec)
    required_tokens, metadata_warnings = _evaluate_shot_type_rules(
        shot_type=shot.shot_type,
        combined_text=combined_text,
        shot_prompt_spec=shot_prompt_spec,
    )
    visual_warnings, visual_metrics = _evaluate_shot_type_visual_rules(
        image_path=image.image_path,
        shot_type=shot.shot_type,
        hero_reference_image_path=hero_reference_image_path,
    )
    warnings = [*metadata_warnings, *visual_warnings]
    status = "warning" if warnings else "passed"
    return QCCheck(
        shot_id=image.shot_id,
        check_name="shot_type_match_check",
        passed=status == "passed",
        status=status,
        details=(
            f"shot_type={shot.shot_type},required_tokens={required_tokens},"
            f"evidence_summary={combined_text[:220]},warnings={warnings or ['none']}"
            f",metadata_warnings={metadata_warnings or ['none']}"
            f",visual_warnings={visual_warnings or ['none']}"
            f",visual_metrics={visual_metrics}"
        ),
        related_shot_id=image.shot_id,
    )


def _iter_copy_texts(copy_item: CopyItem) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if copy_item.title:
        items.append(("title", copy_item.title))
    if copy_item.subtitle:
        items.append(("subtitle", copy_item.subtitle))
    if copy_item.bullets:
        items.append(("bullets", "\n".join(copy_item.bullets)))
    if copy_item.cta:
        items.append(("cta", copy_item.cta))
    return items


def _estimate_text_height(text: str, block: LayoutBlock) -> int:
    chars_per_line = max(1, int(block.width / max(block.font_size * 0.55, 1)))
    line_height = max(1, int(block.font_size * 1.35))
    paragraph_lines = 0
    for paragraph in text.splitlines() or [""]:
        paragraph_lines += max(1, math.ceil(len(paragraph) / chars_per_line))
    return paragraph_lines * line_height


def _crop_text_region(image: Image.Image, layout_item: LayoutItem, *, padding_ratio: float = 0.04) -> Image.Image:
    x, y, width, height = _text_rect_from_layout(layout_item)
    pad_x = int(layout_item.canvas_width * padding_ratio)
    pad_y = int(layout_item.canvas_height * padding_ratio)
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(image.width, x + width + pad_x)
    bottom = min(image.height, y + height + pad_y)
    return image.crop((left, top, right, bottom))


def _text_rect_from_layout(layout_item: LayoutItem) -> tuple[int, int, int, int]:
    if not layout_item.blocks:
        return (0, 0, max(1, layout_item.canvas_width // 3), max(1, layout_item.canvas_height // 3))
    left = min(block.x for block in layout_item.blocks)
    top = min(block.y for block in layout_item.blocks)
    right = max(block.x + block.width for block in layout_item.blocks)
    bottom = max(block.y + block.height for block in layout_item.blocks)
    return (left, top, right - left, bottom - top)


def _resolve_text_rect(
    *,
    text_render_report: dict | None,
    layout_item: LayoutItem,
) -> tuple[tuple[int, int, int, int], str]:
    """优先使用 overlay_text 的实际渲染区域，否则退回 layout block。"""
    region = _extract_actual_text_region(text_render_report)
    if region is not None:
        return region, "actual"
    return _text_rect_from_layout(layout_item), "fallback"


def _extract_actual_text_region(text_render_report: dict | None) -> tuple[int, int, int, int] | None:
    """从 overlay_text 回写或落盘的结构中提取真实文本区域。"""
    if not text_render_report:
        return None
    merged_region = text_render_report.get("merged_text_region")
    if merged_region:
        width = int(merged_region.get("width", 0))
        height = int(merged_region.get("height", 0))
        if width > 0 and height > 0:
            return (
                int(merged_region.get("x", 0)),
                int(merged_region.get("y", 0)),
                width,
                height,
            )
    actual_regions = text_render_report.get("actual_text_regions") or text_render_report.get("blocks") or []
    if actual_regions:
        left = min(int(block.get("x", 0)) for block in actual_regions)
        top = min(int(block.get("y", 0)) for block in actual_regions)
        right = max(int(block.get("x", 0)) + int(block.get("width", 0)) for block in actual_regions)
        bottom = max(int(block.get("y", 0)) + int(block.get("height", 0)) for block in actual_regions)
        if right > left and bottom > top:
            return (left, top, right - left, bottom - top)
    return None


def _estimate_subject_focus_rect(layout_item: LayoutItem, shot: ShotSpec | None) -> tuple[int, int, int, int]:
    width = int(layout_item.canvas_width * 0.38)
    height = int(layout_item.canvas_height * 0.5)
    center_x = layout_item.canvas_width * 0.5
    center_y = layout_item.canvas_height * 0.54
    composition = _normalize_text(
        " ".join(filter(None, [getattr(shot, "composition_hint", ""), getattr(shot, "composition_direction", "")]))
    )
    if "主体靠左" in composition or "主体偏左" in composition or "主体在左" in composition:
        center_x = layout_item.canvas_width * 0.38
    elif "主体靠右" in composition or "主体偏右" in composition or "主体在右" in composition:
        center_x = layout_item.canvas_width * 0.62
    if "偏下" in composition or "靠下" in composition:
        center_y = layout_item.canvas_height * 0.6
    elif "偏上" in composition or "靠上" in composition:
        center_y = layout_item.canvas_height * 0.44
    return (
        int(center_x - (width / 2)),
        int(center_y - (height / 2)),
        width,
        height,
    )


def _intersection_area(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    if right <= left or bottom <= top:
        return 0.0
    return float((right - left) * (bottom - top))


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().split())


def _filter_effective_texts(values: list[str]) -> list[str]:
    """过滤掉占位值和空字符串，避免“none”这类伪证据把一致性检查误判为通过。"""
    invalid_tokens = {"", "none", "null", "n/a", "-", "unknown"}
    return [
        normalized
        for value in values
        if (normalized := _normalize_text(str(value))).lower() not in invalid_tokens
    ]


def _classify_evidence_completeness(*, evidence_issues: list[str]) -> str:
    """把证据充分度显式写入 QC，便于区分“真的通过”和“没有证据只能人工复核”。

    约定：
    - `full`：关键证据齐全
    - `partial`：拿到了一部分证据，但还不足以稳定放行
    - `missing`：关键证据整体缺失
    """
    if not evidence_issues:
        return "full"
    unique_issue_count = len(set(evidence_issues))
    if unique_issue_count >= 3:
        return "missing"
    return "partial"


def _calculate_text_region_metrics(*, image_path: str, layout_item: LayoutItem, text_render_report: dict | None) -> tuple[float, float]:
    with Image.open(image_path) as payload:
        region = _crop_resolved_text_region(payload, layout_item=layout_item, text_render_report=text_render_report)
        grayscale = region.convert("L")
        stat = ImageStat.Stat(grayscale)
        luma_stddev = stat.stddev[0]
        luma_range = grayscale.getextrema()[1] - grayscale.getextrema()[0]
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_density = ImageStat.Stat(edges).mean[0] / 255.0
    contrast_score = min(1.0, ((luma_range / 255.0) * 0.65) + (min(luma_stddev / 64.0, 1.0) * 0.35))
    complexity_score = min(1.0, (edge_density * 0.7) + (min(luma_stddev / 80.0, 1.0) * 0.3))
    return contrast_score, complexity_score


def _crop_resolved_text_region(image: Image.Image, *, layout_item: LayoutItem, text_render_report: dict | None, padding_ratio: float = 0.04) -> Image.Image:
    x, y, width, height = _resolve_text_rect(text_render_report=text_render_report, layout_item=layout_item)[0]
    pad_x = int(layout_item.canvas_width * padding_ratio)
    pad_y = int(layout_item.canvas_height * padding_ratio)
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(image.width, x + width + pad_x)
    bottom = min(image.height, y + height + pad_y)
    return image.crop((left, top, right, bottom))


def _has_text_overflow(*, text_render_report: dict | None) -> bool:
    if not text_render_report:
        return False
    return any(bool(block.get("overflow_detected", False)) for block in text_render_report.get("blocks", []))


def _has_min_font_size_hit(*, text_render_report: dict | None) -> bool:
    """判断是否有文本块已经压到了最小可读字号。"""
    if not text_render_report:
        return False
    return any(bool(block.get("min_font_size_hit", False)) for block in text_render_report.get("blocks", []))


def _resolve_text_density_ratio(*, text_render_report: dict | None, copy_item: CopyItem, layout_item: LayoutItem) -> float:
    if text_render_report and text_render_report.get("blocks"):
        return max(float(block.get("density_ratio", 0.0)) for block in text_render_report["blocks"])
    total_chars = sum(len(text) for _, text in _iter_copy_texts(copy_item))
    total_block_area = sum(block.width * block.height for block in layout_item.blocks) or 1
    return min(1.5, total_chars / max(total_block_area / 2800.0, 1.0))


def _has_basic_text_hierarchy(*, text_render_report: dict | None, layout_item: LayoutItem) -> bool:
    if text_render_report and text_render_report.get("blocks"):
        title_block = next((block for block in text_render_report["blocks"] if block.get("kind") == "title"), None)
        subtitle_block = next((block for block in text_render_report["blocks"] if block.get("kind") == "subtitle"), None)
        if title_block and subtitle_block:
            return int(title_block.get("used_font_size", 0)) > int(subtitle_block.get("used_font_size", 0))
    block_map = {block.kind: block for block in layout_item.blocks}
    if "title" in block_map and "subtitle" in block_map:
        return block_map["title"].font_size > block_map["subtitle"].font_size
    return True


def _resolve_used_font_sizes(*, text_render_report: dict | None, layout_item: LayoutItem) -> tuple[dict[str, int], str]:
    """优先读取真实 used_font_size；缺失时回退到 layout 里的规划字号。"""
    if text_render_report and text_render_report.get("blocks"):
        sizes = {
            str(block.get("kind")): int(block.get("used_font_size", 0) or 0)
            for block in text_render_report["blocks"]
            if block.get("kind")
        }
        return sizes, "actual"
    return {block.kind: int(block.font_size) for block in layout_item.blocks}, "layout_fallback"


def _evaluate_min_readable_font_issues(used_font_sizes: dict[str, int]) -> tuple[list[str], bool]:
    """根据商用最小可读字号阈值判断是否已经小到不可接受。"""
    issues: list[str] = []
    severe_small_font = False
    for kind, min_size in MIN_COMMERCIAL_FONT_SIZES.items():
        used_size = int(used_font_sizes.get(kind, 0) or 0)
        if used_size <= 0:
            continue
        if used_size < int(min_size * SEVERE_MIN_FONT_SCALE):
            issues.append(f"{kind}_far_below_min_readable_size")
            severe_small_font = True
        elif used_size < min_size:
            issues.append(f"{kind}_below_min_readable_size")
    return issues, severe_small_font


def _resolve_merged_text_region_ratio(*, text_render_report: dict | None, layout_item: LayoutItem) -> tuple[float, str]:
    """计算真实文字区域或 fallback 文字区域占整图比例。"""
    region, source = _resolve_text_rect(text_render_report=text_render_report, layout_item=layout_item)
    region_area = max(region[2] * region[3], 1)
    canvas_area = max(layout_item.canvas_width * layout_item.canvas_height, 1)
    return region_area / canvas_area, source


def _is_tea_phase1(*, product_analysis: ProductAnalysis | None, shot_plan: ShotPlan) -> bool:
    category = str(getattr(product_analysis, "category", "") or "").strip().lower()
    shot_pairs = [(shot.shot_id, shot.shot_type) for shot in shot_plan.shots]
    expected_pairs = list(get_tea_template_shot_pairs(product_analysis)) if product_analysis is not None else []
    return category in TEA_CATEGORY_FAMILY or shot_pairs == list(TEA_PHASE1_SHOTS) or shot_pairs == expected_pairs


def _collect_brand_anchor_texts(product_analysis: ProductAnalysis | None) -> list[str]:
    if product_analysis is None:
        return []
    provider_anchors = [
        value
        for value in list(getattr(product_analysis, "must_preserve_texts", []) or [])
        if _looks_like_text_anchor(value)
    ]
    if provider_anchors:
        return provider_anchors[:5]

    fallback_candidates = [
        *list(getattr(getattr(product_analysis, "visual_identity", None), "must_preserve", []) or []),
        *list(getattr(product_analysis, "locked_elements", []) or []),
    ]
    fallback_anchors = [value for value in fallback_candidates if _looks_like_text_anchor(value)]
    return fallback_anchors[:5]


def _looks_like_text_anchor(value: str) -> bool:
    """过滤掉视觉结构描述，只保留更像真实包装文字的短文本锚点。"""
    text = _normalize_text(str(value or ""))
    if not text:
        return False
    if len(text) > 24:
        return False
    lower = text.lower()
    visual_markers = (
        "package",
        "label",
        "layout",
        "zone",
        "position",
        "placement",
        "mark",
        "silhouette",
        "structure",
        "background",
        "props",
        "轮廓",
        "标签",
        "标签区",
        "标识区",
        "区域",
        "位置",
        "结构",
        "版式",
        "留白",
        "背景",
        "主体",
        "材质",
        "纹理",
    )
    if any(marker in lower for marker in visual_markers):
        return False
    if re.search(r"\d+(?:\.\d+)?\s*(?:g|kg|ml|l|克|千克|毫升|升|袋|盒|罐)", text, re.IGNORECASE):
        return True
    if re.search(r"[A-Za-z]", text) and len(text) <= 16:
        return True
    chinese_char_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    return 2 <= chinese_char_count <= 12


def _resolve_visual_consistency_label(
    *,
    expected_generation_mode: str,
    actual_generation_mode: str,
    reference_asset_ids: list[str],
    primary_color_detected: bool | None,
    subject_signal_present: bool,
) -> str:
    """把轻量视觉证据归并成更易读的 visual_consistency 摘要。"""
    has_reference_when_needed = True
    if expected_generation_mode == "image_edit" or actual_generation_mode == "image_edit":
        has_reference_when_needed = bool(reference_asset_ids)
    strong_visual = subject_signal_present and primary_color_detected is not False and has_reference_when_needed
    partial_visual = subject_signal_present or primary_color_detected is True
    if strong_visual:
        return "strong"
    if partial_visual:
        return "partial"
    return "weak"


def _evaluate_shot_type_visual_rules(
    *,
    image_path: str,
    shot_type: str,
    hero_reference_image_path: str = "",
) -> tuple[list[str], dict[str, float | str]]:
    """用轻量图像规则补强图位匹配检查，避免只看 metadata 自证。"""
    signature = _compute_image_signature(image_path)
    visual_warnings: list[str] = []
    metrics: dict[str, float | str] = {
        "texture_score_center": round(signature["texture_score_center"], 3),
        "tea_liquid_ratio": round(signature["tea_liquid_ratio"], 3),
        "bright_neutral_ratio": round(signature["bright_neutral_ratio"], 3),
        "peripheral_complexity": round(signature["peripheral_complexity"], 3),
        "hero_similarity": "-",
    }
    if hero_reference_image_path and Path(hero_reference_image_path).exists() and hero_reference_image_path != image_path:
        hero_similarity = _calculate_signature_similarity(
            signature,
            _compute_image_signature(hero_reference_image_path),
        )
        metrics["hero_similarity"] = round(hero_similarity, 3)
    else:
        hero_similarity = None

    if shot_type == "package_detail":
        if hero_similarity is not None and hero_similarity >= VISUAL_SIMILARITY_WARNING_THRESHOLD:
            visual_warnings.append("package_detail_too_similar_to_hero")
        if signature["texture_score_center"] < 0.18:
            visual_warnings.append("package_detail_detail_signal_weak")
    elif shot_type == "dry_leaf_detail":
        if signature["texture_score_center"] < 0.22:
            visual_warnings.append("dry_leaf_texture_signal_weak")
    elif shot_type == "tea_soup_experience":
        if signature["tea_liquid_ratio"] < 0.04 and signature["bright_neutral_ratio"] < 0.10:
            visual_warnings.append("tea_soup_visual_signal_weak")
    elif shot_type in {"lifestyle_or_brewing_context", "package_in_brewing_context"}:
        if hero_similarity is not None and hero_similarity >= VISUAL_SIMILARITY_WARNING_THRESHOLD:
            visual_warnings.append("context_too_similar_to_hero")
        if signature["peripheral_complexity"] < 0.32:
            visual_warnings.append("context_props_signal_weak")

    return visual_warnings, metrics


def _compute_image_signature(image_path: str) -> dict[str, float | list[float] | list[int]]:
    """提取轻量图像特征，用于组图多样性和 shot_type 视觉规则。"""
    with Image.open(image_path) as payload:
        image = payload.convert("RGB").resize((64, 64))
        grayscale = image.convert("L")
        center_box = (16, 12, 48, 52)
        center_region = image.crop(center_box)
        periphery_region = image.copy()
        periphery_mask = Image.new("L", image.size, color=255)
        for y in range(center_box[1], center_box[3]):
            for x in range(center_box[0], center_box[2]):
                periphery_mask.putpixel((x, y), 0)
        periphery_region.putalpha(periphery_mask)

        full_stddev = sum(ImageStat.Stat(grayscale).stddev) / 1.0
        center_gray = center_region.convert("L")
        center_stddev = sum(ImageStat.Stat(center_gray).stddev) / 1.0
        full_edge_density = ImageStat.Stat(grayscale.filter(ImageFilter.FIND_EDGES)).mean[0] / 255.0
        center_edge_density = ImageStat.Stat(center_gray.filter(ImageFilter.FIND_EDGES)).mean[0] / 255.0
        periphery_rgb = _extract_periphery_region(image, center_box)
        periphery_gray = periphery_rgb.convert("L")
        periphery_stddev = ImageStat.Stat(periphery_gray).stddev[0]
        periphery_edge_density = ImageStat.Stat(periphery_gray.filter(ImageFilter.FIND_EDGES)).mean[0] / 255.0

        avg_hash_bits = _average_hash_bits(grayscale.resize((8, 8)))
        color_profile = _coarse_color_profile(image)
        tea_liquid_ratio, bright_neutral_ratio = _estimate_beverage_signal(image)

    texture_score_center = min(1.0, (center_edge_density * 0.6) + (min(center_stddev / 64.0, 1.0) * 0.4))
    peripheral_complexity = min(1.0, (periphery_edge_density * 0.6) + (min(periphery_stddev / 64.0, 1.0) * 0.4))
    return {
        "avg_hash_bits": avg_hash_bits,
        "color_profile": color_profile,
        "full_edge_density": full_edge_density,
        "center_edge_density": center_edge_density,
        "texture_score_center": texture_score_center,
        "peripheral_complexity": peripheral_complexity,
        "tea_liquid_ratio": tea_liquid_ratio,
        "bright_neutral_ratio": bright_neutral_ratio,
        "full_stddev": full_stddev,
    }


def _extract_periphery_region(image: Image.Image, center_box: tuple[int, int, int, int]) -> Image.Image:
    """从缩略图里抽出外围区域，近似表示场景道具和背景复杂度。"""
    strips = [
        image.crop((0, 0, image.width, center_box[1])),
        image.crop((0, center_box[3], image.width, image.height)),
        image.crop((0, center_box[1], center_box[0], center_box[3])),
        image.crop((center_box[2], center_box[1], image.width, center_box[3])),
    ]
    valid_strips = [strip for strip in strips if strip.width > 0 and strip.height > 0]
    if not valid_strips:
        return image
    output_width = max(strip.width for strip in valid_strips)
    output_height = sum(strip.height for strip in valid_strips)
    canvas = Image.new("RGB", (output_width, output_height))
    offset_y = 0
    for strip in valid_strips:
        canvas.paste(strip, (0, offset_y))
        offset_y += strip.height
    return canvas


def _average_hash_bits(image: Image.Image) -> list[int]:
    pixels = list(image.tobytes())
    mean_value = sum(pixels) / max(len(pixels), 1)
    return [1 if pixel >= mean_value else 0 for pixel in pixels]


def _coarse_color_profile(image: Image.Image) -> list[float]:
    """提取 12 维粗粒度色彩分布，用于比较多张图是否高度同构。"""
    channel_histograms: list[float] = []
    for channel_index in range(3):
        histogram = image.histogram()[channel_index * 256:(channel_index + 1) * 256]
        for bucket_index in range(4):
            start = bucket_index * 64
            bucket_value = sum(histogram[start:start + 64])
            channel_histograms.append(bucket_value)
    total = sum(channel_histograms) or 1.0
    return [value / total for value in channel_histograms]


def _estimate_beverage_signal(image: Image.Image) -> tuple[float, float]:
    """估算茶汤颜色和浅色杯具高亮信号，服务 tea_soup 图位检查。"""
    tea_liquid_pixels = 0
    bright_neutral_pixels = 0
    total_pixels = image.width * image.height
    pixel_access = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue = pixel_access[x, y]
            hue, saturation, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
            if 0.06 <= hue <= 0.16 and saturation >= 0.18 and 0.22 <= value <= 0.92:
                tea_liquid_pixels += 1
            if value >= 0.72 and saturation <= 0.18:
                bright_neutral_pixels += 1
    return tea_liquid_pixels / max(total_pixels, 1), bright_neutral_pixels / max(total_pixels, 1)


def _calculate_signature_similarity(left: dict[str, float | list[float] | list[int]], right: dict[str, float | list[float] | list[int]]) -> float:
    """比较两张图是否在主体布局和颜色分布上过度接近。"""
    left_hash = list(left["avg_hash_bits"])
    right_hash = list(right["avg_hash_bits"])
    hash_similarity = 1.0 - (
        sum(1 for left_bit, right_bit in zip(left_hash, right_hash) if left_bit != right_bit) / max(len(left_hash), 1)
    )
    left_color = list(left["color_profile"])
    right_color = list(right["color_profile"])
    color_similarity = 1.0 - (
        sum(abs(left_value - right_value) for left_value, right_value in zip(left_color, right_color)) / max(len(left_color), 1)
    )
    texture_similarity = 1.0 - min(1.0, abs(float(left["texture_score_center"]) - float(right["texture_score_center"])))
    return (hash_similarity * 0.55) + (color_similarity * 0.35) + (texture_similarity * 0.10)


def _detect_primary_color_presence(image_path: str, primary_color: str) -> bool | None:
    color_key = str(primary_color or "").strip().lower()
    if not color_key:
        return None
    color_family = _resolve_color_family(color_key)
    if color_family is None:
        return None
    with Image.open(image_path) as payload:
        sample = payload.convert("RGB").resize((96, 96))
        matched_pixels = 0
        total_pixels = sample.width * sample.height
        pixel_access = sample.load()
        for y in range(sample.height):
            for x in range(sample.width):
                red, green, blue = pixel_access[x, y]
                hue, saturation, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
                if _pixel_matches_color_family(color_family, hue, saturation, value):
                    matched_pixels += 1
    return (matched_pixels / max(total_pixels, 1)) >= 0.06


def _resolve_color_family(color_key: str) -> str | None:
    if any(token in color_key for token in ("red", "crimson", "burgundy", "ruby", "scarlet", "绾", "红")):
        return "red"
    if any(token in color_key for token in ("green", "emerald", "olive", "jade", "绿", "缁")):
        return "green"
    if any(token in color_key for token in ("gold", "amber", "ochre", "golden", "金")):
        return "gold"
    if any(token in color_key for token in ("black", "charcoal", "墨", "黑")):
        return "black"
    if any(token in color_key for token in ("white", "ivory", "cream", "白", "米白")):
        return "white"
    if any(token in color_key for token in ("blue", "navy", "azure", "蓝")):
        return "blue"
    return None


def _pixel_matches_color_family(color_family: str, hue: float, saturation: float, value: float) -> bool:
    if color_family == "red":
        return (hue <= 0.05 or hue >= 0.95) and saturation >= 0.32 and value >= 0.18
    if color_family == "green":
        return 0.20 <= hue <= 0.45 and saturation >= 0.22 and value >= 0.18
    if color_family == "gold":
        return 0.10 <= hue <= 0.18 and saturation >= 0.25 and value >= 0.35
    if color_family == "blue":
        return 0.52 <= hue <= 0.68 and saturation >= 0.20 and value >= 0.18
    if color_family == "black":
        return value <= 0.22
    if color_family == "white":
        return value >= 0.78 and saturation <= 0.14
    return False


def _detect_center_subject_signal(image_path: str) -> bool:
    with Image.open(image_path) as payload:
        image = payload.convert("RGB")
        center_box = (
            int(image.width * 0.3),
            int(image.height * 0.2),
            int(image.width * 0.7),
            int(image.height * 0.8),
        )
        center_region = image.crop(center_box)
        full_stat = ImageStat.Stat(image)
        center_stat = ImageStat.Stat(center_region)
    mean_distance = sum(abs(center_stat.mean[index] - full_stat.mean[index]) for index in range(3)) / 3.0
    texture_signal = sum(center_stat.stddev) / 3.0
    return mean_distance >= 8.0 or texture_signal >= 18.0


def _build_shot_type_evidence_text(*, shot: ShotSpec, shot_prompt_spec) -> str:
    values = [
        shot.shot_type,
        shot.goal,
        shot.focus,
        shot.scene_direction,
        shot.composition_direction,
        shot.composition_hint,
        " ".join(shot.required_subjects or []),
        " ".join(shot.optional_props or []),
    ]
    if shot_prompt_spec is not None:
        values.extend(
            [
                shot_prompt_spec.goal,
                shot_prompt_spec.subject_prompt,
                shot_prompt_spec.package_appearance_prompt,
                shot_prompt_spec.composition_prompt,
                shot_prompt_spec.background_prompt,
                shot_prompt_spec.lighting_prompt,
                shot_prompt_spec.style_prompt,
            ]
        )
    return _normalize_text(" ".join(filter(None, values))).lower()


def _evaluate_shot_type_rules(*, shot_type: str, combined_text: str, shot_prompt_spec) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    required_tokens: list[str]
    if shot_type == "hero_brand":
        required_tokens = ["package", "hero", "brand"]
        if not any(token in combined_text for token in ("package", "gift box", "box", "brand", "hero")):
            warnings.append("hero_brand_missing_package_hero_anchor")
    elif shot_type == "carry_action":
        required_tokens = ["carry", "hand", "gift"]
        if not any(token in combined_text for token in ("carry", "hand", "handoff", "gift")):
            warnings.append("carry_action_missing_hand_or_carry_anchor")
        allow_human = bool(getattr(getattr(shot_prompt_spec, "render_constraints", None), "allow_human_presence", False))
        allow_hand_only = bool(getattr(getattr(shot_prompt_spec, "render_constraints", None), "allow_hand_only", False))
        if shot_prompt_spec is not None and not (allow_hand_only or allow_human):
            warnings.append("carry_action_render_constraints_missing_hand_signal")
    elif shot_type == "open_box_structure":
        required_tokens = ["open", "structure", "inner"]
        if not any(token in combined_text for token in ("open", "opened", "structure", "inner", "tray", "layout")):
            warnings.append("open_box_structure_missing_open_or_structure_anchor")
    elif shot_type == "dry_leaf_detail":
        required_tokens = ["leaf", "detail", "texture"]
        if not any(token in combined_text for token in ("dry leaf", "tea leaves", "leaf", "texture", "detail", "raw")):
            warnings.append("dry_leaf_detail_missing_leaf_anchor")
    elif shot_type == "tea_soup_experience":
        required_tokens = ["tea soup", "cup", "brewed"]
        if not any(token in combined_text for token in ("tea soup", "brewed", "teacup", "cup", "gaiwan", "vessel")):
            warnings.append("tea_soup_experience_missing_brewed_tea_anchor")
    elif shot_type == "label_or_material_detail":
        required_tokens = ["label", "material", "detail"]
        if not any(token in combined_text for token in ("label", "material", "foil", "texture", "lid", "craft", "detail")):
            warnings.append("label_or_material_detail_missing_package_craft_anchor")
    elif shot_type == "package_with_leaf_hint":
        required_tokens = ["package", "leaf hint", "tea"]
        if not any(token in combined_text for token in ("package", "tin", "pouch", "leaf", "tea", "hint")):
            warnings.append("package_with_leaf_hint_missing_package_or_leaf_anchor")
    elif shot_type == "package_in_brewing_context":
        required_tokens = ["package", "brewing context", "props"]
        if not any(token in combined_text for token in ("package", "tin", "pouch", "brewing", "cup", "kettle", "context")):
            warnings.append("package_in_brewing_context_missing_brewing_anchor")
    else:
        required_tokens = [shot_type]
    return required_tokens, warnings
