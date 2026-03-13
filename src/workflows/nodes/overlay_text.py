"""中文后贴字节点。"""

from __future__ import annotations

from pathlib import Path

from src.core.paths import get_task_final_dir, get_task_final_preview_dir, get_task_preview_dir
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.services.rendering.image_postprocess import save_preview
from src.workflows.state import WorkflowDependencies, WorkflowState


def overlay_text(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """对生成结果执行中文后贴字并生成预览图。"""
    task = state["task"]
    render_variant = str(state.get("render_variant") or "final")
    logs = [*state.get("logs", []), f"[overlay_text] 开始执行中文后贴字，render_variant={render_variant}，图片数={len(state['generation_result'].images)}。"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    final_images: list[GeneratedImage] = []
    for image in state["generation_result"].images:
        final_base_dir = Path(get_task_final_preview_dir(task.task_id)) if render_variant == "preview" else Path(get_task_final_dir(task.task_id))
        final_path = final_base_dir / Path(image.image_path).name
        preview_thumb_path = Path(get_task_preview_dir(task.task_id)) / f"{render_variant}_{Path(image.image_path).name}"
        deps.text_renderer.render_copy(
            input_image_path=image.image_path,
            copy_item=copy_map[image.shot_id],
            layout_item=layout_map[image.shot_id],
            output_path=str(final_path),
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
            f"[overlay_text] 中文后贴字完成，render_variant={render_variant}，finalized_images={len(final_images)}。",
            "[overlay_text] 已通过 Pillow 完成中文后贴字。",
        ],
    }
    if render_variant == "preview":
        updates["preview_generation_result"] = result
    return updates
