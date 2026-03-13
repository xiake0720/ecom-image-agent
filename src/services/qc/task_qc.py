from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from src.domain.copy_plan import CopyItem
from src.domain.generation_result import GeneratedImage
from src.domain.layout_plan import LayoutBlock, LayoutItem
from src.domain.qc_report import QCCheck


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
