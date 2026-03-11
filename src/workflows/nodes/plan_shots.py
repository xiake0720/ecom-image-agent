"""图组规划节点。

当前节点负责输出 `ShotPlan`，并保持 shot_id、张数和落盘结构稳定。
"""

from __future__ import annotations

from src.domain.shot_plan import ShotPlan
from src.services.planning.shot_planner import build_mock_shot_plan
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState


def plan_shots(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """根据商品分析结果生成图组规划。"""
    task = state["task"]
    if deps.text_provider_mode == "real":
        prompt = (
            "请为当前茶叶商品任务规划电商图组。\n"
            f"要求生成 {task.shot_count} 张图，且每个 shot_id 唯一。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"商品分析:\n{dump_pretty(state['product_analysis'])}"
        )
        shot_plan = deps.text_provider.generate_structured(
            prompt,
            ShotPlan,
            system_prompt=load_prompt_text("plan_shots.md"),
        )
    else:
        shot_plan = build_mock_shot_plan(state["product_analysis"], task.shot_count)
    deps.storage.save_json_artifact(task.task_id, "shot_plan.json", shot_plan)
    return {"shot_plan": shot_plan, "logs": [*state.get("logs", []), "Planned image shots."]}
