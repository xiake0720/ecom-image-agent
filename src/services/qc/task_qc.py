from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from src.domain.copy_plan import CopyItem
from src.domain.generation_result import GeneratedImage
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.domain.qc_report import QCCheck
from src.domain.shot_plan import ShotSpec


def build_file_exists_check(*, shot_id: str, path: Path, check_name: str) -> QCCheck:
    return QCCheck(
        shot_id=shot_id,
        check_name=check_name,
        passed=path.exists(),
        details=str(path),
    )


def build_dir_exists_check(*, shot_id: str, path: Path, check_name: str) -> QCCheck:
    return QCCheck(
        shot_id=shot_id,
        check_name=check_name,
        passed=path.exists() and path.is_dir(),
        details=str(path),
    )


def build_task_output_dimension_check(image: GeneratedImage, *, expected_size: str) -> QCCheck:
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


def build_product_consistency_risk_check(
    *,
    shot_id: str,
    expected_generation_mode: str,
    actual_generation_mode: str,
    reference_asset_ids: list[str],
    prompt_generation_mode: str,
) -> QCCheck:
    warnings: list[str] = []
    if expected_generation_mode == "image_edit" and not reference_asset_ids:
        warnings.append("image_edit_expected_but_reference_assets_missing")
    if actual_generation_mode == "image_edit" and not reference_asset_ids:
        warnings.append("image_edit_actual_but_reference_assets_missing")
    if actual_generation_mode != expected_generation_mode:
        warnings.append(f"expected_{expected_generation_mode}_but_actual_{actual_generation_mode}")
    if prompt_generation_mode != expected_generation_mode:
        warnings.append(f"prompt_generation_mode_{prompt_generation_mode}_mismatch")
    status = "warning" if warnings else "passed"
    details = (
        f"expected_generation_mode={expected_generation_mode},actual_generation_mode={actual_generation_mode},"
        f"prompt_generation_mode={prompt_generation_mode},reference_asset_ids={reference_asset_ids},"
        f"warnings={warnings or ['none']}"
    )
    return QCCheck(
        shot_id=shot_id,
        check_name="product_consistency_risk",
        passed=status == "passed",
        status=status,
        details=details,
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


def _estimate_subject_focus_rect(layout_item: LayoutItem, shot: ShotSpec | None) -> tuple[int, int, int, int]:
    width = int(layout_item.canvas_width * 0.38)
    height = int(layout_item.canvas_height * 0.5)
    center_x = layout_item.canvas_width * 0.5
    center_y = layout_item.canvas_height * 0.54
    composition = _normalize_text(" ".join(filter(None, [getattr(shot, "composition_hint", ""), getattr(shot, "composition_direction", "")])))
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
