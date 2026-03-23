"""Prompt 桥接节点。

文件位置：
- `src/workflows/nodes/build_prompts.py`

核心职责：
- 把结构化 `shot_prompt_specs` 映射成兼容旧渲染链路的 `ImagePromptPlan`
- 在 prompt contract 层兼容 `t2i` 与 `image_edit`
- 逐张落盘 shot / copy / layout / prompt 调试产物

节点前后关系：
- 上游节点：`shot_prompt_refiner`
- 下游节点：`render_images`
"""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.copy_plan import CopyItem
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutItem
from src.domain.shot_plan import ShotSpec
from src.services.assets.reference_selector import select_reference_assets
from src.services.fallbacks.copy_fallback import build_default_copy_item_for_shot
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    should_use_cache,
)
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

logger = logging.getLogger(__name__)


def build_prompts(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """根据结构化 spec 构建兼容型 `ImagePromptPlan`。"""
    task = state["task"]
    target_generation = _resolve_target_generation_context(state, deps)
    logs = [
        *state.get("logs", []),
        (
            "[build_prompts] start "
            f"target_generation_mode={target_generation['generation_mode']} "
            f"reference_asset_ids={target_generation['reference_asset_ids']} "
            f"style_architecture_present={bool(state.get('style_architecture'))} "
            f"shot_prompt_specs_present={bool(state.get('shot_prompt_specs'))}"
        ),
        *format_connected_contract_logs(state, node_name="build_prompts"),
    ]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    spec_map = {item.shot_id: item for item in state["shot_prompt_specs"].specs}
    cache_key, cache_context = build_node_cache_key(
        node_name="build_prompts",
        state=state,
        deps=deps,
        prompt_version="structured-shot-prompt-specs-v2",
        provider_name="structured_mapper",
        model_id="programmatic",
        extra_payload={
            "target_generation_mode": target_generation["generation_mode"],
            "target_reference_asset_ids": target_generation["reference_asset_ids"],
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "style_architecture_hash": hash_state_payload(state["style_architecture"]),
            "shot_plan_hash": hash_state_payload(state["shot_plan"]),
            "shot_prompt_specs_hash": hash_state_payload(state["shot_prompt_specs"]),
            "layout_plan_hash": hash_state_payload(state["layout_plan"]),
        },
    )
    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("build_prompts", cache_key, ImagePromptPlan)
        if cached_plan is not None:
            _save_all_prompt_artifacts(
                deps=deps,
                task_id=task.task_id,
                prompts=cached_plan.prompts,
                shots=state["shot_plan"].shots,
                copy_map=copy_map,
                layout_map=layout_map,
            )
            deps.storage.save_json_artifact(task.task_id, "image_prompt_plan.json", cached_plan)
            logs.extend(
                [
                    f"[build_prompts] cache hit key={cache_key}",
                    f"[cache] node=build_prompts status=hit key={cache_key}",
                    f"[build_prompts] restored cached ImagePromptPlan generation_mode={cached_plan.generation_mode}",
                ]
            )
            return {"image_prompt_plan": cached_plan, "logs": logs}
        logs.extend(
            [
                f"[build_prompts] cache miss key={cache_key}",
                f"[cache] node=build_prompts status=miss key={cache_key}",
            ]
        )
    elif is_force_rerun(state):
        logs.extend(
            [
                "[build_prompts] ignore cache requested",
                "[cache] node=build_prompts status=ignored key=-",
            ]
        )

    generation_mode = str(target_generation["generation_mode"])
    prompts: list[ImagePrompt] = []
    for shot in state["shot_plan"].shots:
        prompt = _build_image_prompt(
            task_output_size=task.output_size,
            shot=shot,
            copy_item=_get_copy_item_for_shot(shot, copy_map, logs),
            layout_item=layout_map[shot.shot_id],
            spec=spec_map[shot.shot_id],
            product_analysis=state["product_analysis"],
            style_architecture=state["style_architecture"],
            generation_mode=generation_mode,
        )
        prompts.append(prompt)
    plan = ImagePromptPlan(generation_mode=generation_mode, prompts=prompts)
    deps.storage.save_json_artifact(task.task_id, "image_prompt_plan.json", plan)
    _save_all_prompt_artifacts(
        deps=deps,
        task_id=task.task_id,
        prompts=plan.prompts,
        shots=state["shot_plan"].shots,
        copy_map=copy_map,
        layout_map=layout_map,
    )
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("build_prompts", cache_key, plan, metadata=cache_context)
    logs.extend(
        [
            f"[build_prompts] completed generation_mode={plan.generation_mode} count={len(plan.prompts)}",
            "[build_prompts] saved image_prompt_plan.json",
        ]
    )
    return {"image_prompt_plan": plan, "logs": logs}


def _build_image_prompt(
    *,
    task_output_size: str,
    shot: ShotSpec,
    copy_item: CopyItem,
    layout_item: LayoutItem,
    spec,
    product_analysis,
    style_architecture,
    generation_mode: str,
) -> ImagePrompt:
    """把单张结构化 spec 映射成兼容型 `ImagePrompt`。

    这里保留两套输入：
    - `prompt`：兼容 `t2i`
    - `edit_instruction`：兼容 `image_edit`
    """
    del copy_item
    text_safe_zone = getattr(layout_item, "text_safe_zone", "")
<<<<<<< HEAD
    product_lock_rules = spec.product_lock.flattened_rules()
=======
    product_lock_rules = _resolve_prompt_keep_subject_rules(spec=spec, product_analysis=product_analysis)
    editable_regions = _resolve_prompt_editable_regions(
        shot_type=shot.shot_type,
        spec=spec,
        product_analysis=product_analysis,
    )
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    layout_constraint_lines = spec.layout_constraints.as_prompt_lines()
    render_constraint_lines = spec.render_constraints.as_prompt_lines()
    preserve_rules = [*product_analysis.locked_elements, *product_analysis.visual_identity.must_preserve]
    prompt = (
        f"{spec.subject_prompt} "
        f"{spec.package_appearance_prompt} "
        f"{spec.composition_prompt} "
        f"{spec.background_prompt} "
        f"{spec.lighting_prompt} "
        f"{spec.style_prompt} "
        f"{spec.quality_prompt} "
        f"Copy intent: {spec.copy_intent.summary_text()}."
    )
    edit_instruction = (
        "Edit the uploaded reference product image with strict product lock. "
        f"Goal: {spec.goal}. "
        f"Product lock: {', '.join(product_lock_rules)}. "
        f"Package appearance: {spec.package_appearance_prompt}. "
        f"Composition: {spec.composition_prompt}. "
        f"Background: {spec.background_prompt}. "
        f"Lighting: {spec.lighting_prompt}. "
        f"Style: {spec.style_prompt}. "
        f"Layout constraints: {', '.join(layout_constraint_lines)}. "
        f"Render constraints: {', '.join(render_constraint_lines)}. "
        f"Copy intent: {spec.copy_intent.summary_text()}."
    )
    return ImagePrompt(
        shot_id=shot.shot_id,
        shot_type=shot.shot_type,
        prompt=prompt,
        generation_mode=generation_mode,
        edit_instruction=edit_instruction,
        negative_prompt=spec.negative_prompt,
        output_size=task_output_size,
        preserve_rules=preserve_rules,
        keep_subject_rules=product_lock_rules or preserve_rules,
<<<<<<< HEAD
        editable_regions=spec.product_lock.editable_regions or product_analysis.editable_elements,
=======
        editable_regions=editable_regions,
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        locked_regions=product_analysis.locked_elements,
        background_direction="; ".join(style_architecture.background_strategy + [spec.background_prompt]),
        lighting_direction="; ".join(style_architecture.lighting_strategy + [spec.lighting_prompt]),
        text_safe_zone=text_safe_zone,
        subject_consistency_level=spec.render_constraints.consistency_strength,
        text_space_hint=text_safe_zone,
        composition_notes=[spec.composition_prompt, *layout_constraint_lines],
        style_notes=[style_architecture.style_theme, *style_architecture.prop_system, *style_architecture.lens_strategy],
    )


<<<<<<< HEAD
=======
def _resolve_prompt_keep_subject_rules(*, spec, product_analysis) -> list[str]:
    """把结构化商品锁定规则整理成兼容层也能稳定消费的去重列表。"""
    return _merge_unique_strings(
        list(spec.product_lock.must_preserve or []),
        [f"must preserve texts: {item}" for item in list(spec.product_lock.must_preserve_texts or [])],
        [f"must not change: {item}" for item in list(spec.product_lock.must_not_change or [])],
        list(product_analysis.locked_elements or []),
    )


def _resolve_prompt_editable_regions(*, shot_type: str, spec, product_analysis) -> list[str]:
    """统一生成 shot-aware 的 editable_regions，避免后续 render 日志频繁出现空数组。"""
    return _merge_unique_strings(
        _editable_region_defaults_for_shot_type(shot_type),
        [_normalize_editable_region_name(item) for item in list(spec.product_lock.editable_regions or [])],
        [_normalize_editable_region_name(item) for item in list(product_analysis.editable_elements or [])],
    )


def _editable_region_defaults_for_shot_type(shot_type: str) -> list[str]:
    """按 shot_type 提供最小可编辑区域兜底，兼顾 image_edit 的镜头变化空间。"""
    mapping = {
        "hero_brand": ["background", "props", "lighting", "crop"],
        "carry_action": ["hand_pose", "background", "props", "lighting", "crop"],
        "open_box_structure": ["package_structure", "background", "props", "lighting", "crop"],
        "package_detail": ["crop", "lighting", "detail_emphasis", "background"],
        "label_or_material_detail": ["crop", "detail_emphasis", "lighting", "background"],
        "package_with_leaf_hint": ["foreground_leaf_subject", "background", "props", "lighting", "crop"],
        "dry_leaf_detail": ["foreground_leaf_subject", "background", "props", "lighting", "depth_of_field"],
        "tea_soup_experience": ["tea_soup_subject", "vessel", "background", "props", "lighting"],
        "lifestyle_or_brewing_context": ["props", "background", "scene_context", "depth_of_field", "lighting"],
        "package_in_brewing_context": ["props", "background", "scene_context", "depth_of_field", "lighting"],
    }
    return list(mapping.get(shot_type, ["background", "props", "lighting", "crop"]))


def _normalize_editable_region_name(value: str) -> str:
    """把上游不同命名收敛成 render 阶段更稳定的区域标签。"""
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "surface_styling": "props",
        "prop_accents": "props",
        "micro_props": "props",
        "shadow_shape": "lighting",
        "surface_highlights": "detail_emphasis",
        "crop_window": "crop",
        "foreground_leaves": "foreground_leaf_subject",
        "breathing_space_around_leaves": "depth_of_field",
        "background_anchor_placement": "background",
        "tea_vessel": "vessel",
        "tea_liquid": "tea_soup_subject",
        "background_package_anchor": "background",
        "brewing_props": "props",
        "vessel_placement": "vessel",
        "background_context": "scene_context",
        "inner_tray_visibility": "package_structure",
        "lid_angle": "package_structure",
    }
    return aliases.get(normalized, normalized)


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    """保持原始顺序合并去重，避免兼容 prompt 字段里重复同义规则。"""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
def _resolve_target_generation_context(state: WorkflowState, deps: WorkflowDependencies) -> dict[str, object]:
    """在 `build_prompts` 阶段预判后续渲染会走哪种 generation mode。"""
    selected_assets = select_reference_assets(
        state.get("assets", []),
        max_images=_resolve_render_max_reference_images(state),
    )
    resolver = getattr(deps.image_generation_provider, "resolve_generation_context", None)
    if callable(resolver):
        context = resolver(reference_assets=selected_assets)
        return {
            "generation_mode": context.generation_mode,
            "reference_asset_ids": context.reference_asset_ids,
        }
    return {
        "generation_mode": "image_edit" if selected_assets else "t2i",
        "reference_asset_ids": [asset.asset_id for asset in selected_assets],
    }


