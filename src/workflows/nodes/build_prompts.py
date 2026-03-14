"""Build image prompt artifacts."""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.copy_plan import CopyItem
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutItem
from src.domain.shot_plan import ShotSpec
from src.services.assets.reference_selector import select_reference_assets
from src.services.fallbacks.copy_fallback import build_default_copy_item_for_shot
from src.services.prompting.context_builder import (
    build_build_prompts_context,
    collect_prompt_policy_signature,
    infer_text_space_hint,
)
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import describe_prompt_source, dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


DEFAULT_NEGATIVE_PROMPTS = [
    "plain white background",
    "deformed product",
    "wrong label layout",
    "wrong packaging structure",
    "wrong material appearance",
    "garbled text",
    "misspelled Chinese text",
    "low resolution",
    "blurry details",
    "overexposed lighting",
    "underexposed lighting",
    "cheap looking composition",
    "messy background",
    "exaggerated visual effects",
    "plastic cheap texture",
    "floating object composition",
    "illustration style",
    "cartoon style",
    "too many props",
    "harsh shadows",
    "props overpowering product",
]


def build_prompts(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """Build and persist the image prompt plan."""
    task = state["task"]
    prompt_build_mode = _resolve_prompt_build_mode(state)
    target_generation = _resolve_target_generation_context(state, deps)
    logs = [
        *state.get("logs", []),
        (
            "[build_prompts] start "
            f"text_provider_mode={deps.text_provider_mode} "
            f"prompt_build_mode={prompt_build_mode} "
            f"target_generation_mode={target_generation['generation_mode']} "
            f"reference_asset_ids={target_generation['reference_asset_ids']}"
        ),
    ]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    template_name = "build_image_prompts.md"
    template_source = describe_prompt_source(template_name)
    provider_name, provider_model_id = planning_provider_identity(deps)
    policy_signature = collect_prompt_policy_signature(
        task=task,
        product_analysis=state["product_analysis"],
        shots=state["shot_plan"].shots,
    )
    cache_key, cache_context = build_node_cache_key(
        node_name="build_prompts",
        state=state,
        deps=deps,
        prompt_filename=template_name if deps.text_provider_mode == "real" else None,
        prompt_version="mock-image-prompts-v2" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "prompt_build_mode": prompt_build_mode,
            "target_generation_mode": target_generation["generation_mode"],
            "target_reference_asset_ids": target_generation["reference_asset_ids"],
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "shot_plan_hash": hash_state_payload(state["shot_plan"]),
            "copy_plan_hash": hash_state_payload(state["copy_plan"]),
            "layout_plan_hash": hash_state_payload(state["layout_plan"]),
            "policy_signature_hash": hash_state_payload(policy_signature),
        },
    )
    logger.info(
        "build_prompts running: template_source=%s, prompt_build_mode=%s, target_generation_mode=%s",
        template_source,
        prompt_build_mode,
        target_generation["generation_mode"],
    )
    logs.extend(
        [
            f"[build_prompts] template_source={template_source}",
            "[build_prompts] no raw image input is sent to the LLM in this node; real reference assets are only sent during render_images",
        ]
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
                    f"[build_prompts] restored cached ImagePromptPlan generation_mode={cached_plan.generation_mode}",
                ]
            )
            return {"image_prompt_plan": cached_plan, "logs": logs}
        logs.append(f"[build_prompts] cache miss key={cache_key}")
    elif is_force_rerun(state):
        logs.append("[build_prompts] ignore cache requested")

    if prompt_build_mode == "batch":
        plan = _build_prompts_batch_mode(state, deps, logs, template_name, target_generation)
    else:
        plan = _build_prompts_per_shot_mode(state, deps, logs, template_name, target_generation)

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
    prompt_shot_ids = ", ".join(item.shot_id for item in plan.prompts)
    logs.extend(
        [
            (
                "[build_prompts] completed "
                f"generation_mode={plan.generation_mode} "
                f"count={len(plan.prompts)} "
                f"shot_ids={prompt_shot_ids or '-'}"
            ),
            f"[build_prompts] planning_model={deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}",
            "[build_prompts] saved image_prompt_plan.json",
        ]
    )
    return {"image_prompt_plan": plan, "logs": logs}


