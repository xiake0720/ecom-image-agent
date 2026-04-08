"""详情图规划节点。"""

from __future__ import annotations

from backend.core.config import get_settings
from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.services.detail_planner_service import DetailPlannerService


def detail_plan(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """生成整套详情图规划并落盘。"""

    service = DetailPlannerService(template_root=get_settings().template_root)
    payload = state["detail_payload"]
    assets = state.get("detail_assets", [])
    preflight_report = state.get("detail_preflight_report")
    director_brief = service.build_director_brief(payload, assets, preflight_report=preflight_report)
    plan = service.build_plan(
        payload,
        assets,
        preflight_report=preflight_report,
        director_brief=director_brief,
        planning_provider=deps.planning_provider,
    )
    deps.storage.save_json_artifact(state["task"].task_id, "plan/director_brief.json", director_brief)
    deps.storage.save_json_artifact(state["task"].task_id, "plan/detail_plan.json", plan)
    return {
        "detail_director_brief": director_brief,
        "detail_plan": plan,
        "logs": [
            *state.get("logs", []),
            f"[detail_plan] total_pages={plan.total_pages} total_screens={plan.total_screens}",
            "[detail_plan] saved plan/director_brief.json",
            "[detail_plan] saved plan/detail_plan.json",
        ],
    }
