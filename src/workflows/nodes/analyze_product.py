from __future__ import annotations

from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.workflows.state import WorkflowDependencies, WorkflowState


def analyze_product(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
    analysis = build_mock_product_analysis(state.get("assets", []), task.product_name)
    deps.storage.save_json_artifact(task.task_id, "product_analysis.json", analysis)
    return {"product_analysis": analysis, "logs": [*state.get("logs", []), "Generated product analysis."]}

