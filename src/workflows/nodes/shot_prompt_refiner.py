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

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ShotExecutionProfile:
    """单个 shot_type 的执行画像。

    作用：
    - 把主次主体、排他规则、构图约束和锁定等级集中在一起。
    - 避免 `subject/composition/background/lighting/render_constraints` 各自维护一套分散逻辑。
    """

    primary_subject: str
    secondary_subject: str
    differentiation_summary: str
    banned_fallback_pattern: str
    subject_rules: list[str]
    composition_rules: list[str]
    background_rules: list[str]
    lighting_rules: list[str]
    negative_rules: list[str]
    product_lock_level: str
    consistency_strength: str
    reference_image_priority: str
    editable_regions: list[str]
    editable_region_strategy: str
    allow_human_presence: bool = False
    allow_hand_only: bool = False


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
            logs.extend(_build_spec_debug_logs(cached, state["product_analysis"]))
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
    logs.extend(_build_spec_debug_logs(plan, state["product_analysis"]))
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
    profile = _build_shot_execution_profile(shot, product_analysis)
    preferred_zone = _resolve_preferred_text_safe_zone(shot, layout_item, profile)
    product_lock = _build_product_lock(product_analysis, profile)
    layout_constraints = LayoutConstraintSpec(
        preferred_text_safe_zone=preferred_zone,
        avoid_overlap_with_subject=True,
        max_text_layers=2,
        subject_placement_hint=_resolve_subject_placement_hint(shot, preferred_zone, profile),
    )
    render_constraints = _build_render_constraints(shot, generation_context, profile)
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
        subject_prompt=_build_subject_prompt(shot, product_analysis, profile),
        package_appearance_prompt=_build_package_appearance_prompt(product_analysis),
        composition_prompt=_build_composition_prompt(shot, preferred_zone, profile),
        background_prompt=_build_background_prompt(shot, style_architecture, saturated_background_rule, profile),
        lighting_prompt=_build_lighting_prompt(shot, style_architecture, profile),
        style_prompt=f"{common_style_summary}. keep the full set visually unified.",
        quality_prompt=_build_quality_prompt(shot, profile),
        negative_prompt=_build_negative_prompt(product_analysis, style_architecture, profile),
        layout_constraints=layout_constraints,
        render_constraints=render_constraints,
        copy_intent=_build_copy_intent(shot),
    )


def _build_subject_prompt(shot: ShotSpec, product_analysis, profile: ShotExecutionProfile) -> str:
    """构建主体层，明确主次主体和不得退化的执行边界。"""
    package_label = product_analysis.package_type or "product package"
    return _join_prompt_sentences(
        [
            f"Primary subject: {profile.primary_subject}",
            f"Secondary subject: {profile.secondary_subject}",
            f"Use the uploaded {package_label} as the exact brand reference",
            *profile.subject_rules,
        ]
    )


def _build_package_appearance_prompt(product_analysis) -> str:
    return (
        f"Keep package type {product_analysis.package_type or '-'}, "
        f"primary color {product_analysis.primary_color or '-'}, "
        f"material {product_analysis.material or '-'}, "
        f"label structure {product_analysis.label_structure or '-'} unchanged. "
        "Do not redesign package proportions, surface graphics, or brand texts."
    )


def _build_composition_prompt(shot: ShotSpec, preferred_zone: str, profile: ShotExecutionProfile) -> str:
    """构图层使用明确镜头执行语句，不再只做宽泛描述。"""
    composition_base = shot.composition_direction or shot.composition_hint or "keep the composition stable and commercial"
    return _join_prompt_sentences(
        [
            composition_base,
            f"Preferred text-safe zone: {preferred_zone}",
            *profile.composition_rules,
        ]
    )


def _build_background_prompt(shot: ShotSpec, style_architecture, saturated_background_rule: str, profile: ShotExecutionProfile) -> str:
    background_base = "; ".join(style_architecture.background_strategy)
    return _join_prompt_sentences(
        [
            background_base,
            saturated_background_rule,
            *profile.background_rules,
        ]
    )


