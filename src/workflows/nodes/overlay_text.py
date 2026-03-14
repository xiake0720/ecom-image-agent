"""Chinese text overlay node."""

from __future__ import annotations

from pathlib import Path

from src.core.config import get_settings
from src.core.paths import get_task_final_dir, get_task_final_preview_dir, get_task_preview_dir
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.services.rendering.image_postprocess import save_preview
from src.workflows.state import WorkflowDependencies, WorkflowState


def overlay_text(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """Overlay Chinese copy onto generated images and save previews."""
    task = state["task"]
    render_variant = str(state.get("render_variant") or "final")
    logs = [
        *state.get("logs", []),
        (
            f"[overlay_text] start render_variant={render_variant} "
            f"image_count={len(state['generation_result'].images)} "
            f"text_render_preset={get_settings().resolve_text_render_preset()}"
        ),
    ]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    final_images: list[GeneratedImage] = []
    for image in state["generation_result"].images:
        final_base_dir = Path(get_task_final_preview_dir(task.task_id)) if render_variant == "preview" else Path(get_task_final_dir(task.task_id))
        final_path = final_base_dir / Path(image.image_path).name
        preview_thumb_path = Path(get_task_preview_dir(task.task_id)) / f"{render_variant}_{Path(image.image_path).name}"
        render_report = deps.text_renderer.render_copy(
            input_image_path=image.image_path,
            copy_item=copy_map[image.shot_id],
            layout_item=layout_map[image.shot_id],
            output_path=str(final_path),
        )
        block_summaries = [
            (
                f"{block.kind}:preset={block.typography_preset},"
                f"color={block.text_color},"
                f"plate={block.background_plate_applied},"
                f"shadow={block.shadow_applied},"
                f"stroke={block.stroke_applied}"
            )
            for block in render_report.blocks
        ]
        logs.append(
            (
                "[overlay] "
                f"shot_id={image.shot_id} "
                f"typography_preset={get_settings().resolve_text_render_preset()} "
                f"adaptive_color_result={block_summaries or ['no_text_blocks_rendered']}"
            )
        )
        save_preview(str(final_path), preview_thumb_path)
        final_images.append(
            image.model_copy(
                update={
                    "image_path": str(final_path),
                    "preview_path": str(preview_thumb_path),
                    "status": "finalized",
                }
            )
        )
    result = GenerationResult(images=final_images)
    updates = {
        "generation_result": result,
        "logs": [
            *logs,
            f"[overlay_text] completed render_variant={render_variant} finalized_images={len(final_images)}",
            "[overlay_text] chinese copy overlay finished with Pillow",
        ],
    }
    if render_variant == "preview":
        updates["preview_generation_result"] = result
    return updates
