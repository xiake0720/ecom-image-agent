"""图片生成节点。"""

from __future__ import annotations

from pathlib import Path

from src.core.config import get_settings
from src.core.paths import get_task_generated_dir, get_task_generated_preview_dir
from src.domain.image_prompt_plan import ImagePromptPlan
from src.services.assets.reference_selector import select_reference_assets
from src.workflows.state import WorkflowDependencies, WorkflowState


def render_images(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成基础图片并返回 `GenerationResult`。"""
    task = state["task"]
    render_mode = _resolve_render_mode(state)
    render_variant = "preview" if render_mode == "preview" else "final"
    prompt_plan = _resolve_render_prompt_plan(state, render_mode)
    output_dir = (
        Path(get_task_generated_preview_dir(task.task_id))
        if render_variant == "preview"
        else Path(get_task_generated_dir(task.task_id))
    )
    reference_assets = _select_render_assets(state)
    reference_asset_ids = [asset.asset_id for asset in reference_assets]
    logs = [
        *state.get("logs", []),
        (
            "[render_images] 开始生成图片，"
            f"render_mode={render_mode}，render_variant={render_variant}，"
            f"prompts={len(prompt_plan.prompts)}，references={len(reference_assets)}，"
            f"provider={deps.image_provider_name or '-'}，"
            f"model={deps.image_model_selection.model_id if deps.image_model_selection else '-'}。"
        ),
        f"[render_images] 本次生图实际参考图 asset_id={reference_asset_ids or ['-']}。",
    ]
    result = deps.image_generation_provider.generate_images(
        prompt_plan,
        output_dir=output_dir,
        reference_assets=reference_assets,
    )
    output_names = ", ".join(Path(image.image_path).name for image in result.images)
    logs.extend(
        [
            f"[render_images] 图片生成完成，数量={len(result.images)}，文件={output_names or '-'}。",
            f"[render_images] 输出目录={output_dir}。",
        ]
    )
    return {
        "generation_result": result,
        "render_variant": render_variant,
        "render_mode": render_mode,
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
    return ImagePromptPlan(prompts=preview_prompts)


def _resolve_render_max_reference_images(state: WorkflowState) -> int:
    explicit_value = state.get("render_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    return max(1, int(get_settings().render_max_reference_images))


def _select_render_assets(state: WorkflowState) -> list:
    return select_reference_assets(
        state.get("assets", []),
        max_images=_resolve_render_max_reference_images(state),
    )
