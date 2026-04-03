"""详情图规划节点。"""

from __future__ import annotations

from pathlib import Path

from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.services.detail_planner_service import DetailPlannerService


def detail_plan(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """生成整套详情图规划并落盘。"""

    service = DetailPlannerService(template_root=Path("backend/templates"))
    plan = service.build_plan(
        state["detail_payload"],
        state.get("detail_assets", []),
        planning_provider=deps.planning_provider,
    )
    deps.storage.save_json_artifact(state["task"].task_id, "plan/detail_plan.json", plan)
    return {
        "detail_plan": plan,
        "logs": [
            *state.get("logs", []),
            f"[detail_plan] total_pages={plan.total_pages} total_screens={plan.total_screens}",
            "[detail_plan] saved plan/detail_plan.json",
        ],
    }
