"""图片渲染节点。

文件位置：
- `src/workflows/nodes/render_images.py`

核心职责：
- 根据 preview / final 决定输出目录。
- 选择渲染参考图，并复用统一的 reference selector 规则。
- 判断当前走 `t2i` 还是 `image_edit`。
- 在 `image_edit` 模式下优先基于三层结构化 contract 组装最终执行 prompt。
- 调用图片 provider 生成图片。

节点前后关系：
- 上游节点：`build_prompts`
- 下游节点：`overlay_text`
"""

from __future__ import annotations

from pathlib import Path

from src.core.config import get_settings
from src.core.paths import get_task_generated_dir, get_task_generated_preview_dir
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.services.assets.reference_selector import ReferenceSelection, select_reference_bundle
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs


def render_images(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """执行图片生成并返回 `GenerationResult`。

    参数：
    - state：当前 workflow state，要求至少包含任务对象、兼容 prompt plan，必要时包含结构化 contract。
    - deps：依赖容器，主要使用图片 provider。

    返回：
    - dict：写回生成结果、渲染模式、参考图调试信息和日志。

    关键副作用：
    - 调用图片 provider，触发真实图片生成。
    - 在任务目录中写出预览图或生成图。
    - 追加渲染阶段调试日志，明确说明本次是 contract mode 还是 legacy fallback。
    """
    task = state["task"]
    render_mode = _resolve_render_mode(state)
    render_variant = "preview" if render_mode == "preview" else "final"
    prompt_plan = _resolve_render_prompt_plan(state, render_mode)
    output_dir = (
        Path(get_task_generated_preview_dir(task.task_id))
        if render_variant == "preview"
        else Path(get_task_generated_dir(task.task_id))
    )

    selection = _select_render_assets(state, render_mode=render_mode)
    reference_assets = selection.selected_assets
    generation_context = _resolve_generation_context(
        provider=deps.image_generation_provider,
        fallback_model_id=deps.image_model_selection.model_id if deps.image_model_selection else "-",
        reference_assets=reference_assets,
    )
    render_generation_mode = str(generation_context["generation_mode"])
    render_reference_asset_ids = list(generation_context["reference_asset_ids"])

    # image_edit 现在优先吃三层 contract；如果缺任何关键输入，才退回旧 prompt。
    execution_plan, prompt_debug_rows = _build_execution_prompt_plan(
        prompt_plan=prompt_plan,
        shot_prompt_specs=state.get("shot_prompt_specs"),
        product_lock=state.get("product_lock") or state.get("product_analysis"),
        style_architecture=state.get("style_architecture"),
        generation_mode=render_generation_mode,
    )

    logs = [
        *state.get("logs", []),
        *format_connected_contract_logs(state, node_name="render_images"),
        (
            "[render_images] start "
            f"render_mode={render_mode} "
            f"render_variant={render_variant} "
            f"render_generation_mode={render_generation_mode} "
            f"prompts={len(prompt_plan.prompts)} "
            f"provider={deps.image_provider_name or '-'} "
            f"model={generation_context['model_id']} "
            f"reference_asset_ids={render_reference_asset_ids or []}"
        ),
        (
            "[render] "
            f"mode={render_mode} "
            f"variant={render_variant} "
            f"generation_mode={render_generation_mode} "
            f"refs={render_reference_asset_ids or []} "
            f"provider={deps.image_provider_name or '-'} "
            f"model={generation_context['model_id']}"
        ),
        (
            "[render_images] reference_selection "
            f"selected_main_asset_id={selection.selected_main_asset_id or '-'} "
            f"selected_detail_asset_id={selection.selected_detail_asset_id or '-'} "
            f"selected_reference_asset_ids={selection.selected_asset_ids or []}"
        ),
        f"[render_images] selection_reason={selection.selection_reason}",
        (
            "[render_images] contract_readiness "
            f"product_lock_connected={str(bool(state.get('product_lock') or state.get('product_analysis'))).lower()} "
            f"style_architecture_connected={str(bool(state.get('style_architecture'))).lower()} "
            f"shot_prompt_specs_available_for_render={str(bool(state.get('shot_prompt_specs'))).lower()}"
        ),
    ]

    for prompt_row in prompt_debug_rows:
        logs.append(
            (
                "[render_images] prompt_contract "
                f"shot_id={prompt_row['shot_id']} "
                f"shot_type={prompt_row['shot_type']} "
                f"generation_mode={prompt_row['generation_mode']} "
                f"execution_source={prompt_row['execution_source']} "
                f"has_product_lock={str(prompt_row['has_product_lock']).lower()} "
                f"has_style_architecture={str(prompt_row['has_style_architecture']).lower()} "
                f"has_shot_prompt_spec={str(prompt_row['has_shot_prompt_spec']).lower()} "
                f"reference_asset_ids={render_reference_asset_ids or []} "
                f"text_safe_zone={prompt_row['text_safe_zone']} "
                f"must_preserve_visuals={prompt_row['must_preserve_visuals']} "
                f"must_preserve_texts={prompt_row['must_preserve_texts']} "
                f"text_anchor_source={prompt_row['text_anchor_source']} "
                f"text_anchor_status={prompt_row['text_anchor_status']} "
                f"must_not_change={prompt_row['must_not_change']} "
                f"keep_subject_rules={prompt_row['keep_subject_rules']} "
                f"primary_subject={prompt_row['primary_subject']} "
                f"secondary_subject={prompt_row['secondary_subject']} "
                f"allowed_scene_change_level={prompt_row['allowed_scene_change_level']} "
                f"forbidden_regression_pattern={prompt_row['forbidden_regression_pattern']} "
                f"editable_regions={prompt_row['editable_regions']} "
                f"editable_regions_final={prompt_row['editable_regions_final']}"
            )
        )
        logs.append(
            (
                "[render_images] execution_prompt "
                f"shot_id={prompt_row['shot_id']} "
                f"shot_type={prompt_row['shot_type']} "
                f"generation_mode={prompt_row['generation_mode']} "
                f"execution_source={prompt_row['execution_source']} "
                f"reference_asset_ids={render_reference_asset_ids or []} "
                f"prompt_summary={prompt_row['prompt_summary']}"
            )
        )

    result = deps.image_generation_provider.generate_images(
        execution_plan,
        output_dir=output_dir,
        reference_assets=reference_assets,
    )
    output_names = ", ".join(Path(image.image_path).name for image in result.images)
    logs.extend(
        [
            (
                "[render_images] completed "
                f"render_generation_mode={render_generation_mode} "
                f"count={len(result.images)} "
                f"files={output_names or '-'}"
            ),
            (
                "[render] "
                f"completed variant={render_variant} "
                f"generation_mode={render_generation_mode} "
                f"refs={render_reference_asset_ids or []} "
                f"output_dir={output_dir}"
            ),
            f"[render_images] output_dir={output_dir}",
        ]
    )
    return {
        "generation_result": result,
        "render_variant": render_variant,
        "render_mode": render_mode,
        "render_generation_mode": render_generation_mode,
        "render_reference_asset_ids": render_reference_asset_ids,
        "render_image_provider_impl": deps.image_provider_name or "-",
        "render_image_model_id": generation_context["model_id"],
        "render_selected_main_asset_id": selection.selected_main_asset_id,
        "render_selected_detail_asset_id": selection.selected_detail_asset_id,
        "render_reference_selection_reason": selection.selection_reason,
        "logs": logs,
    }


def _resolve_render_mode(state: WorkflowState) -> str:
    """解析当前运行是 preview、final 还是 full_auto。"""
    explicit_value = str(state.get("render_mode") or "").strip().lower()
    if explicit_value in {"preview", "final", "full_auto"}:
        return explicit_value
    return get_settings().resolve_render_mode()


def _resolve_render_prompt_plan(state: WorkflowState, render_mode: str) -> ImagePromptPlan:
    """preview 阶段只截取前几张图并调整输出尺寸。"""
    base_plan = state["image_prompt_plan"]
    if render_mode != "preview":
        return base_plan
    settings = get_settings()
    preview_count = max(1, min(settings.preview_shot_count, len(base_plan.prompts)))
    preview_prompts = [
        prompt.model_copy(update={"output_size": settings.preview_output_size})
        for prompt in base_plan.prompts[:preview_count]
    ]
    return ImagePromptPlan(generation_mode=base_plan.generation_mode, prompts=preview_prompts)


def _resolve_render_max_reference_images(state: WorkflowState, *, render_mode: str) -> int:
    """preview 和 final 默认参考图张数不同。"""
    explicit_value = state.get("render_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    if render_mode == "preview":
        return 1
    return 2


def _select_render_assets(state: WorkflowState, *, render_mode: str) -> ReferenceSelection:
    """渲染阶段复用统一参考图选择器，但数量按 preview/final 区分。"""
    return select_reference_bundle(
        state.get("assets", []),
        max_images=_resolve_render_max_reference_images(state, render_mode=render_mode),
    )


def _resolve_generation_context(*, provider, fallback_model_id: str, reference_assets: list) -> dict[str, object]:
    """从 provider 适配层读取实际 generation mode 和模型信息。"""
    resolver = getattr(provider, "resolve_generation_context", None)
    if callable(resolver):
        context = resolver(reference_assets=reference_assets)
        return {
            "generation_mode": context.generation_mode,
            "model_id": context.model_id,
            "reference_asset_ids": context.reference_asset_ids,
        }
    return {
        "generation_mode": "image_edit" if reference_assets else "t2i",
        "model_id": fallback_model_id,
        "reference_asset_ids": [asset.asset_id for asset in reference_assets],
    }


def _build_execution_prompt_plan(
    *,
    prompt_plan: ImagePromptPlan,
    shot_prompt_specs,
    product_lock,
    style_architecture,
    generation_mode: str,
) -> tuple[ImagePromptPlan, list[dict[str, object]]]:
    """把结构化 contract 组装成最终执行 prompt。

    设计原则：
    - `t2i` 继续兼容旧 prompt plan。
    - `image_edit` 时优先按三层 contract 组装执行 prompt。
    - 如果缺少 `product_lock / style_architecture / shot_prompt_spec` 任何一项，就回退到旧 prompt。
    """
    spec_map = {
        spec.shot_id: spec
        for spec in getattr(shot_prompt_specs, "specs", [])
    }
    prompts: list[ImagePrompt] = []
    debug_rows: list[dict[str, object]] = []

    for prompt in prompt_plan.prompts:
        spec = spec_map.get(prompt.shot_id)
        identity_rule_groups = _resolve_identity_rule_groups(
            product_lock=product_lock,
            spec=spec,
        )
        clean_keep_subject_rules = _flatten_identity_rule_groups(identity_rule_groups)
        if not clean_keep_subject_rules:
            clean_keep_subject_rules = _coerce_rule_strings(getattr(prompt, "keep_subject_rules", []) or [])
        clean_editable_regions = _resolve_final_editable_regions(
            prompt=prompt,
            product_lock=product_lock,
            spec=spec,
        )
        shot_summary = _build_shot_edit_summary(
            prompt=prompt,
            spec=spec,
            editable_regions_final=clean_editable_regions,
        )
        prompt_text, execution_source = _resolve_prompt_text_for_generation(
            prompt=prompt,
            spec=spec,
            product_lock=product_lock,
            style_architecture=style_architecture,
            generation_mode=generation_mode,
            identity_rule_groups=identity_rule_groups,
            editable_regions_final=clean_editable_regions,
            shot_summary=shot_summary,
        )
        updated_prompt = _build_updated_prompt(
            prompt=prompt,
            prompt_text=prompt_text,
            generation_mode=generation_mode,
            spec=spec,
        )
        prompts.append(updated_prompt)
        debug_rows.append(
            {
                "shot_id": prompt.shot_id,
                "shot_type": prompt.shot_type,
                "generation_mode": generation_mode,
                "execution_source": execution_source,
                "has_product_lock": product_lock is not None,
                "has_style_architecture": style_architecture is not None,
                "has_shot_prompt_spec": spec is not None,
                "text_safe_zone": _resolve_text_safe_zone(prompt=prompt, spec=spec),
                "keep_subject_rules": clean_keep_subject_rules,
                "must_preserve_visuals": identity_rule_groups["must_preserve_visuals"],
                "must_preserve_texts": identity_rule_groups["must_preserve_texts"],
                "text_anchor_source": str(getattr(product_lock, "text_anchor_source", "") or "none"),
                "text_anchor_status": str(getattr(product_lock, "text_anchor_status", "") or "unreadable"),
                "must_not_change": identity_rule_groups["must_not_change"],
                "editable_regions": clean_editable_regions,
                "editable_regions_final": clean_editable_regions,
                "primary_subject": shot_summary["primary_subject"],
                "secondary_subject": shot_summary["secondary_subject"],
                "allowed_scene_change_level": shot_summary["allowed_scene_change_level"],
                "forbidden_regression_pattern": shot_summary["forbidden_regression_pattern"],
                "prompt_summary": _summarize_prompt_text(prompt_text),
            }
        )

    return prompt_plan.model_copy(update={"generation_mode": generation_mode, "prompts": prompts}), debug_rows


def _resolve_prompt_text_for_generation(
    *,
    prompt: ImagePrompt,
    spec,
    product_lock,
    style_architecture,
    generation_mode: str,
    identity_rule_groups: dict[str, list[str]],
    editable_regions_final: list[str],
    shot_summary: dict[str, object],
) -> tuple[str, str]:
    """决定当前 shot 最终使用 contract mode 还是 legacy fallback。"""
    if generation_mode != "image_edit":
        return prompt.prompt, "legacy_t2i_prompt"
    if product_lock is None or style_architecture is None or spec is None:
        return _resolve_legacy_image_edit_prompt(prompt), "legacy_prompt_fallback"
    return (
        _assemble_image_edit_contract_prompt(
            product_lock=product_lock,
            style_architecture=style_architecture,
            spec=spec,
            text_safe_zone=prompt.text_safe_zone or prompt.text_space_hint,
            identity_rule_groups=identity_rule_groups,
            editable_regions_final=editable_regions_final,
            shot_summary=shot_summary,
        ),
        "image_edit_contract_mode",
    )


def _build_updated_prompt(*, prompt: ImagePrompt, prompt_text: str, generation_mode: str, spec) -> ImagePrompt:
    """把解析后的执行 prompt 写回兼容 prompt 对象。"""
    negative_prompt = prompt.negative_prompt
    if spec is not None and getattr(spec, "negative_prompt", None):
        negative_prompt = list(spec.negative_prompt)
    return prompt.model_copy(
        update={
            "generation_mode": generation_mode,
            "prompt": prompt_text if generation_mode == "t2i" else prompt.prompt,
            "edit_instruction": prompt_text if generation_mode == "image_edit" else prompt.edit_instruction,
            "negative_prompt": negative_prompt,
        }
    )


def _resolve_legacy_image_edit_prompt(prompt: ImagePrompt) -> str:
    """缺少结构化 contract 时，回退到旧的 image_edit prompt。"""
    if prompt.edit_instruction:
        return prompt.edit_instruction
    return prompt.prompt


def _resolve_text_safe_zone(*, prompt: ImagePrompt, spec) -> str:
    """统一解析日志和执行 prompt 使用的文字安全区。"""
    return (
        prompt.text_safe_zone
        or prompt.text_space_hint
        or (spec.layout_constraints.preferred_text_safe_zone if spec is not None else "")
    )


def _assemble_image_edit_contract_prompt(
    *,
    product_lock,
    style_architecture,
    spec,
    text_safe_zone: str,
    identity_rule_groups: dict[str, list[str]],
    editable_regions_final: list[str],
    shot_summary: dict[str, object],
) -> str:
    """按更适合 image_edit 的顺序组装执行 prompt，先强调分镜差异，再落商品锁定。"""
    return "\n".join(
        [
            "Edit mode: reference-image commercial generation.",
            "",
            "[Task Type And Current Shot Objective]",
            "Task type: image_edit commercial product generation.",
            f"Current shot type: {spec.shot_type}.",
            f"Current shot goal: {spec.goal}.",
            f"Allowed scene change level: {shot_summary['allowed_scene_change_level']}.",
            "",
            "[Shot Differentiation Rules]",
            *shot_summary["differentiation_lines"],
            "",
            "[Subject Hierarchy]",
            f"Primary subject: {shot_summary['primary_subject']}.",
            f"Secondary subject: {shot_summary['secondary_subject']}.",
            *shot_summary["subject_hierarchy_lines"],
            "",
            "[Allowed Editable Regions]",
            f"Editable regions final: {'; '.join(editable_regions_final)}.",
            f"Editable region strategy: {spec.render_constraints.editable_region_strategy}.",
            "Only change scene, crop, props, lighting, or non-identity elements inside the allowed editable regions.",
            "",
            "[Product Identity Lock]",
            "Keep original product identity unchanged while making only the shot-specific scene changes above.",
            *_build_product_lock_lines(identity_rule_groups),
            "",
            "[Global Style Architecture]",
            f"Style theme: {style_architecture.style_theme}.",
            *_format_named_lines("Color strategy", style_architecture.color_strategy),
            *_format_named_lines("Lighting strategy", style_architecture.lighting_strategy),
            *_format_named_lines("Lens strategy", style_architecture.lens_strategy),
            *_format_named_lines("Prop system", style_architecture.prop_system),
            *_format_named_lines("Background strategy", style_architecture.background_strategy),
            *_format_named_lines("Text strategy", style_architecture.text_strategy),
            "",
            "[Layout And Text Safe Zone]",
            *_build_layout_lines(spec, text_safe_zone),
            "",
            "[Negative Rules]",
            *_build_negative_lines(style_architecture, spec),
        ]
    ).strip()


def _build_product_lock_lines(identity_rule_groups: dict[str, list[str]]) -> list[str]:
    """把商品锁定整理成三组稳定规则，避免重复堆叠导致 shot differentiation 被淹没。"""
    lines: list[str] = []
    if identity_rule_groups["must_preserve_visuals"]:
        lines.append(f"Must preserve visuals: {'; '.join(identity_rule_groups['must_preserve_visuals'])}.")
    if identity_rule_groups["must_preserve_texts"]:
        lines.append(f"Must preserve texts: {'; '.join(identity_rule_groups['must_preserve_texts'])}.")
    if identity_rule_groups["must_not_change"]:
        lines.append(f"Must not change: {'; '.join(identity_rule_groups['must_not_change'])}.")
    return lines or ["Must preserve visuals: package structure; label hierarchy; dominant product color."]


def _resolve_identity_rule_groups(*, product_lock, spec) -> dict[str, list[str]]:
    """把商品锁定拆成视觉、文本和禁止变化三组，供 prompt 与日志共用。"""
    product_visuals = _coerce_rule_strings(getattr(product_lock, "locked_elements", []) or [])
    visual_identity = getattr(product_lock, "visual_identity", None)
    if visual_identity is not None:
        product_visuals = _merge_unique_strings(product_visuals, _coerce_rule_strings(getattr(visual_identity, "must_preserve", []) or []))
    visual_overrides = _coerce_rule_strings(spec.product_lock.must_preserve) if spec is not None and getattr(spec, "product_lock", None) is not None else []
    preserve_texts = _merge_unique_strings(
        _coerce_rule_strings(getattr(product_lock, "must_preserve_texts", []) or []),
        _coerce_rule_strings(spec.product_lock.must_preserve_texts) if spec is not None and getattr(spec, "product_lock", None) is not None else [],
    )
    must_not_change = _coerce_rule_strings(spec.product_lock.must_not_change) if spec is not None and getattr(spec, "product_lock", None) is not None else []
    if not must_not_change:
        must_not_change = _coerce_rule_strings(
            [
                getattr(product_lock, "package_type", ""),
                getattr(product_lock, "label_structure", ""),
                getattr(product_lock, "primary_color", ""),
                getattr(product_lock, "material", ""),
            ]
        )
    return {
        "must_preserve_visuals": _merge_unique_strings(product_visuals, visual_overrides),
        "must_preserve_texts": preserve_texts,
        "must_not_change": must_not_change,
    }


def _flatten_identity_rule_groups(identity_rule_groups: dict[str, list[str]]) -> list[str]:
    """兼容旧 keep_subject_rules 字段，但内部已经改成三组清晰规则来源。"""
    return _merge_unique_strings(
        identity_rule_groups["must_preserve_visuals"],
        [f"must preserve texts: {item}" for item in identity_rule_groups["must_preserve_texts"]],
        [f"must not change: {item}" for item in identity_rule_groups["must_not_change"]],
    )


def _resolve_final_editable_regions(*, prompt: ImagePrompt, product_lock, spec) -> list[str]:
    """统一生成最终 editable_regions，保证 image_edit 日志和执行 prompt 都不再频繁为空。"""
    shot_type = getattr(spec, "shot_type", "") or prompt.shot_type
    spec_regions = _coerce_rule_strings(spec.product_lock.editable_regions) if spec is not None and getattr(spec, "product_lock", None) is not None else []
    return _merge_unique_strings(
        _editable_region_defaults_for_shot_type(shot_type),
        [_normalize_editable_region_name(item) for item in spec_regions],
        [_normalize_editable_region_name(item) for item in _coerce_rule_strings(getattr(prompt, "editable_regions", []) or [])],
        [_normalize_editable_region_name(item) for item in _coerce_rule_strings(getattr(product_lock, "editable_elements", []) or [])],
    )


def _build_shot_edit_summary(*, prompt: ImagePrompt, spec, editable_regions_final: list[str]) -> dict[str, object]:
    """抽取当前 shot 的执行摘要，供最终 prompt 前置强调分镜变化。"""
    if spec is None:
        return {
            "primary_subject": prompt.shot_type or "uploaded product reference",
            "secondary_subject": "supporting scene only",
            "allowed_scene_change_level": "fallback_from_legacy_prompt",
            "forbidden_regression_pattern": "generic hero packshot",
            "differentiation_lines": ["Fallback to legacy prompt for this shot."],
            "subject_hierarchy_lines": [f"Scene edits may appear in: {'; '.join(editable_regions_final)}."],
        }
    primary_subject, secondary_subject, reference_anchor_line, subject_rule_lines = _parse_subject_prompt(spec.subject_prompt)
    differentiation_lines = [
        f"This shot must not regress into: {_resolve_forbidden_regression_pattern(spec, prompt.shot_type)}.",
        f"Reference image priority: {spec.render_constraints.reference_image_priority}.",
        f"Consistency strength: {spec.render_constraints.consistency_strength}.",
        f"Product lock level: {spec.render_constraints.product_lock_level}.",
        *[f"- {line}" for line in subject_rule_lines],
        f"- Composition direction: {_clean_prompt_fragment(spec.composition_prompt)}.",
        f"- Background direction: {_clean_prompt_fragment(spec.background_prompt)}.",
        f"- Lighting direction: {_clean_prompt_fragment(spec.lighting_prompt)}.",
        f"- Quality direction: {_clean_prompt_fragment(spec.quality_prompt)}.",
    ]
    subject_hierarchy_lines: list[str] = []
    if reference_anchor_line:
        subject_hierarchy_lines.append(f"Reference anchor: {reference_anchor_line}.")
    subject_hierarchy_lines.append(f"Scene edits may appear in: {'; '.join(editable_regions_final)}.")
    return {
        "primary_subject": primary_subject or "uploaded product reference",
        "secondary_subject": secondary_subject or "supporting scene only",
        "allowed_scene_change_level": _resolve_allowed_scene_change_level(spec),
        "forbidden_regression_pattern": _resolve_forbidden_regression_pattern(spec, prompt.shot_type),
        "differentiation_lines": differentiation_lines,
        "subject_hierarchy_lines": subject_hierarchy_lines,
    }


def _coerce_rule_strings(values) -> list[str]:
    """把规则列表清洗成干净字符串，避免把 tuple、dict items 或对象直接串进 prompt/log。"""
    cleaned: list[str] = []
    if isinstance(values, str):
        values = [values]
    for value in values or []:
        if isinstance(value, tuple) and len(value) == 2:
            key, raw = value
            if isinstance(raw, (list, tuple, set)):
                for item in raw:
                    normalized = f"{key}: {str(item).strip()}".strip()
                    if normalized and normalized not in cleaned:
                        cleaned.append(normalized)
                continue
            value = f"{key}: {raw}"
        elif isinstance(value, dict):
            for key, raw in value.items():
                normalized = f"{key}: {str(raw).strip()}".strip()
                if normalized and normalized not in cleaned:
                    cleaned.append(normalized)
            continue

        normalized = str(value).strip()
        if not normalized:
            continue
        if normalized.startswith("(") and normalized.endswith(")"):
            # 这类字符串通常来自错误地把 tuple 直接做了 str()，对调试和 prompt 都是噪声。
            normalized = normalized.strip("()")
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _editable_region_defaults_for_shot_type(shot_type: str) -> list[str]:
    """按 shot_type 提供最小可编辑区域兜底，保证 image_edit 有足够变化空间。"""
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


def _parse_subject_prompt(subject_prompt: str) -> tuple[str, str, str, list[str]]:
    """从结构化 subject_prompt 里提取主次主体和剩余执行规则。"""
    primary_subject = ""
    secondary_subject = ""
    reference_anchor_line = ""
    rule_lines: list[str] = []
    for raw in str(subject_prompt or "").split("."):
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("primary subject:"):
            primary_subject = line.split(":", maxsplit=1)[1].strip()
            continue
        if lower.startswith("secondary subject:"):
            secondary_subject = line.split(":", maxsplit=1)[1].strip()
            continue
        if lower.startswith("use the uploaded"):
            reference_anchor_line = line
            continue
        rule_lines.append(line)
    return primary_subject, secondary_subject, reference_anchor_line, rule_lines


def _resolve_allowed_scene_change_level(spec) -> str:
    """把 product_lock_level 转成更直观的 scene change 摘要。"""
    if spec is None:
        return "fallback_from_legacy_prompt"
    mapping = {
        "strong_product_lock": "low_scene_change_locked_product",
        "medium_product_lock": "moderate_scene_change_keep_package_readable",
        "anchor_only_product_lock": "high_scene_change_package_as_brand_anchor",
    }
    return mapping.get(spec.render_constraints.product_lock_level, "moderate_scene_change_keep_package_readable")


def _resolve_forbidden_regression_pattern(spec, shot_type: str) -> str:
    """输出每个 shot 不应退化回去的典型错误形态。"""
    current_shot_type = getattr(spec, "shot_type", "") or shot_type
    mapping = {
        "hero_brand": "detail crop or prop-led auxiliary scene",
        "carry_action": "isolated hero packshot without carry gesture",
        "open_box_structure": "closed package hero frame",
        "package_detail": "full front-facing hero packshot",
        "label_or_material_detail": "full package hero view",
        "package_with_leaf_hint": "isolated studio packshot with no leaf cue",
        "dry_leaf_detail": "package-only composition or hero packshot",
        "tea_soup_experience": "package-only composition without visible brewed tea",
        "lifestyle_or_brewing_context": "isolated studio packshot with token props only",
        "package_in_brewing_context": "isolated packshot with decorative props only",
    }
    return mapping.get(current_shot_type, "generic hero packshot")


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    """保持原始顺序合并去重，避免日志和 prompt 反复输出同义内容。"""
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


def _clean_prompt_fragment(value) -> str:
    """清洗单个 prompt 片段，尽量把 tuple repr / pydantic repr 转回可读文本。"""
    if value is None:
        return ""
    if isinstance(value, tuple) and len(value) == 2:
        return f"{value[0]}: {value[1]}"
    text = str(value).strip()
    if not text:
        return ""
    replacements = {
        "('preferred_text_safe_zone', ": "preferred_text_safe_zone: ",
        '("preferred_text_safe_zone", ': "preferred_text_safe_zone: ",
        "('avoid_overlap_with_subject', ": "avoid_overlap_with_subject: ",
        '("avoid_overlap_with_subject", ': "avoid_overlap_with_subject: ",
        "('max_text_layers', ": "max_text_layers: ",
        '("max_text_layers", ': "max_text_layers: ",
        "('subject_placement_hint', ": "subject_placement_hint: ",
        '("subject_placement_hint", ': "subject_placement_hint: ",
        "title_role='": "title_role=",
        "subtitle_role='": "subtitle_role=",
        "bullet_role='": "bullet_role=",
        "cta_role='": "cta_role=",
        "')": "",
        '")': "",
        "', '": "; ",
        '", "': "; ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = text.replace("'", "").replace('"', "")
    text = " ".join(text.split())
    return text


def _format_named_lines(title: str, values: list[str]) -> list[str]:
    """把 strategy 列表变成稳定的分行结构。"""
    if not values:
        return [f"{title}: none."]
    return [f"{title}: {value}." for value in values]


def _build_layout_lines(spec, text_safe_zone: str) -> list[str]:
    """把布局约束转成给图模型的留白指令。"""
    resolved_text_safe_zone = _clean_prompt_fragment(
        text_safe_zone or spec.layout_constraints.preferred_text_safe_zone or "top_right"
    )
    lines = [
        f"Leave clean visual space for copy at: {resolved_text_safe_zone}.",
        f"Avoid overlap with subject: {str(spec.layout_constraints.avoid_overlap_with_subject).lower()}.",
        f"Max text layers reserved: {spec.layout_constraints.max_text_layers}.",
    ]
    if spec.layout_constraints.subject_placement_hint:
        lines.append(f"Subject placement hint: {_clean_prompt_fragment(spec.layout_constraints.subject_placement_hint)}.")
    copy_intent_summary = _build_copy_intent_summary(spec)
    if copy_intent_summary:
        lines.append(f"Copy intent: {copy_intent_summary}.")
    return lines


def _build_render_constraint_lines(spec) -> list[str]:
    """把 render constraints 转成稳定段落，保留 shot 分层约束。"""
    lines = [
        f"Generation mode target: {spec.render_constraints.generation_mode}.",
        f"Reference image priority: {spec.render_constraints.reference_image_priority}.",
        f"Consistency strength: {spec.render_constraints.consistency_strength}.",
        f"Product lock level: {spec.render_constraints.product_lock_level}.",
        f"Editable region strategy: {spec.render_constraints.editable_region_strategy}.",
        f"Allow human presence: {str(spec.render_constraints.allow_human_presence).lower()}.",
        f"Allow hand only: {str(spec.render_constraints.allow_hand_only).lower()}.",
    ]
    return lines


def _build_copy_intent_summary(spec) -> str:
    """把 copy_intent 清洗成稳定摘要，避免把 pydantic repr 直接写进 prompt。"""
    parts = [
        f"title_role={_clean_prompt_fragment(spec.copy_intent.title_role)}" if spec.copy_intent.title_role else "",
        f"subtitle_role={_clean_prompt_fragment(spec.copy_intent.subtitle_role)}" if spec.copy_intent.subtitle_role else "",
        f"bullet_role={_clean_prompt_fragment(spec.copy_intent.bullet_role)}" if spec.copy_intent.bullet_role else "",
        f"cta_role={_clean_prompt_fragment(spec.copy_intent.cta_role)}" if spec.copy_intent.cta_role else "",
    ]
    return "; ".join(part for part in parts if part)


def _build_negative_lines(style_architecture, spec) -> list[str]:
    """合并组级和单张级 negative 约束。"""
    negatives = [
        *list(getattr(style_architecture, "global_negative_rules", []) or []),
        *list(getattr(spec, "negative_prompt", []) or []),
    ]
    if not negatives:
        return ["Avoid redesigning the package, label, or product identity."]
    return [f"- {item}" for item in negatives]


def _summarize_prompt_text(prompt: str, limit: int = 220) -> str:
    """截断日志中的 prompt 摘要，避免日志过长。"""
    normalized = " ".join(str(prompt).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."