def _build_lighting_prompt(shot: ShotSpec, style_architecture, profile: ShotExecutionProfile) -> str:
    lighting_base = "; ".join(style_architecture.lighting_strategy)
    lens_base = "; ".join(style_architecture.lens_strategy)
    return _join_prompt_sentences(
        [
            lighting_base,
            f"Keep the lens language consistent: {lens_base}",
            *profile.lighting_rules,
        ]
    )


def _build_quality_prompt(shot: ShotSpec, profile: ShotExecutionProfile) -> str:
    if shot.shot_type in {"dry_leaf_detail", "package_detail", "label_or_material_detail"}:
        return "high-end commercial macro detail photography, crisp texture, premium material fidelity, clean depth separation"
    if shot.shot_type in {"tea_soup_experience", "lifestyle_or_brewing_context", "package_in_brewing_context"}:
        return "high-end commercial beverage photography, transparent tea soup, premium mood, clean reflections"
    return _join_prompt_sentences(
        [
            "high-end commercial e-commerce photography",
            "premium material fidelity",
            "stable composition",
            "clean product edges",
            profile.differentiation_summary,
        ]
    )


def _build_negative_prompt(product_analysis, style_architecture, profile: ShotExecutionProfile) -> list[str]:
    return _merge_unique_strings(
        style_architecture.global_negative_rules,
        [
            "do not redesign the package structure",
            "do not redesign the label",
            "do not change package proportions",
            "do not add oversaturated background colors",
            *profile.negative_rules,
            *[f"must not change {item}" for item in product_analysis.locked_elements],
        ],
    )


def _build_product_lock(product_analysis, profile: ShotExecutionProfile) -> ProductLockSpec:
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
        editable_regions=_merge_unique_strings(product_analysis.editable_elements, profile.editable_regions),
        must_not_change=must_not_change,
    )


