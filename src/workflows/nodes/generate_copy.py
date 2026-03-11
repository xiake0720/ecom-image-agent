from __future__ import annotations

from src.services.planning.copy_generator import build_mock_copy_plan
from src.workflows.state import WorkflowDependencies, WorkflowState


def generate_copy(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
    copy_plan = build_mock_copy_plan(task, state["shot_plan"])
    deps.storage.save_json_artifact(task.task_id, "copy_plan.json", copy_plan)
    return {"copy_plan": copy_plan, "logs": [*state.get("logs", []), "Generated structured copy."]}

