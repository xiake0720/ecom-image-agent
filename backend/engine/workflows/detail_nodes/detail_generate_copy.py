"""详情图文案节点。"""

from __future__ import annotations

from backend.engine.workflows.detail_state import DetailWorkflowDependencies, DetailWorkflowState
from backend.services.detail_copy_service import DetailCopyService


def detail_generate_copy(state: DetailWorkflowState, deps: DetailWorkflowDependencies) -> dict:
    """为 plan 中每一屏生成结构化中文文案。"""

    plan = state.get("detail_plan")
    if plan is None:
        raise RuntimeError("detail_generate_copy requires detail_plan")
    service = DetailCopyService()
    copy_blocks = service.build_copy(
        state["detail_payload"],
        plan,
        planning_provider=deps.planning_provider,
    )
    deps.storage.save_json_artifact(state["task"].task_id, "plan/detail_copy_plan.json", {"items": copy_blocks})
    return {
        "detail_copy_blocks": copy_blocks,
        "logs": [
            *state.get("logs", []),
            f"[detail_generate_copy] block_count={len(copy_blocks)}",
            "[detail_generate_copy] saved plan/detail_copy_plan.json",
        ],
    }
