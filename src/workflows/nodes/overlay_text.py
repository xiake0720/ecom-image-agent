from __future__ import annotations

from pathlib import Path

from src.core.paths import get_task_final_dir, get_task_preview_dir
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.services.rendering.image_postprocess import save_preview
from src.workflows.state import WorkflowDependencies, WorkflowState


def overlay_text(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    final_images: list[GeneratedImage] = []
    for image in state["generation_result"].images:
        final_path = Path(get_task_final_dir(task.task_id)) / Path(image.image_path).name
        preview_path = Path(get_task_preview_dir(task.task_id)) / Path(image.image_path).name
        deps.text_renderer.render_copy(
            input_image_path=image.image_path,
            copy_item=copy_map[image.shot_id],
            layout_item=layout_map[image.shot_id],
            output_path=str(final_path),
        )
        save_preview(str(final_path), preview_path)
        final_images.append(
            image.model_copy(
                update={
                    "image_path": str(final_path),
                    "preview_path": str(preview_path),
                    "status": "finalized",
                }
            )
        )
    return {
        "generation_result": GenerationResult(images=final_images),
        "logs": [*state.get("logs", []), "Overlayed Chinese copy with Pillow."],
    }

