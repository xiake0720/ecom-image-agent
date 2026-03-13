"""图片提示词构建节点。"""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutItem
from src.domain.shot_plan import ShotSpec
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
    """生成并落盘图片提示词计划。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[build_prompts] 开始构建图片提示词，模式={deps.text_provider_mode}。"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    template_name = "build_image_prompts.md"
    template_source = describe_prompt_source(template_name)
    prompt_build_mode = _resolve_prompt_build_mode(state)
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
        prompt_version="mock-image-prompts-v1" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "prompt_build_mode": prompt_build_mode,
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "shot_plan_hash": hash_state_payload(state["shot_plan"]),
            "copy_plan_hash": hash_state_payload(state["copy_plan"]),
            "layout_plan_hash": hash_state_payload(state["layout_plan"]),
            "policy_signature_hash": hash_state_payload(policy_signature),
        },
    )
    logger.info(
        "build_prompts 当前为纯结构化推理模式，未向文本模型发送图片输入，模板来源=%s，prompt_build_mode=%s",
        template_source,
        prompt_build_mode,
    )
    logs.extend(
        [
            "[build_prompts] 当前为纯结构化推理模式，仅基于 task、product_analysis、shot、copy、layout 生成提示词。",
            "[build_prompts] 当前未向模型发送图片输入；真正的商品参考图会在 render_images 节点发送给图片模型。",
            f"[build_prompts] 当前使用的模板来源文件：{template_source}。",
            f"[build_prompts] 当前 prompt build mode：{prompt_build_mode}。",
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
                    f"[build_prompts] cache hit，命中节点缓存，key={cache_key}。",
                    f"[build_prompts] 已从缓存恢复 {prompt_build_mode} 模式的 aggregate 与 per-shot prompt 产物。",
                ]
            )
            return {"image_prompt_plan": cached_plan, "logs": logs}
        logs.append(f"[build_prompts] cache miss，未命中节点缓存，key={cache_key}。")
    elif is_force_rerun(state):
        logs.append("[build_prompts] ignore cache，已忽略缓存并强制重跑。")

    if prompt_build_mode == "batch":
        plan = _build_prompts_batch_mode(state, deps, logs, template_name)
    else:
        plan = _build_prompts_per_shot_mode(state, deps, logs, template_name)

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
            f"[build_prompts] 图片提示词构建完成，数量={len(plan.prompts)}，shot_ids={prompt_shot_ids or '-'}。",
            f"[build_prompts] 当前实际规划模型={deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}。",
            "[build_prompts] 已写入 image_prompt_plan.json。",
        ]
    )
    return {"image_prompt_plan": plan, "logs": logs}


def _build_prompts_per_shot_mode(
    state: WorkflowState,
    deps: WorkflowDependencies,
    logs: list[str],
    template_name: str,
) -> ImagePromptPlan:
    task = state["task"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    logs.append("[build_prompts] 当前使用 per_shot 模式，按单张 shot 逐次调用文本模型。")
    if deps.text_provider_mode == "real":
        prompts = []
        total_shots = len(state["shot_plan"].shots)
        for index, shot in enumerate(state["shot_plan"].shots, start=1):
            copy_item = copy_map[shot.shot_id]
            layout_item = layout_map[shot.shot_id]
            prompt_input = _build_single_shot_prompt_input(
                task=task,
                product_analysis=state["product_analysis"],
                shot=shot,
                copy_item=copy_item,
                layout_item=layout_item,
            )
            logs.append(f"[build_prompts] 当前使用 per_shot 模式，正在生成第 {index}/{total_shots} 张：{shot.shot_id}。")
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
                )
            )
        return ImagePromptPlan(prompts=prompts)

    prompts = []
    total_shots = len(state["shot_plan"].shots)
    for index, shot in enumerate(state["shot_plan"].shots, start=1):
        copy_item = copy_map[shot.shot_id]
        layout_item = layout_map[shot.shot_id]
        logs.append(f"[build_prompts] 当前使用 per_shot 模式，正在生成第 {index}/{total_shots} 张：{shot.shot_id}。")
        prompts.append(
            _build_mock_prompt(
                task=task,
                product_analysis=state["product_analysis"],
                shot=shot,
                copy_item=copy_item,
                layout_item=layout_item,
            )
        )
    return ImagePromptPlan(prompts=prompts)


def _build_prompts_batch_mode(
    state: WorkflowState,
    deps: WorkflowDependencies,
    logs: list[str],
    template_name: str,
) -> ImagePromptPlan:
    task = state["task"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    logs.append("[build_prompts] 当前使用 batch 模式，一次调用生成整组 ImagePromptPlan。")
    if deps.text_provider_mode == "real":
        batch_prompt_input = _build_batch_prompt_input(
            task=task,
            product_analysis=state["product_analysis"],
            shots=state["shot_plan"].shots,
            copy_map=copy_map,
            layout_map=layout_map,
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
                )
            )
        return ImagePromptPlan(prompts=normalized_prompts)

    prompts = []
    for shot in state["shot_plan"].shots:
        prompts.append(
            _build_mock_prompt(
                task=task,
                product_analysis=state["product_analysis"],
                shot=shot,
                copy_item=copy_map[shot.shot_id],
                layout_item=layout_map[shot.shot_id],
            )
        )
    return ImagePromptPlan(prompts=prompts)


def _build_single_shot_prompt_input(
    *,
    task,
    product_analysis,
    shot: ShotSpec,
    copy_item,
    layout_item: LayoutItem,
) -> str:
    prompt_context = build_build_prompts_context(
        task=task,
        product_analysis=product_analysis,
        shot=shot,
        copy_item=copy_item,
        layout_item=layout_item,
    )
    prompt_context["build_prompt_rules"] = {
        "mode": "structured_reasoning_only",
        "prompt_build_mode": "per_shot",
        "image_input_sent_to_model": False,
        "reference_image_stage": "render_images",
        "text_space_hint": infer_text_space_hint(layout_item),
        "text_space_intent": "正式中文广告文案将由 Pillow 后贴字完成；当前图片必须预留干净、明亮、可读的文字区。",
        "preserve_priority": product_analysis.visual_identity.must_preserve,
        "negative_prompt_must_cover": DEFAULT_NEGATIVE_PROMPTS,
    }
    return (
        "当前处于 build_prompts 节点，只能基于结构化结果为单张图生成提示词。\n"
        "注意：本节点不会向模型发送任何图片输入；真实商品参考图会在 render_images 节点再发送给图片模型。\n"
        "这不是整组图任务，不要输出多张图，不要写自由解释。\n\n"
        f"{dump_pretty(prompt_context)}"
    )


def _build_batch_prompt_input(
    *,
    task,
    product_analysis,
    shots: list[ShotSpec],
    copy_map: dict[str, object],
    layout_map: dict[str, LayoutItem],
) -> str:
    batch_context = {
        "task": task,
        "product_analysis": product_analysis,
        "build_prompt_rules": {
            "mode": "structured_reasoning_only",
            "prompt_build_mode": "batch",
            "image_input_sent_to_model": False,
            "reference_image_stage": "render_images",
            "output_schema": "ImagePromptPlan",
            "must_keep_shot_ids": [shot.shot_id for shot in shots],
            "negative_prompt_must_cover": DEFAULT_NEGATIVE_PROMPTS,
        },
        "shots": [
            build_build_prompts_context(
                task=task,
                product_analysis=product_analysis,
                shot=shot,
                copy_item=copy_map[shot.shot_id],
                layout_item=layout_map[shot.shot_id],
            )
            for shot in shots
        ],
    }
    return (
        "当前处于 build_prompts 节点，需要一次性为整组 shots 生成 ImagePromptPlan。\n"
        "注意：本节点不会向模型发送任何图片输入；真实商品参考图会在 render_images 节点再发送给图片模型。\n"
        "你必须仅基于结构化输入，为每个给定 shot_id 生成对应的 ImagePrompt，不能新增或遗漏 shot。\n"
        "不要输出自由解释，只输出符合 ImagePromptPlan schema 的 JSON。\n\n"
        f"{dump_pretty(batch_context)}"
    )


def _build_mock_prompt(
    *,
    task,
    product_analysis,
    shot: ShotSpec,
    copy_item,
    layout_item: LayoutItem,
) -> ImagePrompt:
    prompt_context = build_build_prompts_context(
        task=task,
        product_analysis=product_analysis,
        shot=shot,
        copy_item=copy_item,
        layout_item=layout_item,
    )
    return _normalize_image_prompt(
        task_output_size=task.output_size,
        shot=shot,
        layout_item=layout_item,
        product_analysis=product_analysis,
        prompt=ImagePrompt(
            shot_id=shot.shot_id,
            shot_type=shot.shot_type,
            prompt=(
                "Use the uploaded reference product as the exact hero subject, preserve the original package silhouette, "
                "label placement and key identity points, keep the package basically unchanged, "
                f"render a premium e-commerce shot for {shot.title}, "
                f"follow category policy and platform policy: {dump_pretty(prompt_context['category_policy'])}, "
                f"{dump_pretty(prompt_context['platform_policy'])}, "
                f"scene and composition: {shot.scene_direction or shot.purpose}, {shot.composition_direction or shot.composition_hint}, "
                f"reserve clean text space in the {infer_text_space_hint(layout_item)} area, restrained props, realistic premium lighting."
            ),
            negative_prompt=DEFAULT_NEGATIVE_PROMPTS,
            output_size=task.output_size,
            preserve_rules=product_analysis.visual_identity.must_preserve,
            text_space_hint=infer_text_space_hint(layout_item),
            composition_notes=[
                shot.composition_hint,
                *(prompt_context["shot_type_policy"].get("composition_defaults", [])),
            ],
            style_notes=[
                prompt_context["style_anchor_summary"],
                *(prompt_context["platform_policy"].get("commercial_focus", [])),
            ],
        ),
    )


def _normalize_image_prompt(
    *,
    task_output_size: str,
    shot: ShotSpec,
    layout_item: LayoutItem,
    product_analysis,
    prompt: ImagePrompt,
) -> ImagePrompt:
    preserve_rules = prompt.preserve_rules or product_analysis.visual_identity.must_preserve
    text_space_hint = prompt.text_space_hint or infer_text_space_hint(layout_item)
    composition_notes = prompt.composition_notes or [
        shot.composition_hint,
        shot.composition_direction or "主体清晰稳定，留白区域干净可读",
    ]
    style_notes = prompt.style_notes or [
        *product_analysis.visual_constraints.recommended_style_direction[:3],
        "高端电商商业摄影风格",
    ]
    negative_prompt = prompt.negative_prompt or DEFAULT_NEGATIVE_PROMPTS
    return prompt.model_copy(
        update={
            "shot_id": prompt.shot_id or shot.shot_id,
            "shot_type": prompt.shot_type or shot.shot_type or shot.title,
            "output_size": prompt.output_size or task_output_size,
            "negative_prompt": negative_prompt,
            "preserve_rules": preserve_rules,
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


def _save_all_prompt_artifacts(
    *,
    deps: WorkflowDependencies,
    task_id: str,
    prompts: list[ImagePrompt],
    shots: list[ShotSpec],
    copy_map: dict[str, object],
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
            copy_item=copy_map[shot.shot_id],
            layout_item=layout_map[shot.shot_id],
            prompt=prompt,
        )


def _save_shot_debug_artifacts(
    *,
    deps: WorkflowDependencies,
    task_id: str,
    shot: ShotSpec,
    copy_item,
    layout_item: LayoutItem,
    prompt: ImagePrompt,
) -> None:
    base_dir = f"artifacts/shots/{shot.shot_id}"
    deps.storage.save_json_artifact(task_id, f"{base_dir}/shot.json", shot)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/copy.json", copy_item)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/layout.json", layout_item)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/prompt.json", prompt)
