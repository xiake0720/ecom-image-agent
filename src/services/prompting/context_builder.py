from __future__ import annotations

from typing import Any

from src.services.prompting.policy_loader import (
    describe_policy_source,
    load_category_policy,
    load_platform_policy,
    load_shot_type_policy,
)


FALLBACK_CATEGORY_POLICIES: dict[str, dict[str, Any]] = {
    "tea": {
        "core_shot_types": ["hero", "dry_leaf_detail", "tea_soup", "brewed_leaf_detail"],
        "optional_shot_types": [
            "packaging_display",
            "gift_scene",
            "tea_table_scene",
            "origin_scene",
            "single_can_display",
            "multi_can_display",
        ],
    },
    "other": {
        "core_shot_types": ["hero", "packaging_display", "detail_closeup"],
        "optional_shot_types": ["lifestyle_scene", "material_detail", "usage_scene"],
    },
}


def infer_category_family(product_analysis) -> str:
    normalized = " ".join(
        filter(
            None,
            [
                product_analysis.category,
                product_analysis.subcategory,
                product_analysis.product_type,
                product_analysis.product_form,
                product_analysis.packaging_structure.primary_container,
            ],
        )
    ).lower()
    family_rules = [
        ("tea", ["tea", "茶", "乌龙", "红茶", "绿茶", "白茶", "普洱", "茶叶", "tea_can"]),
        ("apparel", ["apparel", "clothing", "fashion", "shirt", "pants", "dress", "jacket", "服", "衣", "裤"]),
        ("bag", ["bag", "backpack", "tote", "wallet", "handbag", "包", "背包", "手袋"]),
        ("beauty", ["beauty", "skincare", "serum", "cream", "mask", "lotion", "美妆", "护肤"]),
        ("food", ["food", "snack", "cookie", "biscuit", "candy", "零食", "食品", "糕点"]),
    ]
    for family, keywords in family_rules:
        if any(keyword in normalized for keyword in keywords):
            return family
    return "other"


def build_plan_shots_context(*, task, product_analysis) -> dict[str, Any]:
    category_family = infer_category_family(product_analysis)
    category_policy = _resolve_category_policy(category_family)
    platform_policy = load_platform_policy(task.platform)
    style_anchor_summary = build_style_anchor_summary(
        product_analysis=product_analysis,
        platform=task.platform,
        category_policy=category_policy,
        platform_policy=platform_policy,
    )
    return {
        "category_family": category_family,
        "required_shot_count": task.shot_count,
        "group_style_anchor_summary": style_anchor_summary,
        "category_policy": {
            "display_name": category_policy.get("display_name", category_family),
            "core_shot_types": category_policy.get("core_shot_types", []),
            "optional_shot_types": category_policy.get("optional_shot_types", []),
            "scene_prop_boundaries": category_policy.get("scene_prop_boundaries", {}),
            "avoid_style_directions": category_policy.get("avoid_style_directions", []),
            "recommended_background_palettes": category_policy.get("recommended_background_palettes", []),
            "recommended_lighting_styles": category_policy.get("recommended_lighting_styles", []),
        },
        "platform_policy": {
            "platform": platform_policy.get("platform", str(task.platform).lower()),
            "aesthetic_direction": platform_policy.get("aesthetic_direction"),
            "commercial_focus": platform_policy.get("commercial_focus", []),
            "avoid": platform_policy.get("avoid", []),
        },
        "planning_rules": [
            "先满足核心图型，再从扩展图型中补足张数",
            "所有 shots 必须受同一组背景色系、光线风格、道具家族和平台审美方向约束",
            "允许适度变化，但禁止引入与类目无关、喧宾夺主的场景元素",
            "场景必须服务商品主体与后续文案留白，不得为了丰富而失控发散",
        ],
        "policy_sources": {
            "category": describe_policy_source("categories", category_family)
            if category_policy.get("enabled", False)
            else "fallback",
            "platform": describe_policy_source("platforms", task.platform),
        },
    }