def _resolve_render_max_reference_images(state: WorkflowState) -> int:
    """解析 render 阶段默认参考图数量。"""
    explicit_value = state.get("render_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    return max(1, int(get_settings().resolve_image_edit_max_reference_images()))


def _get_copy_item_for_shot(shot: ShotSpec, copy_map: dict[str, CopyItem], logs: list[str]) -> CopyItem:
    """获取单张图对应文案；如果缺失则回退到默认文案。"""
    copy_item = copy_map.get(shot.shot_id)
    if copy_item is not None:
        return copy_item
    logs.append(f"[build_prompts] warning missing copy for shot_id={shot.shot_id}, fallback applied")
    return build_default_copy_item_for_shot(shot)


def _save_all_prompt_artifacts(
    *,
    deps: WorkflowDependencies,
    task_id: str,
    prompts: list[ImagePrompt],
    shots: list[ShotSpec],
    copy_map: dict[str, CopyItem],
    layout_map: dict[str, LayoutItem],
) -> None:
    """按 shot 落盘中间产物，便于逐张排查 prompt、copy、layout 是否对齐。"""
    prompt_map = {prompt.shot_id: prompt for prompt in prompts}
    for shot in shots:
        prompt = prompt_map.get(shot.shot_id)
        if prompt is None:
            continue
        base_dir = f"artifacts/shots/{shot.shot_id}"
        deps.storage.save_json_artifact(task_id, f"{base_dir}/shot.json", shot)
        deps.storage.save_json_artifact(task_id, f"{base_dir}/copy.json", copy_map.get(shot.shot_id) or build_default_copy_item_for_shot(shot))
        deps.storage.save_json_artifact(task_id, f"{base_dir}/layout.json", layout_map[shot.shot_id])
        deps.storage.save_json_artifact(task_id, f"{base_dir}/prompt.json", prompt)
