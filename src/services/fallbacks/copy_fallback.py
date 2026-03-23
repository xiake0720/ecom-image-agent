<<<<<<< HEAD
=======
"""文案 fallback 规则。

文件位置：
- `src/services/fallbacks/copy_fallback.py`

核心职责：
- 当 provider 缺失文案时提供 shot-aware 的短版贴图 fallback
- 保证 fallback 文案本身也适合 1440x1440 叠字，不输出长句、bullets 堆叠或 CTA
"""

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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


<<<<<<< HEAD
def build_default_copy_item_for_shot(shot: ShotSpec) -> CopyItem:
    return CopyItem(
        shot_id=shot.shot_id,
        title=_build_default_title(shot),
        subtitle="",
=======
def build_default_copy_item_for_shot(shot: ShotSpec, *, task=None, product_analysis=None) -> CopyItem:
    """按 shot_type 生成兜底短版文案，默认不输出 bullets 和 CTA。"""
    title, subtitle = _build_default_overlay_copy(shot=shot, task=task, product_analysis=product_analysis)
    return CopyItem(
        shot_id=shot.shot_id,
        title=title,
        subtitle=subtitle,
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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


<<<<<<< HEAD
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
=======
def _build_default_overlay_copy(*, shot: ShotSpec, task=None, product_analysis=None) -> tuple[str, str]:
    """根据 shot_type 输出更像电商贴图的标题和副标题。"""
    product_phrase = _resolve_product_phrase(task=task, product_analysis=product_analysis)
    material_phrase = _resolve_material_phrase(product_analysis=product_analysis)
    rules = {
        "hero_brand": (
            product_phrase or "好茶礼赠之选",
            _hero_subtitle(task=task, product_analysis=product_analysis),
        ),
        "package_detail": ("细节近看更显质感", material_phrase or "结构利落更显精致"),
        "label_or_material_detail": ("材质细节近看更显质感", material_phrase or "纹理清楚包装更显精致"),
        "dry_leaf_detail": ("条索紧结原叶匀整", "干茶纹理清晰可见"),
        "tea_soup_experience": ("汤色清透回甘舒展", "入口鲜爽饮感更顺"),
        "lifestyle_or_brewing_context": ("日常冲泡更有茶感", "茶具入景氛围更松弛"),
        "package_in_brewing_context": ("冲泡入景更显茶感", "包装在场画面更完整"),
        "package_with_leaf_hint": ("茶叶入景更显茶感", "包装清晰茶感更到位"),
        "open_box_structure": ("开盒层次一目了然", "结构清晰取放更顺手"),
        "carry_action": ("提拿轻松送礼体面", "出门携带体面不费力"),
    }
    return rules.get(shot.shot_type, (product_phrase or "商品卖点直达", "短句贴图更易阅读"))


def _resolve_product_phrase(*, task=None, product_analysis=None) -> str:
    """优先用真实商品名，否则回退到可确认的品类短语。"""
    candidates = [
        getattr(task, "product_name", ""),
        getattr(product_analysis, "subcategory", ""),
        getattr(product_analysis, "product_type", ""),
        getattr(product_analysis, "package_type", ""),
    ]
    for candidate in candidates:
        text = str(candidate or "").strip().replace(" ", "")
        if 4 <= len(text) <= 18:
            return text
    return "好茶上新"


def _resolve_material_phrase(*, product_analysis=None) -> str:
    """从商品分析里提炼一个可确认的材质或结构短语。"""
    if product_analysis is None:
        return ""
    material = str(getattr(product_analysis, "material", "") or "").strip()
    package_type = str(getattr(product_analysis, "package_type", "") or "").strip()
    if material and len(material) <= 10:
        return f"{material}细节更显质感"
    if package_type and len(package_type) <= 10:
        return f"{package_type}结构更显利落"
    return ""


def _hero_subtitle(*, task=None, product_analysis=None) -> str:
    """hero 图副标题根据包装和语气做保守表达。"""
    task_tone = str(getattr(task, "copy_tone", "") or "")
    package_type = str(getattr(product_analysis, "package_type", "") or "")
    if "礼" in task_tone or "gift" in package_type.lower():
        return "茶香清雅礼赠体面"
    if "tin" in package_type.lower() or "can" in package_type.lower() or "罐" in package_type:
        return "罐装锁鲜茶香更稳"
    if "pouch" in package_type.lower() or "袋" in package_type:
        return "轻装便携日常好泡"
    return "茶香清雅日常好泡"
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