def build_build_prompts_context(*, task, product_analysis, shot, copy_item, layout_item) -> dict[str, Any]:
    category_family = infer_category_family(product_analysis)
    category_policy = _resolve_category_policy(category_family)
    platform_policy = load_platform_policy(task.platform)
    shot_type_policy = load_shot_type_policy(shot.shot_type)
    return {
        "category_family": category_family,
        "category_policy": {
            "core_shot_types": category_policy.get("core_shot_types", []),
            "optional_shot_types": category_policy.get("optional_shot_types", []),
            "scene_prop_boundaries": category_policy.get("scene_prop_boundaries", {}),
            "avoid_style_directions": category_policy.get("avoid_style_directions", []),
            "recommended_background_palettes": category_policy.get("recommended_background_palettes", []),
            "recommended_lighting_styles": category_policy.get("recommended_lighting_styles", []),
        },
        "platform_policy": {
            "platform": platform_policy.get("platform", str(task.platform).lower()),
            "aesthetic_direction": platform_policy.get("aesthetic_direction"),
            "commercial_focus": platform_policy.get("commercial_focus", []),
            "avoid": platform_policy.get("avoid", []),
        },
        "shot_type_policy": {
            "shot_type": shot_type_policy.get("shot_type", shot.shot_type),
            "intent": shot_type_policy.get("intent"),
            "composition_defaults": shot_type_policy.get("composition_defaults", []),
            "prop_guidance": shot_type_policy.get("prop_guidance", []),
            "text_space_guidance": shot_type_policy.get("text_space_guidance"),
        },
        "current_layout_text_space_hint": infer_text_space_hint(layout_item),
        "style_anchor_summary": build_style_anchor_summary(
            product_analysis=product_analysis,
            platform=task.platform,
            category_policy=category_policy,
            platform_policy=platform_policy,
        ),
        "policy_sources": {
            "category": describe_policy_source("categories", category_family)
            if category_policy.get("enabled", False)
            else "fallback",
            "platform": describe_policy_source("platforms", task.platform),
            "shot_type": describe_policy_source("shot_types", shot.shot_type)
            if shot_type_policy.get("enabled", True)
            else "fallback",
        },
        "task": task,
        "product_analysis": product_analysis,
        "current_shot": shot,
        "current_copy": copy_item,
        "current_layout": layout_item,
    }


def collect_prompt_policy_signature(*, task, product_analysis, shots) -> dict[str, Any]:
    category_family = infer_category_family(product_analysis)
    return {
        "category_family": category_family,
        "category_policy": _resolve_category_policy(category_family),
        "platform_policy": load_platform_policy(task.platform),
        "shot_type_policies": [load_shot_type_policy(shot.shot_type) for shot in shots],
    }


def build_style_anchor_summary(*, product_analysis, platform: str, category_policy: dict[str, Any], platform_policy: dict[str, Any]) -> str:
    colors = category_policy.get("recommended_background_palettes") or product_analysis.visual_identity.dominant_colors[:3]
    lights = category_policy.get("recommended_lighting_styles") or product_analysis.visual_constraints.recommended_style_direction[:2]
    avoid = category_policy.get("avoid_style_directions") or product_analysis.visual_constraints.avoid[:2]
    colors_text = "/".join(colors[:3]) if isinstance(colors, list) else str(colors)
    lights_text = "、".join(lights[:2]) if isinstance(lights, list) else str(lights)
    avoid_text = "、".join(avoid[:2]) if isinstance(avoid, list) else str(avoid)
    return (
        f"背景色系围绕{colors_text}展开，"
        f"光线风格以{lights_text}为主，"
        f"平台审美方向偏{platform_policy.get('aesthetic_direction') or platform}，"
        f"优先避免={avoid_text}"
    )


def infer_text_space_hint(layout_item) -> str:
    text_safe_zone = getattr(layout_item, "text_safe_zone", "")
    if text_safe_zone:
        return str(text_safe_zone)
    if not getattr(layout_item, "blocks", None):
        return "top_right"
    title_block = layout_item.blocks[0]
    horizontal = "left" if title_block.x <= layout_item.canvas_width // 2 else "right"
    vertical = "top" if title_block.y <= layout_item.canvas_height * 0.33 else "bottom"
    if layout_item.canvas_height * 0.33 < title_block.y < layout_item.canvas_height * 0.66:
        return f"{horizontal}_center"
    return f"{vertical}_{horizontal}"


def _resolve_category_policy(category_family: str) -> dict[str, Any]:
    policy = load_category_policy(category_family)
    if policy.get("enabled", False):
        return policy
    fallback = FALLBACK_CATEGORY_POLICIES.get(category_family) or FALLBACK_CATEGORY_POLICIES["other"]
    return {
        "category": category_family,
        "display_name": category_family,
        "enabled": False,
        **fallback,
    }