def _build_prompts_per_shot_mode(
    state: WorkflowState,
    deps: WorkflowDependencies,
    logs: list[str],
    template_name: str,
    target_generation: dict[str, object],
) -> ImagePromptPlan:
    task = state["task"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    generation_mode = str(target_generation["generation_mode"])
    logs.append(f"[build_prompts] using per_shot mode target_generation_mode={generation_mode}")
    if deps.text_provider_mode == "real":
        prompts = []
        total_shots = len(state["shot_plan"].shots)
        for index, shot in enumerate(state["shot_plan"].shots, start=1):
            copy_item = _get_copy_item_for_shot(shot=shot, copy_map=copy_map, logs=logs)
            layout_item = layout_map[shot.shot_id]
            prompt_input = _build_single_shot_prompt_input(
                task=task,
                product_analysis=state["product_analysis"],
                shot=shot,
                copy_item=copy_item,
                layout_item=layout_item,
                target_generation=target_generation,
            )
            logs.append(
                f"[build_prompts] generating shot {index}/{total_shots} shot_id={shot.shot_id} generation_mode={generation_mode}"
            )
            shot_prompt = deps.planning_provider.generate_structured(
                prompt_input,
                ImagePrompt,
                system_prompt=load_prompt_text(template_name),
            )
            prompts.append(
                _normalize_image_prompt(
                    task_output_size=task.output_size,
                    shot=shot,
                    layout_item=layout_item,
                    product_analysis=state["product_analysis"],
                    prompt=shot_prompt,
                    generation_mode=generation_mode,
                )
            )
        return ImagePromptPlan(generation_mode=generation_mode, prompts=prompts)

    prompts = []
    total_shots = len(state["shot_plan"].shots)
    for index, shot in enumerate(state["shot_plan"].shots, start=1):
        copy_item = _get_copy_item_for_shot(shot=shot, copy_map=copy_map, logs=logs)
        layout_item = layout_map[shot.shot_id]
        logs.append(f"[build_prompts] mock generation shot {index}/{total_shots} shot_id={shot.shot_id} generation_mode={generation_mode}")
        prompts.append(
            _build_mock_prompt(
                task=task,
                product_analysis=state["product_analysis"],
                shot=shot,
                copy_item=copy_item,
                layout_item=layout_item,
                generation_mode=generation_mode,
            )
        )
    return ImagePromptPlan(generation_mode=generation_mode, prompts=prompts)


def _build_prompts_batch_mode(
    state: WorkflowState,
    deps: WorkflowDependencies,
    logs: list[str],
    template_name: str,
    target_generation: dict[str, object],
) -> ImagePromptPlan:
    task = state["task"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    generation_mode = str(target_generation["generation_mode"])
    logs.append(f"[build_prompts] using batch mode target_generation_mode={generation_mode}")
    if deps.text_provider_mode == "real":
        batch_prompt_input = _build_batch_prompt_input(
            task=task,
            product_analysis=state["product_analysis"],
            shots=state["shot_plan"].shots,
            copy_map=copy_map,
            layout_map=layout_map,
            logs=logs,
            target_generation=target_generation,
        )
        plan = deps.planning_provider.generate_structured(
            batch_prompt_input,
            ImagePromptPlan,
            system_prompt=load_prompt_text(template_name),
        )
        normalized_prompts = []
        for shot in state["shot_plan"].shots:
            layout_item = layout_map[shot.shot_id]
            prompt = _find_prompt_by_shot_id(plan, shot.shot_id)
            normalized_prompts.append(
                _normalize_image_prompt(
                    task_output_size=task.output_size,
                    shot=shot,
                    layout_item=layout_item,
                    product_analysis=state["product_analysis"],
                    prompt=prompt,
                    generation_mode=generation_mode,
                )
            )
        return ImagePromptPlan(generation_mode=generation_mode, prompts=normalized_prompts)

    prompts = []
    for shot in state["shot_plan"].shots:
        prompts.append(
            _build_mock_prompt(
                task=task,
                product_analysis=state["product_analysis"],
                shot=shot,
                copy_item=_get_copy_item_for_shot(shot=shot, copy_map=copy_map, logs=logs),
                layout_item=layout_map[shot.shot_id],
                generation_mode=generation_mode,
            )
        )
    return ImagePromptPlan(generation_mode=generation_mode, prompts=prompts)


def _build_single_shot_prompt_input(
    *,
    task,
    product_analysis,
    shot: ShotSpec,
    copy_item: CopyItem,
    layout_item: LayoutItem,
    target_generation: dict[str, object],
) -> str:
    layout_text_safe_zone = _resolve_layout_text_safe_zone(layout_item)
    prompt_context = build_build_prompts_context(
        task=task,
        product_analysis=product_analysis,
        shot=shot,
        copy_item=copy_item,
        layout_item=layout_item,
    )
    generation_mode = str(target_generation["generation_mode"])
    prompt_context["build_prompt_rules"] = {
        "mode": "structured_reasoning_only",
        "prompt_build_mode": "per_shot",
        "target_generation_mode": generation_mode,
        "image_input_sent_to_model": False,
        "reference_image_stage": "render_images",
        "reference_asset_ids_for_render": target_generation["reference_asset_ids"],
        "text_space_hint": layout_text_safe_zone,
        "layout_text_safe_zone": layout_text_safe_zone,
        "text_safe_zone_required": True,
        "preserve_priority": product_analysis.visual_identity.must_preserve,
        "negative_prompt_must_cover": DEFAULT_NEGATIVE_PROMPTS,
        "image_edit_contract": {
            "keep_original_package": True,
            "keep_label_layout": True,
            "keep_main_colors": True,
            "keep_structure_ratio": True,
            "allow_background_change": True,
            "allow_props_change": True,
            "allow_lighting_change": True,
            "allow_angle_change": True,
        },
    }
    return (
        "You are in the build_prompts node. Produce one ImagePrompt JSON object for exactly one shot.\n"
        "Do not output free-form explanation. Do not output markdown.\n"
        "The LLM does not see any image input in this node. Real reference assets are only passed later in render_images.\n"
        f"{dump_pretty(prompt_context)}"
    )


def _build_batch_prompt_input(
    *,
    task,
    product_analysis,
    shots: list[ShotSpec],
    copy_map: dict[str, CopyItem],
    layout_map: dict[str, LayoutItem],
    logs: list[str],
    target_generation: dict[str, object],
) -> str:
    batch_context_shots = []
    for shot in shots:
        batch_context_shots.append(
            build_build_prompts_context(
                task=task,
                product_analysis=product_analysis,
                shot=shot,
                copy_item=_get_copy_item_for_shot(shot=shot, copy_map=copy_map, logs=logs),
                layout_item=layout_map[shot.shot_id],
            )
        )
    batch_context = {
        "task": task,
        "product_analysis": product_analysis,
        "build_prompt_rules": {
            "mode": "structured_reasoning_only",
            "prompt_build_mode": "batch",
            "target_generation_mode": target_generation["generation_mode"],
            "image_input_sent_to_model": False,
            "reference_image_stage": "render_images",
            "reference_asset_ids_for_render": target_generation["reference_asset_ids"],
            "output_schema": "ImagePromptPlan",
            "must_keep_shot_ids": [shot.shot_id for shot in shots],
            "negative_prompt_must_cover": DEFAULT_NEGATIVE_PROMPTS,
            "image_edit_contract": {
                "keep_original_package": True,
                "do_not_redesign_label": True,
                "do_not_change_container_shape": True,
                "do_not_change_structure_ratio": True,
                "background_and_lighting_can_change": True,
                "must_leave_text_safe_zone": True,
            },
        },
        "shots": batch_context_shots,
    }
    return (
        "You are in the build_prompts node. Produce one ImagePromptPlan JSON for the full shot list.\n"
        "The LLM does not see any image input in this node. Real reference assets are only passed later in render_images.\n"
        "Do not omit shot_id values and do not add extra shots.\n"
        f"{dump_pretty(batch_context)}"
    )


def _build_mock_prompt(
    *,
    task,
    product_analysis,
    shot: ShotSpec,
    copy_item: CopyItem,
    layout_item: LayoutItem,
    generation_mode: str,
) -> ImagePrompt:
    prompt_context = build_build_prompts_context(
        task=task,
        product_analysis=product_analysis,
        shot=shot,
        copy_item=copy_item,
        layout_item=layout_item,
    )
    layout_text_safe_zone = _resolve_layout_text_safe_zone(layout_item)
    base_prompt = ImagePrompt(
        shot_id=shot.shot_id,
        shot_type=shot.shot_type,
        generation_mode=generation_mode,
        prompt=(
            "Use the uploaded reference product as the exact hero subject, preserve the original package silhouette, "
            "label placement, package colors and key identity points, "
            f"render a premium e-commerce shot for {shot.title}, "
            f"scene and composition: {shot.scene_direction or shot.purpose}, {shot.composition_direction or shot.composition_hint}, "
            f"reserve clean text space in the {layout_text_safe_zone} area, restrained props, realistic premium lighting."
        ),
        negative_prompt=DEFAULT_NEGATIVE_PROMPTS,
        output_size=task.output_size,
        preserve_rules=product_analysis.visual_identity.must_preserve,
        keep_subject_rules=_default_keep_subject_rules(product_analysis),
        editable_regions=_default_editable_regions(),
        locked_regions=_default_locked_regions(),
        background_direction=shot.scene_direction or prompt_context["style_anchor_summary"],
        lighting_direction=_default_lighting_direction(product_analysis),
        text_safe_zone=layout_text_safe_zone,
        text_space_hint=layout_text_safe_zone,
        subject_consistency_level="strict" if generation_mode == "image_edit" else "high",
        composition_notes=[
            shot.composition_hint,
            *(prompt_context["shot_type_policy"].get("composition_defaults", [])),
        ],
        style_notes=[
            prompt_context["style_anchor_summary"],
            *(prompt_context["platform_policy"].get("commercial_focus", [])),
        ],
    )
    return _normalize_image_prompt(
        task_output_size=task.output_size,
        shot=shot,
        layout_item=layout_item,
        product_analysis=product_analysis,
        prompt=base_prompt,
        generation_mode=generation_mode,
    )


def _normalize_image_prompt(
    *,
    task_output_size: str,
    shot: ShotSpec,
    layout_item: LayoutItem,
    product_analysis,
    prompt: ImagePrompt,
    generation_mode: str,
) -> ImagePrompt:
    preserve_rules = prompt.preserve_rules or product_analysis.visual_identity.must_preserve
    layout_text_safe_zone = _resolve_layout_text_safe_zone(layout_item)
    text_space_hint = layout_text_safe_zone or prompt.text_space_hint
    keep_subject_rules = prompt.keep_subject_rules or _default_keep_subject_rules(product_analysis)
    editable_regions = prompt.editable_regions or _default_editable_regions()
    locked_regions = prompt.locked_regions or _default_locked_regions()
    background_direction = prompt.background_direction or shot.scene_direction or shot.purpose
    lighting_direction = prompt.lighting_direction or _default_lighting_direction(product_analysis)
    text_safe_zone = layout_text_safe_zone or prompt.text_safe_zone or text_space_hint
    subject_consistency_level = prompt.subject_consistency_level or ("strict" if generation_mode == "image_edit" else "high")
    composition_notes = prompt.composition_notes or [
        shot.composition_hint,
        shot.composition_direction or "clean commercial composition with explicit text-safe space",
    ]
    style_notes = prompt.style_notes or [
        *product_analysis.visual_constraints.recommended_style_direction[:3],
        "high-end e-commerce photography",
    ]
    negative_prompt = prompt.negative_prompt or DEFAULT_NEGATIVE_PROMPTS
    base_prompt = prompt.prompt or _default_t2i_prompt(
        shot=shot,
        text_space_hint=text_space_hint,
        preserve_rules=preserve_rules,
        background_direction=background_direction,
        lighting_direction=lighting_direction,
    )
    edit_instruction = prompt.edit_instruction or _default_edit_instruction(
        shot=shot,
        keep_subject_rules=keep_subject_rules,
        editable_regions=editable_regions,
        locked_regions=locked_regions,
        background_direction=background_direction,
        lighting_direction=lighting_direction,
        text_safe_zone=text_safe_zone,
        subject_consistency_level=subject_consistency_level,
    )
    return prompt.model_copy(
        update={
            "shot_id": prompt.shot_id or shot.shot_id,
            "shot_type": prompt.shot_type or shot.shot_type or shot.title,
            "generation_mode": generation_mode,
            "prompt": base_prompt,
            "edit_instruction": edit_instruction,
            "output_size": prompt.output_size or task_output_size,
            "negative_prompt": negative_prompt,
            "preserve_rules": preserve_rules,
            "keep_subject_rules": _dedupe_list([*keep_subject_rules, *preserve_rules]),
            "editable_regions": editable_regions,
            "locked_regions": locked_regions,
            "background_direction": background_direction,
            "lighting_direction": lighting_direction,
            "text_safe_zone": text_safe_zone,
            "subject_consistency_level": subject_consistency_level,
            "text_space_hint": text_space_hint,
            "composition_notes": composition_notes,
            "style_notes": style_notes,
        }
    )


def _find_prompt_by_shot_id(plan: ImagePromptPlan, shot_id: str) -> ImagePrompt:
    for prompt in plan.prompts:
        if prompt.shot_id == shot_id:
            return prompt
    raise ValueError(f"Batch prompt output is missing shot_id={shot_id}")


def _resolve_prompt_build_mode(state: WorkflowState) -> str:
    explicit_value = str(state.get("prompt_build_mode") or "").strip().lower()
    if explicit_value in {"per_shot", "batch"}:
        return explicit_value
    return get_settings().resolve_prompt_build_mode()


def _resolve_target_generation_context(state: WorkflowState, deps: WorkflowDependencies) -> dict[str, object]:
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
    explicit_value = state.get("render_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    return max(1, int(get_settings().resolve_image_edit_max_reference_images()))


def _get_copy_item_for_shot(
    *,
    shot: ShotSpec,
    copy_map: dict[str, CopyItem],
    logs: list[str] | None = None,
) -> CopyItem:
    copy_item = copy_map.get(shot.shot_id)
    if copy_item is not None:
        return copy_item
    fallback_item = build_default_copy_item_for_shot(shot)
    logger.warning("build_prompts missing copy for shot_id=%s, using fallback copy item", shot.shot_id)
    if logs is not None:
        logs.append(f"[build_prompts] warning missing copy for shot_id={shot.shot_id}, fallback applied")
    return fallback_item


def _save_all_prompt_artifacts(
    *,
    deps: WorkflowDependencies,
    task_id: str,
    prompts: list[ImagePrompt],
    shots: list[ShotSpec],
    copy_map: dict[str, CopyItem],
    layout_map: dict[str, LayoutItem],
) -> None:
    prompt_map = {prompt.shot_id: prompt for prompt in prompts}
    for shot in shots:
        prompt = prompt_map.get(shot.shot_id)
        if prompt is None:
            continue
        _save_shot_debug_artifacts(
            deps=deps,
            task_id=task_id,
            shot=shot,
            copy_item=copy_map.get(shot.shot_id) or build_default_copy_item_for_shot(shot),
            layout_item=layout_map[shot.shot_id],
            prompt=prompt,
        )


def _save_shot_debug_artifacts(
    *,
    deps: WorkflowDependencies,
    task_id: str,
    shot: ShotSpec,
    copy_item: CopyItem,
    layout_item: LayoutItem,
    prompt: ImagePrompt,
) -> None:
    base_dir = f"artifacts/shots/{shot.shot_id}"
    deps.storage.save_json_artifact(task_id, f"{base_dir}/shot.json", shot)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/copy.json", copy_item)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/layout.json", layout_item)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/prompt.json", prompt)


def _default_keep_subject_rules(product_analysis) -> list[str]:
    return _dedupe_list(
        [
            "keep the original product package body unchanged",
            "do not redesign the label artwork",
            "keep label position and size relationship stable",
            "do not change the container shape or structure ratio",
            "keep the original main colors and branding stable",
            *product_analysis.visual_identity.must_preserve,
        ]
    )


def _default_editable_regions() -> list[str]:
    return [
        "background",
        "surface and tabletop styling",
        "supporting props",
        "lighting and shadow atmosphere",
        "camera angle and crop within the planned composition",
    ]


def _default_locked_regions() -> list[str]:
    return [
        "product packaging body",
        "front label and brand mark area",
        "container opening structure",
        "overall product structure ratio",
    ]


def _default_lighting_direction(product_analysis) -> str:
    if product_analysis.visual_constraints.recommended_style_direction:
        return product_analysis.visual_constraints.recommended_style_direction[0]
    return "soft premium commercial lighting with clear package edges"


def _default_t2i_prompt(
    *,
    shot: ShotSpec,
    text_space_hint: str,
    preserve_rules: list[str],
    background_direction: str,
    lighting_direction: str,
) -> str:
    return (
        "Create a premium e-commerce product image with a realistic commercial photography style. "
        f"Shot goal: {shot.goal or shot.title}. "
        f"Scene direction: {background_direction}. "
        f"Composition direction: {shot.composition_direction or shot.composition_hint}. "
        f"Keep these identity constraints visible and stable: {', '.join(preserve_rules)}. "
        f"Lighting direction: {lighting_direction}. "
        f"Reserve a clean text-safe area in {text_space_hint} for later Chinese copy overlay."
    )


def _default_edit_instruction(
    *,
    shot: ShotSpec,
    keep_subject_rules: list[str],
    editable_regions: list[str],
    locked_regions: list[str],
    background_direction: str,
    lighting_direction: str,
    text_safe_zone: str,
    subject_consistency_level: str,
) -> str:
    return (
        "Edit the uploaded reference product image instead of redesigning the product. "
        f"Subject consistency level: {subject_consistency_level}. "
        f"Must keep: {', '.join(keep_subject_rules)}. "
        f"Locked regions: {', '.join(locked_regions)}. "
        f"Only change: {', '.join(editable_regions)}. "
        f"Background direction: {background_direction}. "
        f"Lighting direction: {lighting_direction}. "
        f"Composition target: {shot.composition_direction or shot.composition_hint}. "
        f"Leave a clean text-safe zone in {text_safe_zone} for later Chinese copy overlay."
    )


def _dedupe_list(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _resolve_layout_text_safe_zone(layout_item: LayoutItem) -> str:
    text_safe_zone = getattr(layout_item, "text_safe_zone", "")
    if text_safe_zone:
        return str(text_safe_zone)
    return infer_text_space_hint(layout_item)
