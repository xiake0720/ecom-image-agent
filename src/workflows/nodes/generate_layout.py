from __future__ import annotations

from src.services.planning.layout_generator import build_mock_layout_plan
from src.workflows.state import WorkflowDependencies, WorkflowState


def generate_layout(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
    layout_plan = build_mock_layout_plan(state["shot_plan"], task.output_size)
    deps.storage.save_json_artifact(task.task_id, "layout_plan.json", layout_plan)
    return {"layout_plan": layout_plan, "logs": [*state.get("logs", []), "Generated layout plan."]}

