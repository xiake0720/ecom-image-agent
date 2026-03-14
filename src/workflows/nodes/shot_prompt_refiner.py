"""单张结构化 spec 精修节点。

文件位置：
- `src/workflows/nodes/shot_prompt_refiner.py`

核心职责：
- 基于 `product_analysis + style_architecture + shot_plan + layout_plan`
  输出 `shot_prompt_specs.json`
- 这是“三层结构化视觉导演架构”的第二层：负责把单张图的执行说明拆成可消费的结构化 spec

节点前后关系：
- 上游节点：`generate_layout`
- 下游节点：`build_prompts`
"""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.shot_prompt_specs import (
    CopyIntentSpec,
    LayoutConstraintSpec,
    ProductLockSpec,
    RenderConstraintSpec,
    ShotPromptSpec,
    ShotPromptSpecPlan,
)
from src.domain.shot_plan import ShotSpec
from src.services.assets.reference_selector import select_reference_bundle
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

logger = logging.getLogger(__name__)


def shot_prompt_refiner(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成每张图的结构化 prompt spec。

    调用链位置：
    - `generate_layout` 之后调用
    - 输出给 `build_prompts` 作为兼容旧 prompt plan 的上游结构化输入

    关键副作用：
    - 落盘 `shot_prompt_specs.json`
    - 记录每个 shot 的结构化层是否完整，便于后续定位是 style、layout 还是单张 spec 出了问题
    """
    task = state["task"]
    generation_context = _resolve_target_generation_context(state, deps)
    logs = [
        *state.get("logs", []),
        (
            "[shot_prompt_refiner] start "
            f"generation_mode={generation_context['generation_mode']} "
            f"reference_asset_ids={generation_context['reference_asset_ids']}"
        ),
        *format_connected_contract_logs(state, node_name="shot_prompt_refiner"),
    ]
    provider_name, provider_model_id = planning_provider_identity(deps)
    cache_key, cache_context = build_node_cache_key(
        node_name="shot_prompt_refiner",
        state=state,
        deps=deps,
        prompt_filename="shot_prompt_refiner.md" if deps.text_provider_mode == "real" else None,
        prompt_version="structured-shot-prompt-specs-v2" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "style_architecture_hash": hash_state_payload(state["style_architecture"]),
            "shot_plan_hash": hash_state_payload(state["shot_plan"]),
            "layout_plan_hash": hash_state_payload(state["layout_plan"]),
            "generation_context": generation_context,
        },
    )
    if should_use_cache(state):
        cached = deps.storage.load_cached_json_artifact("shot_prompt_refiner", cache_key, ShotPromptSpecPlan)
        if cached is not None:
            deps.storage.save_json_artifact(task.task_id, "shot_prompt_specs.json", cached)
            logs.extend(
                [
                    f"[cache] node=shot_prompt_refiner status=hit key={cache_key}",
                    f"[shot_prompt_refiner] generation_mode_summary={generation_context['generation_mode']}",
                    "[shot_prompt_refiner] saved shot_prompt_specs.json from cache",
                ]
            )
            logs.extend(_build_spec_debug_logs(cached))
            logs.extend(
                format_connected_contract_logs(
                    {**state, "shot_prompt_specs": cached},
                    node_name="shot_prompt_refiner",
                )
            )
            return {"shot_prompt_specs": cached, "logs": logs}
        logs.extend(
            [
                f"[cache] node=shot_prompt_refiner status=miss key={cache_key}",
                f"[shot_prompt_refiner] generation_mode_summary={generation_context['generation_mode']}",
            ]
        )
    elif is_force_rerun(state):
        logs.extend(
            [
                "[cache] node=shot_prompt_refiner status=ignored key=-",
                f"[shot_prompt_refiner] generation_mode_summary={generation_context['generation_mode']}",
            ]
        )

    if deps.text_provider_mode == "real":
        plan = _build_real_spec_plan(state, deps, generation_context)
    else:
        plan = _build_mock_spec_plan(state, generation_context)

    deps.storage.save_json_artifact(task.task_id, "shot_prompt_specs.json", plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("shot_prompt_refiner", cache_key, plan, metadata=cache_context)
    logs.extend(
        [
            f"[shot_prompt_refiner] shot_prompt_specs_generated=true count={len(plan.specs)}",
            f"[shot_prompt_refiner] generation_mode_summary={generation_context['generation_mode']}",
            f"[shot_prompt_refiner] reference_asset_ids={generation_context['reference_asset_ids']}",
            "[shot_prompt_refiner] saved shot_prompt_specs.json",
        ]
    )
    logs.extend(_build_spec_debug_logs(plan))
    logs.extend(
        format_connected_contract_logs(
            {**state, "shot_prompt_specs": plan},
            node_name="shot_prompt_refiner",
        )
    )
    return {"shot_prompt_specs": plan, "logs": logs}


def _build_real_spec_plan(state: WorkflowState, deps: WorkflowDependencies, generation_context: dict[str, object]) -> ShotPromptSpecPlan:
    """real 模式下调用规划 provider 生成结构化 spec，并用程序规则做兜底合并。"""
    task = state["task"]
    prompt = (
        "You are the shot prompt refiner for a fixed five-shot tea product workflow.\n"
        "Output one ShotPromptSpecPlan JSON object only.\n"
        "Each shot must contain structured product_lock, layout_constraints, render_constraints, and copy_intent objects.\n"
        "Each shot must contain all eight prompt layers.\n"
        "You must inherit unified style rules from style_architecture, respect product lock from product_analysis, and align text safe zone with shot type and layout.\n"
        f"user_preferences={dump_pretty(_build_user_preference_summary(task, state['style_architecture']))}\n\n"
        f"generation_context={dump_pretty(generation_context)}\n\n"
        f"product_analysis={dump_pretty(state['product_analysis'])}\n\n"
        f"style_architecture={dump_pretty(state['style_architecture'])}\n\n"
        f"shot_plan={dump_pretty(state['shot_plan'])}\n\n"
        f"layout_plan={dump_pretty(state['layout_plan'])}"
    )
    generated_plan = deps.planning_provider.generate_structured(
        prompt,
        ShotPromptSpecPlan,
        system_prompt=load_prompt_text("shot_prompt_refiner.md"),
    )
    return _merge_spec_plan_with_defaults(state, generated_plan, generation_context)


def _build_mock_spec_plan(state: WorkflowState, generation_context: dict[str, object]) -> ShotPromptSpecPlan:
    """本地拼装结构化 spec，保证不联网时也能完整跑通主链路。"""
    return _merge_spec_plan_with_defaults(state, None, generation_context)


def _merge_spec_plan_with_defaults(
    state: WorkflowState,
    generated_plan: ShotPromptSpecPlan | None,
    generation_context: dict[str, object],
) -> ShotPromptSpecPlan:
    """用程序规则生成强约束基础 spec，再合并模型产出的可变文字层。"""
    generated_map = {spec.shot_id: spec for spec in generated_plan.specs} if generated_plan is not None else {}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    merged_specs: list[ShotPromptSpec] = []
    for shot in state["shot_plan"].shots:
        base_spec = _build_base_spec(
            shot=shot,
            layout_item=layout_map[shot.shot_id],
            product_analysis=state["product_analysis"],
            style_architecture=state["style_architecture"],
            generation_context=generation_context,
        )
        generated_spec = generated_map.get(shot.shot_id)
        if generated_spec is None:
            merged_specs.append(base_spec)
            continue
        merged_specs.append(
            base_spec.model_copy(
                update={
                    "goal": generated_spec.goal or base_spec.goal,
                    "subject_prompt": generated_spec.subject_prompt or base_spec.subject_prompt,
                    "package_appearance_prompt": generated_spec.package_appearance_prompt or base_spec.package_appearance_prompt,
                    "composition_prompt": generated_spec.composition_prompt or base_spec.composition_prompt,
                    "background_prompt": generated_spec.background_prompt or base_spec.background_prompt,
                    "lighting_prompt": generated_spec.lighting_prompt or base_spec.lighting_prompt,
                    "style_prompt": generated_spec.style_prompt or base_spec.style_prompt,
                    "quality_prompt": generated_spec.quality_prompt or base_spec.quality_prompt,
                    "negative_prompt": _merge_unique_strings(base_spec.negative_prompt, generated_spec.negative_prompt),
                    "copy_intent": generated_spec.copy_intent or base_spec.copy_intent,
                    # 下面三组字段由程序兜底，避免模型把 product_lock / 安全区 / 渲染模式写偏。
                    "product_lock": _merge_product_lock(base_spec.product_lock, generated_spec.product_lock),
                    "layout_constraints": _merge_layout_constraints(base_spec.layout_constraints, generated_spec.layout_constraints),
                    "render_constraints": _merge_render_constraints(base_spec.render_constraints, generated_spec.render_constraints),
                }
            )
        )
    return ShotPromptSpecPlan(specs=merged_specs)


def _build_base_spec(*, shot: ShotSpec, layout_item, product_analysis, style_architecture, generation_context: dict[str, object]) -> ShotPromptSpec:
    """按固定规则生成单张图的基础 spec。"""
    preferred_zone = _resolve_preferred_text_safe_zone(shot, layout_item)
    product_lock = _build_product_lock(product_analysis)
    layout_constraints = LayoutConstraintSpec(
        preferred_text_safe_zone=preferred_zone,
        avoid_overlap_with_subject=True,
        max_text_layers=2,
        subject_placement_hint=_resolve_subject_placement_hint(shot, preferred_zone),
    )
    render_constraints = _build_render_constraints(shot, generation_context)
    saturated_background_rule = _build_background_saturation_rule(product_analysis)
    common_style_summary = " | ".join(
        [
            style_architecture.style_theme,
            *style_architecture.lens_strategy,
            *style_architecture.prop_system,
        ]
    )
    return ShotPromptSpec(
        shot_id=shot.shot_id,
        shot_type=shot.shot_type,
        goal=shot.goal or shot.title,
        product_lock=product_lock,
        subject_prompt=_build_subject_prompt(shot, product_analysis),
        package_appearance_prompt=_build_package_appearance_prompt(product_analysis),
        composition_prompt=_build_composition_prompt(shot, preferred_zone),
        background_prompt=_build_background_prompt(shot, style_architecture, saturated_background_rule),
        lighting_prompt=_build_lighting_prompt(shot, style_architecture),
        style_prompt=f"{common_style_summary}. keep the full set visually unified.",
        quality_prompt=_build_quality_prompt(shot),
        negative_prompt=_build_negative_prompt(product_analysis, style_architecture),
        layout_constraints=layout_constraints,
        render_constraints=render_constraints,
        copy_intent=_build_copy_intent(shot),
    )


def _build_subject_prompt(shot: ShotSpec, product_analysis) -> str:
    if shot.shot_type == "hero_brand":
        return (
            "Use the uploaded product as the exact hero subject. "
            "Keep the full package clearly recognizable as the primary visual center."
        )
    if shot.shot_type == "carry_action":
        return (
            "Use the uploaded product as the exact subject in a restrained carry or gifting action. "
            "Only a hand gesture may appear when needed."
        )
    if shot.shot_type == "open_box_structure":
        return (
            "Use the uploaded product package in an opened or structure-revealing state. "
            "The opening logic and internal arrangement must stay believable."
        )
    if shot.shot_type == "dry_leaf_detail":
        return (
            "Show dry tea leaf detail as the immediate visual focus while keeping the uploaded package as the brand anchor."
        )
    if shot.shot_type == "tea_soup_experience":
        return (
            "Show brewed tea experience with tea soup as the foreground focus while keeping the uploaded package as the scene anchor."
        )
    return f"Use the uploaded {product_analysis.package_type or 'product package'} as the exact subject."


def _build_package_appearance_prompt(product_analysis) -> str:
    return (
        f"Keep package type {product_analysis.package_type or '-'}, "
        f"primary color {product_analysis.primary_color or '-'}, "
        f"material {product_analysis.material or '-'}, "
        f"label structure {product_analysis.label_structure or '-'} unchanged. "
        "Do not redesign package proportions, surface graphics, or brand texts."
    )


def _build_composition_prompt(shot: ShotSpec, preferred_zone: str) -> str:
    composition_base = shot.composition_direction or shot.composition_hint or "keep the composition stable and commercial"
    if shot.shot_type == "carry_action":
        return (
            f"{composition_base} Place the text area on the opposite side of the action direction and keep the copy zone clean."
        )
    if shot.shot_type == "open_box_structure":
        return (
            f"{composition_base} Keep the structural read clean and reserve a top or upper-right copy zone."
        )
    if shot.shot_type == "dry_leaf_detail":
        return (
            f"{composition_base} Keep a clean background patch for text instead of placing text over the tea leaf texture."
        )
    if shot.shot_type == "tea_soup_experience":
        return f"{composition_base} Keep the upper area open for copy and avoid clutter behind the liquid."
    return f"{composition_base} Preferred text-safe zone: {preferred_zone}."


def _build_background_prompt(shot: ShotSpec, style_architecture, saturated_background_rule: str) -> str:
    background_base = "; ".join(style_architecture.background_strategy)
    if shot.shot_type == "dry_leaf_detail":
        return f"{background_base}. Use a calm neutral surface with an explicit clean text patch. {saturated_background_rule}"
    return f"{background_base}. {saturated_background_rule}"


def _build_lighting_prompt(shot: ShotSpec, style_architecture) -> str:
    lighting_base = "; ".join(style_architecture.lighting_strategy)
    lens_base = "; ".join(style_architecture.lens_strategy)
    return f"{lighting_base}. Keep the lens language consistent: {lens_base}. Shot type: {shot.shot_type}."


def _build_quality_prompt(shot: ShotSpec) -> str:
    if shot.shot_type == "dry_leaf_detail":
        return "high-end commercial macro detail photography, crisp texture, premium material fidelity, clean depth separation"
    if shot.shot_type == "tea_soup_experience":
        return "high-end commercial beverage photography, transparent tea soup, premium mood, clean reflections"
    return "high-end commercial e-commerce photography, premium material fidelity, stable composition, clean product edges"


def _build_negative_prompt(product_analysis, style_architecture) -> list[str]:
    return _merge_unique_strings(
        style_architecture.global_negative_rules,
        [
            "do not redesign the package structure",
            "do not redesign the label",
            "do not change package proportions",
            "do not add oversaturated background colors",
            *[f"must not change {item}" for item in product_analysis.locked_elements],
        ],
    )


def _build_product_lock(product_analysis) -> ProductLockSpec:
    must_not_change = _merge_unique_strings(
        [
            product_analysis.package_type or "",
            product_analysis.primary_color or "",
            product_analysis.label_structure or "",
        ],
        product_analysis.locked_elements,
    )
    return ProductLockSpec(
        must_preserve=_merge_unique_strings(product_analysis.locked_elements, product_analysis.visual_identity.must_preserve),
        must_preserve_texts=product_analysis.must_preserve_texts,
        editable_regions=product_analysis.editable_elements,
        must_not_change=must_not_change,
    )


def _build_render_constraints(shot: ShotSpec, generation_context: dict[str, object]) -> RenderConstraintSpec:
    generation_mode = str(generation_context["generation_mode"])
    reference_image_priority = "none"
    consistency_strength = "medium"
    if generation_mode == "image_edit":
        if shot.shot_type == "dry_leaf_detail":
            reference_image_priority = "main_packshot_plus_detail_if_available"
            consistency_strength = "medium_high"
        else:
            reference_image_priority = "main_packshot"
            consistency_strength = "high" if shot.shot_type in {"hero_brand", "carry_action"} else "medium_high"
    return RenderConstraintSpec(
        generation_mode=generation_mode,
        reference_image_priority=reference_image_priority,
        consistency_strength=consistency_strength,
        allow_human_presence=shot.shot_type == "carry_action",
        allow_hand_only=shot.shot_type == "carry_action",
    )


def _build_copy_intent(shot: ShotSpec) -> CopyIntentSpec:
    if shot.shot_type == "hero_brand":
        return CopyIntentSpec(title_role="品牌气质", subtitle_role="礼赠价值", bullet_role="optional", cta_role="none")
    if shot.shot_type == "carry_action":
        return CopyIntentSpec(title_role="手提设计", subtitle_role="送礼体面感", bullet_role="optional", cta_role="none")
    if shot.shot_type == "open_box_structure":
        return CopyIntentSpec(title_role="开盒价值", subtitle_role="结构与内装", bullet_role="optional", cta_role="none")
    if shot.shot_type == "dry_leaf_detail":
        return CopyIntentSpec(title_role="原料品质", subtitle_role="茶干细节", bullet_role="optional", cta_role="none")
    if shot.shot_type == "tea_soup_experience":
        return CopyIntentSpec(title_role="茶汤体验", subtitle_role="口感与氛围", bullet_role="optional", cta_role="none")
    return CopyIntentSpec(title_role=shot.copy_goal or shot.title, subtitle_role="", bullet_role="optional", cta_role="none")


def _resolve_target_generation_context(state: WorkflowState, deps: WorkflowDependencies) -> dict[str, object]:
    """预判这批 spec 更偏向 image_edit 还是 t2i。

    这里不直接驱动最终渲染，只是给 shot spec 写入目标生成模式，便于调试和后续 prompt 组装。
    """
    selection = select_reference_bundle(
        state.get("assets", []),
        max_images=get_settings().resolve_image_edit_max_reference_images(),
    )
    resolver = getattr(deps.image_generation_provider, "resolve_generation_context", None)
    if callable(resolver):
        context = resolver(reference_assets=selection.selected_assets)
        return {
            "generation_mode": context.generation_mode,
            "reference_asset_ids": context.reference_asset_ids,
        }
    return {
        "generation_mode": "image_edit" if selection.selected_assets else "t2i",
        "reference_asset_ids": selection.selected_asset_ids,
    }


def _build_user_preference_summary(task, style_architecture) -> dict[str, object]:
    """把用户偏好统一整理给 refiner 使用。"""
    return {
        "platform": task.platform,
        "copy_tone": task.copy_tone,
        "style_architecture_user_preferences": style_architecture.user_preferences,
    }


def _resolve_preferred_text_safe_zone(shot: ShotSpec, layout_item) -> str:
    layout_zone = getattr(layout_item, "text_safe_zone", "") or shot.preferred_text_safe_zone
    if shot.shot_type == "hero_brand":
        return layout_zone if layout_zone in {"top_left", "top_right", "top"} else "top_right"
    if shot.shot_type == "carry_action":
        return "opposite_of_action_direction"
    if shot.shot_type == "open_box_structure":
        return layout_zone if layout_zone in {"top", "top_right"} else "top_right"
    if shot.shot_type == "dry_leaf_detail":
        return "background_clean_area"
    if shot.shot_type == "tea_soup_experience":
        return "top"
    return layout_zone or "top_right"


def _resolve_subject_placement_hint(shot: ShotSpec, preferred_zone: str) -> str:
    if shot.shot_type == "hero_brand":
        return "stable hero package with clean upper-area copy zone"
    if shot.shot_type == "carry_action":
        return "subject follows the hand motion, copy stays on the opposite side"
    if shot.shot_type == "open_box_structure":
        return "opened package stays central and structural read remains clear"
    if shot.shot_type == "dry_leaf_detail":
        return "tea leaf detail foreground, package anchor background, text stays in clean background area"
    if shot.shot_type == "tea_soup_experience":
        return "tea soup foreground, package anchor background, upper area kept clear"
    return f"prefer copy zone at {preferred_zone}"


def _build_background_saturation_rule(product_analysis) -> str:
    if _is_high_saturation_product(product_analysis.primary_color):
        return "Background must stay low saturation so the product remains the only saturated visual center."
    return "Keep the background restrained and subordinate to the product."


def _is_high_saturation_product(primary_color: str) -> bool:
    color = str(primary_color or "").strip().lower()
    return any(keyword in color for keyword in ("red", "红", "gold", "金", "emerald", "green", "绿"))


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    """合并多个字符串列表并去重，保留原有顺序。"""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _merge_product_lock(base: ProductLockSpec, generated: ProductLockSpec) -> ProductLockSpec:
    return base.model_copy(
        update={
            "must_preserve": _merge_unique_strings(base.must_preserve, generated.must_preserve),
            "must_preserve_texts": _merge_unique_strings(base.must_preserve_texts, generated.must_preserve_texts),
            "editable_regions": _merge_unique_strings(base.editable_regions, generated.editable_regions),
            "must_not_change": _merge_unique_strings(base.must_not_change, generated.must_not_change),
        }
    )


def _merge_layout_constraints(base: LayoutConstraintSpec, generated: LayoutConstraintSpec) -> LayoutConstraintSpec:
    return base.model_copy(
        update={
            "preferred_text_safe_zone": base.preferred_text_safe_zone or generated.preferred_text_safe_zone,
            "avoid_overlap_with_subject": base.avoid_overlap_with_subject,
            "max_text_layers": min(base.max_text_layers, generated.max_text_layers or base.max_text_layers),
            "subject_placement_hint": base.subject_placement_hint or generated.subject_placement_hint,
        }
    )


def _merge_render_constraints(base: RenderConstraintSpec, generated: RenderConstraintSpec) -> RenderConstraintSpec:
    return base.model_copy(
        update={
            "generation_mode": base.generation_mode,
            "reference_image_priority": base.reference_image_priority,
            "consistency_strength": base.consistency_strength or generated.consistency_strength,
            "allow_human_presence": base.allow_human_presence,
            "allow_hand_only": base.allow_hand_only,
        }
    )


def _build_spec_debug_logs(plan: ShotPromptSpecPlan) -> list[str]:
    """输出每个 shot 的关键 spec 摘要，便于调试。"""
    logs: list[str] = []
    for spec in plan.specs:
        style_summary = spec.style_prompt[:100] + ("..." if len(spec.style_prompt) > 100 else "")
        logs.append(
            (
                "[shot_prompt_refiner] shot_spec "
                f"shot_id={spec.shot_id} "
                f"shot_type={spec.shot_type} "
                f"style_theme_summary={style_summary} "
                f"generation_mode={spec.render_constraints.generation_mode} "
                f"complete_eight_layers={str(spec.has_complete_prompt_layers()).lower()}"
            )
        )
    return logs
