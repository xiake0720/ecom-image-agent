from __future__ import annotations

from src.services.planning.shot_planner import build_mock_shot_plan
from src.workflows.state import WorkflowDependencies, WorkflowState


def plan_shots(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
    shot_plan = build_mock_shot_plan(state["product_analysis"], task.shot_count)
    deps.storage.save_json_artifact(task.task_id, "shot_plan.json", shot_plan)
    return {"shot_plan": shot_plan, "logs": [*state.get("logs", []), "Planned image shots."]}

