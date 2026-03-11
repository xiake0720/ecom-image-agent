"""图片生成节点。

当前节点负责把 `ImagePromptPlan` 交给图片 provider。
mock / real 的真正分支选择已经在依赖注入层完成，这里只保持统一调用入口。
"""

from __future__ import annotations

from pathlib import Path

from src.core.paths import get_task_generated_dir
from src.workflows.state import WorkflowDependencies, WorkflowState


def render_images(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成基础图片并返回 `GenerationResult`。"""
    task = state["task"]
    output_dir = Path(get_task_generated_dir(task.task_id))
    result = deps.image_provider.generate_images(
        state["image_prompt_plan"],
        output_dir=output_dir,
        # real 图片 provider 需要上传素材作为参考输入；mock provider 会忽略该参数。
        reference_assets=state.get("assets", []),
    )
    return {"generation_result": result, "logs": [*state.get("logs", []), "Rendered placeholder images."]}