def _build_render_constraints(
    shot: ShotSpec,
    generation_context: dict[str, object],
    profile: ShotExecutionProfile,
) -> RenderConstraintSpec:
    """把 shot 差异化执行画像映射为 render_constraints 分层策略。"""
    generation_mode = str(generation_context["generation_mode"])
    return RenderConstraintSpec(
        generation_mode=generation_mode,
        reference_image_priority=profile.reference_image_priority if generation_mode == "image_edit" else "none",
        consistency_strength=profile.consistency_strength,
        product_lock_level=profile.product_lock_level,
        editable_region_strategy=profile.editable_region_strategy,
        allow_human_presence=profile.allow_human_presence,
        allow_hand_only=profile.allow_hand_only,
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


def _build_shot_execution_profile(shot: ShotSpec, product_analysis) -> ShotExecutionProfile:
    """按 shot_type 汇总执行画像，统一管理主次主体、排他规则和锁定强度。"""
    shot_type = str(shot.shot_type or "").strip()
    package_type = product_analysis.package_type or "product package"
    template_family = str(getattr(product_analysis, "package_template_family", "") or "").strip().lower()
    asset_mode = str(getattr(product_analysis, "asset_completeness_mode", "") or "").strip().lower()
    is_tin_can = template_family == "tea_tin_can"
    base_secondary = f"{package_type} brand anchor"

    if shot_type == "hero_brand":
        return ShotExecutionProfile(
            primary_subject=f"full {package_type} hero package",
            secondary_subject="minimal supporting surface only",
            differentiation_summary="full package hero frame, package owns the visual weight, not a detail crop or context scene",
            banned_fallback_pattern="detail crop, beverage-first scene, or prop-led lifestyle composition",
            subject_rules=[
                "Make the full package the absolute first subject and keep it fully readable",
                "Package must occupy the dominant visual weight in the frame",
                "Do not downgrade this shot into a detail crop, texture study, or scene-assist image",
            ],
            composition_rules=[
                "Use a stable hero framing with the package front or controlled 3/4 view clearly visible",
                "Keep the package large and centered or near-centered instead of pushing it deep into the background",
            ],
            background_rules=["Keep props minimal and clearly subordinate to the package hero"],
            lighting_rules=["Light for clear packaging legibility and premium silhouette separation rather than mood-only atmosphere"],
            negative_rules=[
                "must not look like a cropped detail image",
                "must not become a lifestyle scene where props outrank the package",
            ],
            product_lock_level="strong_product_lock",
            consistency_strength="high",
            reference_image_priority="main_packshot_must_dominate",
            editable_regions=["background", "surface styling", "shadow shape"],
            editable_region_strategy="background_props_only",
        )

    if shot_type == "carry_action":
        return ShotExecutionProfile(
            primary_subject=f"{package_type} in restrained carry action",
            secondary_subject="single hand gesture",
            differentiation_summary="carry-action packshot with product readability preserved",
            banned_fallback_pattern="full isolated studio hero without human interaction",
            subject_rules=[
                "Keep the package clearly readable while allowing only a restrained hand-carry or gifting action",
                "Human presence is limited to the minimum hand gesture needed to explain the action",
            ],
            composition_rules=["Place copy on the opposite side of the action direction and keep that zone clean"],
            background_rules=["Use a simple scene that supports the carry gesture instead of building a crowded lifestyle set"],
            lighting_rules=["Keep hand and package exposure balanced so the package remains visually dominant"],
            negative_rules=[
                "must not become a full-body lifestyle portrait",
                "must not lose package readability behind the hand",
            ],
            product_lock_level="strong_product_lock",
            consistency_strength="high",
            reference_image_priority="main_packshot_with_hand_action_overlay",
            editable_regions=["background", "hand pose", "prop accents"],
            editable_region_strategy="hand_action_with_locked_package",
            allow_human_presence=True,
            allow_hand_only=True,
        )

    if shot_type == "open_box_structure":
        return ShotExecutionProfile(
            primary_subject=f"opened {package_type} structure",
            secondary_subject="inner tray or opening logic",
            differentiation_summary="structure explanation image, not a closed-package hero",
            banned_fallback_pattern="closed package hero frame with no opening logic",
            subject_rules=[
                "Show the opened package state or structural reveal clearly",
                "The opening logic and internal arrangement must remain believable and readable",
            ],
            composition_rules=[
                "Use a stable top or 3/4 angle that explains the structure instead of hiding it",
                "Do not collapse the shot back into a closed front-facing hero packshot",
            ],
            background_rules=["Keep props sparse so the structural read remains immediate"],
            lighting_rules=["Use crisp light that separates lids, trays, folds, and interior layers"],
            negative_rules=[
                "must not hide the opening state",
                "must not look like a closed-package hero image",
            ],
            product_lock_level="strong_product_lock",
            consistency_strength="medium_high",
            reference_image_priority="main_packshot_with_structural_edit",
            editable_regions=["background", "lid angle", "inner tray visibility"],
            editable_region_strategy="structure_reveal_with_locked_brand_panels",
        )

    if shot_type == "package_detail":
        subject_rules = [
            "This shot must not look like the hero image",
            "Move noticeably closer to the package and emphasize lid seam, label edge, material texture, and cylindrical contour",
            "A partial crop is allowed and preferred if it strengthens the detail-read",
            "Do not use a full front-facing hero composition",
        ]
        if is_tin_can:
            subject_rules.append("Make the cylindrical contour and surface transition clearly readable")
        return ShotExecutionProfile(
            primary_subject=f"{package_type} detail crop",
            secondary_subject="surface texture and edge transition",
            differentiation_summary="near-distance detail study, not a full hero packshot",
            banned_fallback_pattern="full front hero package composition",
            subject_rules=subject_rules,
            composition_rules=[
                "Use close framing, oblique angle, or partial crop so the shot reads as a detail image at first glance",
                "Let the detail dominate and only keep enough package context to preserve brand continuity",
            ],
            background_rules=["Background must stay simple and quiet so micro-details remain the first read"],
            lighting_rules=["Use grazing or directional light to reveal seam depth, embossing, texture, and contour transitions"],
            negative_rules=[
                "package_detail must not look like hero image",
                "must not use a full front-facing hero composition",
            ],
            product_lock_level="medium_product_lock",
            consistency_strength="medium_high",
            reference_image_priority="main_packshot_detail_crop",
            editable_regions=["crop window", "background", "surface highlights", "micro props"],
            editable_region_strategy="detail_crop_and_surface_emphasis",
        )

    if shot_type == "label_or_material_detail":
        return ShotExecutionProfile(
            primary_subject="label edge or package material detail",
            secondary_subject=base_secondary,
            differentiation_summary="micro detail of label finish or material texture, not a hero package view",
            banned_fallback_pattern="full package hero frame",
            subject_rules=[
                "Push in to label edge, print finish, embossing, paper grain, or material joinery as the first subject",
                "Keep only a limited package anchor so this still reads as a detail shot instead of a hero view",
            ],
            composition_rules=[
                "Use macro-like framing and allow partial crop",
                "Do not show the entire front package as the dominant read",
            ],
            background_rules=["Keep the background almost invisible or extremely restrained"],
            lighting_rules=["Use side light or raking light to reveal print finish, fibers, or seam texture"],
            negative_rules=[
                "must not revert to full package hero composition",
                "must not hide the material or label edge texture",
            ],
            product_lock_level="medium_product_lock",
            consistency_strength="medium_high",
            reference_image_priority="main_packshot_label_material_crop",
            editable_regions=["crop window", "surface reflections", "background"],
            editable_region_strategy="label_material_macro_focus",
        )

    if shot_type == "package_with_leaf_hint":
        return ShotExecutionProfile(
            primary_subject=f"{package_type} package with subtle dry leaf cue",
            secondary_subject="small dry leaf hint",
            differentiation_summary="package-led scene with leaf cue, not true dry-leaf hero and not isolated packshot",
            banned_fallback_pattern="isolated studio packshot with no leaf cue",
            subject_rules=[
                "Keep the package as the main readable subject",
                "Add a restrained dry leaf hint as a supporting cue rather than making leaves the foreground hero",
            ],
            composition_rules=[
                "Package should stay large and readable while the leaf hint sits near the foreground or side as a secondary cue",
                "Do not let the frame collapse into a plain isolated hero packshot with token decoration",
            ],
            background_rules=["Background can include a natural tea surface or calm tabletop context that supports the leaf hint"],
            lighting_rules=["Light both package readability and leaf texture, but keep the package as the visual winner"],
            negative_rules=[
                "must not become package-only isolated studio packshot",
                "must not promote the leaf hint above the package",
            ],
            product_lock_level="medium_product_lock",
            consistency_strength="medium_high",
            reference_image_priority="main_packshot_with_leaf_hint",
            editable_regions=["foreground leaves", "background surface", "prop accents"],
            editable_region_strategy="package_hero_with_leaf_support",
        )

    if shot_type == "dry_leaf_detail":
        detail_rule = (
            "Use the detail asset texture cues when available to strengthen dry leaf fidelity"
            if asset_mode == "packshot_plus_detail"
            else "Do not fabricate a package-only composition pretending to be a leaf detail shot"
        )
        return ShotExecutionProfile(
            primary_subject="dry tea leaves in the foreground",
            secondary_subject="package brand anchor in the background",
            differentiation_summary="dry leaf first, package reduced to a background anchor, never a package hero",
            banned_fallback_pattern="package-only composition or full package hero frame",
            subject_rules=[
                "Dry tea leaves must be the absolute first subject in the foreground",
                "Package can only appear as a reduced background brand anchor with clearly lower area share",
                "Highlight strip shape, dry leaf texture, whole-leaf quality, and raw ingredient fidelity",
                detail_rule,
            ],
            composition_rules=[
                "Move the camera close enough that leaf texture is the first read",
                "Do not center the package as a hero object",
                "Reserve text only on a clean patch away from the leaf texture cluster",
            ],
            background_rules=[
                "Use a calm neutral or tea-table surface with one clean text patch",
                "Background must support leaf texture readability instead of becoming a studio hero backdrop",
            ],
            lighting_rules=["Use directional macro light that reveals dry leaf fibers, twists, and surface relief"],
            negative_rules=[
                "dry_leaf_detail must not be package-only composition",
                "must not look like a hero packshot",
            ],
            product_lock_level="anchor_only_product_lock",
            consistency_strength="medium",
            reference_image_priority="detail_asset_first_then_main_packshot_anchor",
            editable_regions=["foreground leaves", "breathing space around leaves", "background anchor placement"],
            editable_region_strategy="foreground_leaf_subject_with_package_anchor",
        )

    if shot_type == "tea_soup_experience":
        return ShotExecutionProfile(
            primary_subject="brewed tea vessel and visible tea liquid",
            secondary_subject="package anchor in the background",
            differentiation_summary="tea soup and vessel first, package only anchors brand in the back",
            banned_fallback_pattern="package-only composition or dry packshot without visible liquid",
            subject_rules=[
                "Tea soup, cup, gaiwan, or brewed tea vessel must be the first subject",
                "Visible liquid is mandatory in the frame",
                "Package must stay in the back as a brand anchor with clearly reduced dominance",
                "Do not output a package-only composition",
            ],
            composition_rules=[
                "Build the frame around the vessel and liquid reflections instead of the package body",
                "Keep the package smaller, further back, or softened as a background anchor",
            ],
            background_rules=["Background should support a real tea-drinking or brewing surface, not an empty studio backdrop"],
            lighting_rules=["Use lighting that reveals liquid transparency, rim highlights, and vessel form"],
            negative_rules=[
                "tea_soup_experience must include brewed tea vessel",
                "must not become a package-only composition",
            ],
            product_lock_level="anchor_only_product_lock",
            consistency_strength="medium",
            reference_image_priority="brewed_tea_vessel_first_then_main_packshot_anchor",
            editable_regions=["tea vessel", "tea liquid", "steam", "background package anchor", "brewing props"],
            editable_region_strategy="brewed_tea_foreground_with_package_anchor",
        )

    if shot_type in {"lifestyle_or_brewing_context", "package_in_brewing_context"}:
        package_rule = (
            "Keep the package readable but not isolated; it must live inside a believable brewing scene"
            if shot_type == "package_in_brewing_context"
            else "Package may act as an anchor, but brewing props and tea context must be visually obvious"
        )
        return ShotExecutionProfile(
            primary_subject="package within brewing or lifestyle context",
            secondary_subject="brewing props and tea-scene anchors",
            differentiation_summary="context-driven tea image with brewing anchors, not a plain studio packshot",
            banned_fallback_pattern="isolated studio packshot with token shadows only",
            subject_rules=[
                "Brewing props or explicit scene anchors are mandatory",
                package_rule,
                "Do not solve this shot by adding only a little background tone and shadow behind an isolated package",
            ],
            composition_rules=[
                "Show a brewing surface, cupware, gaiwan, tray, or other clear tea context",
                "The frame must read as context or lifestyle at first glance rather than hero packshot",
            ],
            background_rules=[
                "Use a believable brewing table, tea room cue, or lifestyle surface instead of plain empty studio background",
            ],
            lighting_rules=["Keep premium tea mood while preserving visible context objects and material depth"],
            negative_rules=[
                "lifestyle shot must not remain isolated studio packshot",
                "must include brewing props or clear scene anchors",
            ],
            product_lock_level="anchor_only_product_lock" if shot_type == "lifestyle_or_brewing_context" else "medium_product_lock",
            consistency_strength="medium",
            reference_image_priority="main_packshot_anchor_with_context_expansion",
            editable_regions=["props", "surface styling", "background context", "vessel placement"],
            editable_region_strategy="context_building_with_package_anchor",
        )

    return ShotExecutionProfile(
        primary_subject=f"{package_type} product package",
        secondary_subject="minimal supporting scene",
        differentiation_summary=f"{shot_type} execution must stay visually distinct from the hero packshot",
        banned_fallback_pattern="generic centered hero packshot",
        subject_rules=[
            f"Use the uploaded {package_type} as the exact subject reference",
            "Follow the shot goal and avoid collapsing back into a generic hero frame",
        ],
        composition_rules=["Keep the composition commercial and readable while preserving shot-specific intent"],
        background_rules=["Keep background subordinate to the intended subject emphasis"],
        lighting_rules=["Preserve product fidelity while adapting the light to the shot intent"],
        negative_rules=["must not collapse into a generic hero packshot"],
        product_lock_level="medium_product_lock",
        consistency_strength="medium_high",
        reference_image_priority="main_packshot",
        editable_regions=["background", "props", "crop"],
        editable_region_strategy="general_subject_locked_scene_adjustment",
    )


def _join_prompt_sentences(parts: list[str]) -> str:
    """把多段执行说明拼成稳定句子，避免空白和重复标点。"""
    merged: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if not text:
            continue
        merged.append(text if text.endswith((".", "!", "?")) else f"{text}.")
    return " ".join(merged)


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


def _resolve_preferred_text_safe_zone(shot: ShotSpec, layout_item, profile: ShotExecutionProfile) -> str:
    """根据 shot 画像和 layout 输出最终可执行的文字安全区偏好。"""
    layout_zone = getattr(layout_item, "text_safe_zone", "") or shot.preferred_text_safe_zone
    if shot.shot_type == "hero_brand":
        return layout_zone if layout_zone in {"top_left", "top_right", "top"} else "top_right"
    if shot.shot_type == "carry_action":
        return "opposite_of_action_direction"
    if shot.shot_type == "open_box_structure":
        return layout_zone if layout_zone in {"top", "top_right"} else "top_right"
    if shot.shot_type in {"dry_leaf_detail", "label_or_material_detail"}:
        return "background_clean_area"
    if shot.shot_type in {"tea_soup_experience", "lifestyle_or_brewing_context", "package_in_brewing_context"}:
        return "top"
    if "detail" in profile.differentiation_summary:
        return layout_zone or "top_left"
    return layout_zone or "top_right"


def _resolve_subject_placement_hint(shot: ShotSpec, preferred_zone: str, profile: ShotExecutionProfile) -> str:
    """输出给 layout/render 共用的主体摆位摘要。"""
    if shot.shot_type == "hero_brand":
        return "stable hero package with clean upper-area copy zone"
    if shot.shot_type == "carry_action":
        return "subject follows the hand motion, copy stays on the opposite side"
    if shot.shot_type == "open_box_structure":
        return "opened package stays central and structural read remains clear"
    if shot.shot_type == "package_detail":
        return "package detail crop dominates, hero framing forbidden, copy stays off the texture focus"
    if shot.shot_type == "label_or_material_detail":
        return "label or material detail dominates, package remains only a small anchor"
    if shot.shot_type == "dry_leaf_detail":
        return "tea leaf detail foreground, package anchor background, text stays in clean background area"
    if shot.shot_type == "tea_soup_experience":
        return "tea soup foreground, package anchor background, upper area kept clear"
    if shot.shot_type in {"lifestyle_or_brewing_context", "package_in_brewing_context"}:
        return "context props and brewing anchors must be visible, package must not read as isolated studio hero"
    if shot.shot_type == "package_with_leaf_hint":
        return "package remains main subject while leaf cue supports in foreground or side"
    if "hero" in profile.banned_fallback_pattern:
        return f"avoid hero fallback, prefer copy zone at {preferred_zone}"
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
            "product_lock_level": base.product_lock_level or generated.product_lock_level,
            "editable_region_strategy": base.editable_region_strategy or generated.editable_region_strategy,
            "allow_human_presence": base.allow_human_presence,
            "allow_hand_only": base.allow_hand_only,
        }
    )


def _build_spec_debug_logs(plan: ShotPromptSpecPlan, product_analysis) -> list[str]:
    """输出每个 shot 的差异化执行摘要，便于定位是否退化成 hero。"""
    logs: list[str] = []
    for spec in plan.specs:
        profile = _build_shot_execution_profile(
            ShotSpec(shot_id=spec.shot_id, shot_type=spec.shot_type, title="", purpose="", composition_hint="", copy_goal=""),
            product_analysis,
        )
        style_summary = spec.style_prompt[:100] + ("..." if len(spec.style_prompt) > 100 else "")
        logs.append(
            (
                "[shot_prompt_refiner] shot_spec "
                f"shot_id={spec.shot_id} "
                f"shot_type={spec.shot_type} "
                f"style_theme_summary={style_summary} "
                f"generation_mode={spec.render_constraints.generation_mode} "
                f"primary_subject={profile.primary_subject} "
                f"secondary_subject={profile.secondary_subject} "
                f"shot_differentiation_summary={profile.differentiation_summary} "
                f"banned_fallback_pattern={profile.banned_fallback_pattern} "
                f"complete_eight_layers={str(spec.has_complete_prompt_layers()).lower()}"
            )
        )
    return logs
