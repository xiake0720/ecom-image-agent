"""图片生成节点。

当前节点负责把 `ImagePromptPlan` 交给图片 provider。
mock / real 的真正分支选择已经在依赖注入层完成，这里只保持统一调用入口。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.paths import get_task_generated_dir
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def render_images(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成基础图片并返回 `GenerationResult`。"""
    task = state["task"]
    output_dir = Path(get_task_generated_dir(task.task_id))
    logs = [
        *state.get("logs", []),
        (
            "[render_images] 开始生成图片，"
            f"mode={deps.image_provider_mode}，prompts={len(state['image_prompt_plan'].prompts)}，"
            f"references={len(state.get('assets', []))}，provider={deps.image_provider_name or '-'}。"
        ),
    ]
    result = deps.image_generation_provider.generate_images(
        state["image_prompt_plan"],
        output_dir=output_dir,
        # real 图片 provider 需要上传素材作为参考输入；mock provider 会忽略该参数。
        reference_assets=state.get("assets", []),
    )
    output_names = ", ".join(Path(image.image_path).name for image in result.images)
    logger.info("图片生成节点完成，输出数量=%s，文件=%s，目录=%s", len(result.images), output_names or "-", output_dir)
    logs.extend(
        [
            f"[render_images] 图片生成完成，数量={len(result.images)}，文件={output_names or '-'}。",
            f"[render_images] 输出目录={output_dir}。",
        ]
    )
    return {"generation_result": result, "logs": logs}
