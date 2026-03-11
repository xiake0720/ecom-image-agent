"""布局生成节点。

该节点负责生成文字布局结构，为后续 Pillow 后贴字提供坐标、尺寸和排版块信息。
当前阶段仍保持为规则型 / mock 布局实现，不接入真实布局模型。
"""

from __future__ import annotations

from src.services.planning.layout_generator import build_mock_layout_plan
from src.workflows.state import WorkflowDependencies, WorkflowState


def generate_layout(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """根据 shot plan 和输出尺寸生成布局计划。"""
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
