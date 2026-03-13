from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.domain.copy_plan import CopyItem, CopyPlan
from src.domain.shot_plan import ShotSpec


@dataclass(frozen=True)
class CopyPlanMergeResult:
    plan: CopyPlan
    original_count: int
    fallback_added_count: int
    missing_shot_ids: list[str]
    unexpected_shot_ids: list[str]
    duplicate_shot_ids: list[str]


def build_default_copy_item_for_shot(shot: ShotSpec) -> CopyItem:
    return CopyItem(
        shot_id=shot.shot_id,
        title=_build_default_title(shot),
        subtitle="",
        bullets=[],
        cta=None,
    )


def merge_copy_plan_with_shots(copy_plan: CopyPlan, shots: Iterable[ShotSpec]) -> CopyPlanMergeResult:
    shot_list = list(shots)
    expected_shot_ids = [shot.shot_id for shot in shot_list]
    expected_shot_id_set = set(expected_shot_ids)

    original_items = list(copy_plan.items)
    unique_items_by_shot_id: dict[str, CopyItem] = {}
    unexpected_shot_ids: list[str] = []
    duplicate_shot_ids: list[str] = []

    for item in original_items:
        normalized_shot_id = str(item.shot_id or "").strip()
        if not normalized_shot_id or normalized_shot_id not in expected_shot_id_set:
            unexpected_shot_ids.append(item.shot_id)
            continue
        if normalized_shot_id in unique_items_by_shot_id:
            duplicate_shot_ids.append(normalized_shot_id)
            continue
        unique_items_by_shot_id[normalized_shot_id] = item

    merged_items: list[CopyItem] = []
    missing_shot_ids: list[str] = []
    for shot in shot_list:
        item = unique_items_by_shot_id.get(shot.shot_id)
        if item is None:
            missing_shot_ids.append(shot.shot_id)
            item = build_default_copy_item_for_shot(shot)
        merged_items.append(item)

    return CopyPlanMergeResult(
        plan=CopyPlan(items=merged_items),
        original_count=len(original_items),
        fallback_added_count=len(missing_shot_ids),
        missing_shot_ids=missing_shot_ids,
        unexpected_shot_ids=unexpected_shot_ids,
        duplicate_shot_ids=duplicate_shot_ids,
    )


def _build_default_title(shot: ShotSpec) -> str:
    primary = _first_non_empty(
        shot.goal,
        shot.focus,
        shot.title,
        shot.shot_type.replace("_", " ").strip(),
        shot.purpose,
        shot.copy_goal,
    )
    normalized = " ".join(primary.split())
    if not normalized:
        return "商品展示"
    return normalized[:24]


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""
