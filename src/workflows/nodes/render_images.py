from __future__ import annotations

from pathlib import Path

from src.core.paths import get_task_generated_dir
from src.workflows.state import WorkflowDependencies, WorkflowState


def render_images(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
    output_dir = Path(get_task_generated_dir(task.task_id))
    result = deps.image_provider.generate_images(state["image_prompt_plan"], output_dir=output_dir)
    return {"generation_result": result, "logs": [*state.get("logs", []), "Rendered placeholder images."]}

