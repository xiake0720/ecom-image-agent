"""中文后贴字节点。

该节点将结构化文案和布局计划应用到基础图片上：
- 使用 Pillow 渲染中文标题 / 副标题 / 卖点
- 输出最终图到 `final/`
- 生成 UI 用预览图到 `previews/`
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.paths import get_task_final_dir, get_task_preview_dir
from src.domain.generation_result import GeneratedImage, GenerationResult
from src.services.rendering.image_postprocess import save_preview
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def overlay_text(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """对生成结果执行中文后贴字并生成预览图。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[overlay_text] 开始执行中文后贴字，图片数={len(state['generation_result'].images)}。"]
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
    logger.info("中文后贴字完成，最终图片数量=%s", len(final_images))
    return {
        "generation_result": GenerationResult(images=final_images),
        "logs": [
            *logs,
            f"[overlay_text] 中文后贴字完成，finalized_images={len(final_images)}。",
            "[overlay_text] 已通过 Pillow 完成中文后贴字。",
        ],
    }
