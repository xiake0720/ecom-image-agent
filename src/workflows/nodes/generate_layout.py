from __future__ import annotations

from src.services.planning.layout_generator import build_mock_layout_plan
from src.workflows.state import WorkflowDependencies, WorkflowState


def generate_layout(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
    logs = [*state.get("logs", []), f"[generate_layout] start output_size={task.output_size}."]
    layout_plan = build_mock_layout_plan(state["shot_plan"], task.output_size)
    deps.storage.save_json_artifact(task.task_id, "layout_plan.json", layout_plan)
    logs.extend(
        [
            f"[generate_layout] result items={len(layout_plan.items)}.",
            "[generate_layout] saved layout_plan.json.",
        ]
    )
    return {"layout_plan": layout_plan, "logs": logs}
