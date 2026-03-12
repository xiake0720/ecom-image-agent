"""图组规划节点。

当前节点负责输出 `ShotPlan`，并保持 shot_id、张数和落盘结构稳定。
"""

from __future__ import annotations

import logging

from src.domain.shot_plan import ShotPlan
from src.services.planning.shot_planner import build_mock_shot_plan
from src.workflows.nodes.prompt_utils import describe_prompt_source, dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def plan_shots(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """根据商品分析结果生成图组规划。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[plan_shots] 开始图组规划，模式={deps.text_provider_mode}，目标张数={task.shot_count}。"]
    category_family = _infer_category_family(state["product_analysis"])
    style_anchor_summary = _build_style_anchor_summary(state["product_analysis"], task.platform)
    template_name = "plan_shots.md"
    template_source = describe_prompt_source(template_name)
    logger.info(
        "plan_shots 当前识别类目族群=%s，整组风格锚点摘要=%s，模板来源=%s",
        category_family,
        style_anchor_summary,
        template_source,
    )
    logs.extend(
        [
            f"[plan_shots] 当前识别到的类目族群：{category_family}。",
            f"[plan_shots] 当前选择的整组风格锚点摘要：{style_anchor_summary}。",
            f"[plan_shots] 当前使用的模板来源文件：{template_source}。",
        ]
    )
    if deps.text_provider_mode == "real":
        model_label = deps.planning_model_selection.label if deps.planning_model_selection else "-"
        model_id = deps.planning_model_selection.model_id if deps.planning_model_selection else "-"
        logger.info(
            "plan_shots 当前走结构化规划 real 模式，provider=%s，模型=%s，model_id=%s",
            deps.planning_provider_name or "unknown",
            model_label,
            model_id,
        )
        prompt = (
            "请基于结构化商品分析结果规划当前任务的电商图组。\n"
            "先在内部确定类目族群、整组统一风格锚点、核心图型与扩展图型，再只输出符合 ShotPlan schema 的 JSON。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"商品分析:\n{dump_pretty(state['product_analysis'])}\n\n"
            "规划上下文:\n"
            f"{dump_pretty(_build_plan_shots_context(category_family, style_anchor_summary, task.shot_count))}"
        )
        shot_plan = deps.planning_provider.generate_structured(
            prompt,
            ShotPlan,
            system_prompt=load_prompt_text(template_name),
        )
    else:
        shot_plan = build_mock_shot_plan(state["product_analysis"], task.shot_count)
    deps.storage.save_json_artifact(task.task_id, "shot_plan.json", shot_plan)
    shot_ids = ", ".join(shot.shot_id for shot in shot_plan.shots)
    core_count, extension_count = _count_core_and_extension_shots(shot_plan, category_family)
    logger.info("图组规划完成，张数=%s，shot_id=%s", len(shot_plan.shots), shot_ids or "-")
    logs.extend(
        [
            f"[plan_shots] 图组规划完成，数量={len(shot_plan.shots)}，shot_ids={shot_ids or '-'}。",
            f"[plan_shots] 当前生成的核心图型数量={core_count}，扩展图型数量={extension_count}。",
            (
                "[plan_shots] 当前实际规划模型="
                f"{deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}。"
            ),
            "[plan_shots] 已写入 shot_plan.json。",
        ]
    )
    return {"shot_plan": shot_plan, "logs": logs}


def _build_plan_shots_context(category_family: str, style_anchor_summary: str, shot_count: int) -> dict:
    """构造图组规划的最小上下文，交由模板主导约束。"""
    core_types, extension_types = _get_family_shot_type_policy(category_family)
    return {
        "category_family": category_family,
        "required_shot_count": shot_count,
        "group_style_anchor_summary": style_anchor_summary,
        "core_shot_types": core_types,
        "extension_shot_types": extension_types,
        "planning_rules": [
            "先满足核心图型，再从扩展图型中补足张数",
            "所有 shots 必须受同一组背景色系、光线风格、道具家族和平台审美方向约束",
            "允许适度变化，但禁止引入与类目无关、喧宾夺主的场景元素",
            "场景必须服务商品主体与后续文案留白，不得为了丰富而失控发散",
        ],
    }


def _infer_category_family(product_analysis) -> str:
    """根据商品分析结果识别类目族群。"""
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
        ("beverage", ["beverage", "drink", "juice", "soda", "coffee", "饮料", "饮品", "咖啡"]),
        ("packaged_food", ["food", "snack", "cookie", "biscuit", "candy", "零食", "食品", "糕点"]),
        ("apparel", ["apparel", "clothing", "fashion", "shirt", "pants", "dress", "jacket", "服", "衣", "裙"]),
        ("bag", ["bag", "backpack", "tote", "wallet", "handbag", "包", "背包", "手袋"]),
        ("beauty_skincare", ["beauty", "skincare", "serum", "cream", "mask", "lotion", "美妆", "护肤"]),
        ("home_lifestyle", ["home", "lifestyle", "furniture", "kitchen", "decor", "家居", "生活"]),
        ("electronics_accessory", ["electronics", "accessory", "charger", "cable", "headphone", "数码", "电子", "配件"]),
        ("gift_set", ["gift", "set", "礼盒", "套装"]),
    ]
    for family, keywords in family_rules:
        if any(keyword in normalized for keyword in keywords):
            return family
    return "other"


def _build_style_anchor_summary(product_analysis, platform: str) -> str:
    """根据商品分析构造整组统一风格锚点摘要。"""
    colors = "/".join(product_analysis.visual_identity.dominant_colors[:3]) or "以商品主色延展"
    lighting = product_analysis.visual_constraints.recommended_style_direction[:2]
    lighting_text = "、".join(lighting) if lighting else "干净自然的商业棚拍光线"
    prop_guard = "、".join(product_analysis.visual_constraints.avoid[:2]) or "避免喧宾夺主道具"
    style_words = "、".join(product_analysis.visual_style_keywords[:2]) or "统一高级电商质感"
    return (
        f"背景色系统一围绕{colors}展开，"
        f"光线与摄影气质以{lighting_text}为主，"
        f"道具家族保持克制且服务主体，"
        f"平台审美方向偏{platform}电商商业图，"
        f"整体风格关键词={style_words}，"
        f"优先避免={prop_guard}"
    )


def _get_family_shot_type_policy(category_family: str) -> tuple[list[str], list[str]]:
    """返回类目族群对应的核心与扩展图型。"""
    policies = {
        "tea": (
            ["hero", "dry_leaf_detail", "tea_soup", "brewed_leaf_detail"],
            ["packaging_display", "gift_scene", "tea_table_scene", "origin_scene", "single_can_display", "multi_can_display"],
        ),
        "beverage": (
            ["hero", "packaging_display", "ingredient_detail", "usage_scene"],
            ["pour_scene", "family_display", "gift_scene", "ice_refresh_scene"],
        ),
        "packaged_food": (
            ["hero", "packaging_display", "texture_closeup", "ingredient_detail"],
            ["serving_scene", "gift_scene", "multi_pack_display", "snack_moment_scene"],
        ),
        "apparel": (
            ["hero", "wearing_display", "front_back_display", "material_detail", "construction_detail"],
            ["lifestyle_scene", "fit_display", "styling_scene", "zipper_detail", "collar_detail", "button_detail"],
        ),
        "bag": (
            ["hero", "front_side_back_display", "material_detail", "hardware_detail", "handle_or_strap_detail"],
            ["capacity_demo", "on_body_display", "lifestyle_scene"],
        ),
        "beauty_skincare": (
            ["hero", "packaging_display", "texture_closeup", "ingredient_detail"],
            ["bathroom_scene", "usage_scene", "gift_set_display"],
        ),
        "home_lifestyle": (
            ["hero", "material_detail", "function_demo", "lifestyle_scene"],
            ["space_scene", "packaging_display", "closeup_detail"],
        ),
        "electronics_accessory": (
            ["hero", "function_demo", "material_detail", "interface_detail"],
            ["usage_scene", "packaging_display", "compatibility_display"],
        ),
        "gift_set": (
            ["hero", "gift_set_display", "packaging_display", "detail_closeup"],
            ["festival_scene", "unboxing_scene", "tabletop_scene"],
        ),
        "other": (
            ["hero", "packaging_display", "detail_closeup"],
            ["lifestyle_scene", "material_detail", "usage_scene"],
        ),
    }
    return policies.get(category_family, policies["other"])


def _count_core_and_extension_shots(shot_plan: ShotPlan, category_family: str) -> tuple[int, int]:
    """按类目图型策略统计核心 / 扩展图型数量。"""
    core_types, extension_types = _get_family_shot_type_policy(category_family)
    core_set = set(core_types)
    extension_set = set(extension_types)
    core_count = 0
    extension_count = 0
    for shot in shot_plan.shots:
        if shot.shot_type in core_set:
            core_count += 1
        elif shot.shot_type in extension_set:
            extension_count += 1
        else:
            extension_count += 1
    return core_count, extension_count
