"""详情图 prompt 节点。"""

from __future__ import annotations

from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.services.detail_prompt_service import DetailPromptService


def detail_generate_prompt(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """把 plan + copy + 用户参数 + 参考图转成最终渲染 prompt。"""

    plan = state.get("detail_plan")
    if plan is None:
        raise RuntimeError("detail_generate_prompt requires detail_plan")
    service = DetailPromptService()
    prompt_plan = service.build_prompt_plan(
        state["detail_payload"],
        plan,
        state.get("detail_copy_blocks", []),
        state.get("detail_assets", []),
        planning_provider=deps.planning_provider,
    )
    deps.storage.save_json_artifact(state["task"].task_id, "plan/detail_prompt_plan.json", {"items": prompt_plan})
    return {
        "detail_prompt_plan": prompt_plan,
        "logs": [
            *state.get("logs", []),
            f"[detail_generate_prompt] page_count={len(prompt_plan)}",
            "[detail_generate_prompt] saved plan/detail_prompt_plan.json",
        ],
    }
