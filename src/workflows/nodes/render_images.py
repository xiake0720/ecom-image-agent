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
                f"keep_subject_rules={prompt_row['keep_subject_rules']} "
                f"editable_regions={prompt_row['editable_regions']}"
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
        clean_keep_subject_rules = _resolve_clean_keep_subject_rules(
            prompt=prompt,
            product_lock=product_lock,
            spec=spec,
        )
        clean_editable_regions = _resolve_clean_editable_regions(
            prompt=prompt,
            product_lock=product_lock,
            spec=spec,
        )
        prompt_text, execution_source = _resolve_prompt_text_for_generation(
            prompt=prompt,
            spec=spec,
            product_lock=product_lock,
            style_architecture=style_architecture,
            generation_mode=generation_mode,
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
                "editable_regions": clean_editable_regions,
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


def _assemble_image_edit_contract_prompt(*, product_lock, style_architecture, spec, text_safe_zone: str) -> str:
    """按三层 contract 组装 image_edit 执行 prompt。

    为什么要显式分块：
    - 让 image_edit 更像“编辑指令”，而不是文生图散文。
    - 便于日志里快速判断是 product lock、style architecture 还是 shot spec 出问题。
    - 便于未来替换 provider 时继续复用上游 contract。
    """
    return "\n".join(
        [
            "Edit mode: reference-image commercial generation.",
            "",
            "[Product Identity Lock]",
            "Keep original product identity unchanged.",
            *_build_product_lock_lines(product_lock, spec),
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
            "[Current Shot Direction]",
            f"Shot goal: {spec.goal}.",
            f"Subject direction: {spec.subject_prompt}.",
            f"Package appearance direction: {spec.package_appearance_prompt}.",
            f"Composition direction: {spec.composition_prompt}.",
            f"Background direction: {spec.background_prompt}.",
            f"Lighting direction: {spec.lighting_prompt}.",
            f"Style direction: {spec.style_prompt}.",
            f"Quality direction: {spec.quality_prompt}.",
            "",
            "[Layout And Text Safe Zone]",
            *_build_layout_lines(spec, text_safe_zone),
            "",
            "[Render Constraints]",
            *_build_render_constraint_lines(spec),
            "",
            "[Negative Rules]",
            *_build_negative_lines(style_architecture, spec),
        ]
    ).strip()


def _build_product_lock_lines(product_lock, spec) -> list[str]:
    """把 product lock 转成稳定的编辑约束段落。"""
    lines: list[str] = []
    locked_elements = _coerce_rule_strings(getattr(product_lock, "locked_elements", []) or [])
    if locked_elements:
        lines.append(f"Preserve locked elements: {'; '.join(locked_elements)}.")
    must_preserve_texts = _coerce_rule_strings(getattr(product_lock, "must_preserve_texts", []) or [])
    if must_preserve_texts:
        lines.append(f"Preserve brand and package texts exactly: {'; '.join(must_preserve_texts)}.")
    if getattr(product_lock, "package_type", ""):
        lines.append(f"Preserve package structure and proportions: {product_lock.package_type}.")
    if getattr(product_lock, "label_structure", ""):
        lines.append(f"Preserve label layout and placement: {product_lock.label_structure}.")
    if getattr(product_lock, "primary_color", ""):
        lines.append(f"Preserve main product color identity: {product_lock.primary_color}.")
    if getattr(product_lock, "material", ""):
        lines.append(f"Preserve visible material impression: {product_lock.material}.")
    editable_elements = _coerce_rule_strings(getattr(product_lock, "editable_elements", []) or [])
    if editable_elements:
        lines.append(f"Only allow scene-side edits on: {'; '.join(editable_elements)}.")
    if spec is not None and getattr(spec, "product_lock", None) is not None:
        must_preserve = _coerce_rule_strings(spec.product_lock.must_preserve)
        if must_preserve:
            lines.append(f"Must preserve from shot spec: {'; '.join(must_preserve)}.")
        spec_must_preserve_texts = _coerce_rule_strings(spec.product_lock.must_preserve_texts)
        if spec_must_preserve_texts:
            lines.append(f"Must preserve texts from shot spec: {'; '.join(spec_must_preserve_texts)}.")
        spec_editable_regions = _coerce_rule_strings(spec.product_lock.editable_regions)
        if spec_editable_regions:
            lines.append(f"Editable regions from shot spec: {'; '.join(spec_editable_regions)}.")
        must_not_change = _coerce_rule_strings(spec.product_lock.must_not_change)
        if must_not_change:
            lines.append(f"Must not change: {'; '.join(must_not_change)}.")
    return lines or ["Preserve package structure, brand text, label hierarchy, and dominant product color."]


def _resolve_clean_keep_subject_rules(*, prompt: ImagePrompt, product_lock, spec) -> list[str]:
    """统一生成调试日志里的主体锁定规则，避免出现 tuple / dict items 的字符串化噪声。"""
    if spec is not None and getattr(spec, "product_lock", None) is not None:
        return _coerce_rule_strings(
            [
                *list(spec.product_lock.must_preserve or []),
                *[f"must preserve texts: {item}" for item in spec.product_lock.must_preserve_texts],
                *[f"must not change: {item}" for item in spec.product_lock.must_not_change],
            ]
        )
    prompt_rules = _coerce_rule_strings(getattr(prompt, "keep_subject_rules", []) or [])
    if prompt_rules:
        return prompt_rules
    return _coerce_rule_strings(getattr(product_lock, "locked_elements", []) or [])


def _resolve_clean_editable_regions(*, prompt: ImagePrompt, product_lock, spec) -> list[str]:
    """统一生成调试日志里的可编辑区域，优先使用结构化 spec。"""
    if spec is not None and getattr(spec, "product_lock", None) is not None:
        return _coerce_rule_strings(spec.product_lock.editable_regions)
    prompt_regions = _coerce_rule_strings(getattr(prompt, "editable_regions", []) or [])
    if prompt_regions:
        return prompt_regions
    return _coerce_rule_strings(getattr(product_lock, "editable_elements", []) or [])


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
    """把 render constraints 转成稳定段落。"""
    lines = [
        f"Generation mode target: {spec.render_constraints.generation_mode}.",
        f"Reference image priority: {spec.render_constraints.reference_image_priority}.",
        f"Consistency strength: {spec.render_constraints.consistency_strength}.",
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
