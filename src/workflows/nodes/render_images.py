"""Image rendering node."""

from __future__ import annotations

from pathlib import Path

from src.core.config import get_settings
from src.core.paths import get_task_generated_dir, get_task_generated_preview_dir
from src.domain.image_prompt_plan import ImagePromptPlan
from src.services.assets.reference_selector import ReferenceSelection, select_reference_bundle
from src.workflows.state import WorkflowDependencies, WorkflowState


def render_images(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """Generate base images and return a `GenerationResult`."""
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
    logs = [
        *state.get("logs", []),
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
    ]
    for prompt in prompt_plan.prompts:
        prompt_generation_mode = (
            "image_edit" if render_generation_mode == "image_edit" else getattr(prompt, "generation_mode", "t2i")
        )
        logs.append(
            (
                "[render_images] prompt_contract "
                f"shot_id={prompt.shot_id} "
                f"generation_mode={prompt_generation_mode} "
                f"text_input={'edit_instruction' if render_generation_mode == 'image_edit' and getattr(prompt, 'edit_instruction', '') else 'prompt'} "
                f"keep_subject_rules={getattr(prompt, 'keep_subject_rules', [])} "
                f"editable_regions={getattr(prompt, 'editable_regions', [])} "
                f"text_safe_zone={getattr(prompt, 'text_safe_zone', '') or getattr(prompt, 'text_space_hint', '')}"
            )
        )
    result = deps.image_generation_provider.generate_images(
        prompt_plan,
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
    explicit_value = str(state.get("render_mode") or "").strip().lower()
    if explicit_value in {"preview", "final", "full_auto"}:
        return explicit_value
    return get_settings().resolve_render_mode()


def _resolve_render_prompt_plan(state: WorkflowState, render_mode: str) -> ImagePromptPlan:
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
    explicit_value = state.get("render_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    if render_mode == "preview":
        return 1
    return 2


def _select_render_assets(state: WorkflowState, *, render_mode: str) -> ReferenceSelection:
    return select_reference_bundle(
        state.get("assets", []),
        max_images=_resolve_render_max_reference_images(state, render_mode=render_mode),
    )


def _resolve_generation_context(*, provider, fallback_model_id: str, reference_assets: list) -> dict[str, object]:
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
