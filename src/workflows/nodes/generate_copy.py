"""文案生成节点。

当前节点负责输出 `CopyPlan`，供后续布局和后贴字使用。
图片模型不负责正式中文落图，因此这里的结构化文案仍是核心输入。
"""

from __future__ import annotations

from src.domain.copy_plan import CopyPlan
from src.services.planning.copy_generator import build_mock_copy_plan
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState


def generate_copy(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘结构化中文文案。"""
    task = state["task"]
    if deps.text_provider_mode == "real":
        prompt = (
            "请为当前茶叶商品任务生成结构化中文文案。\n"
            "文案必须适合后续 Pillow 后贴字，不要输出自由文本解释。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"图组规划:\n{dump_pretty(state['shot_plan'])}"
        )
        copy_plan = deps.text_provider.generate_structured(
            prompt,
            CopyPlan,
            system_prompt=load_prompt_text("generate_copy.md"),
        )
    else:
        copy_plan = build_mock_copy_plan(task, state["shot_plan"])
    deps.storage.save_json_artifact(task.task_id, "copy_plan.json", copy_plan)
    return {"copy_plan": copy_plan, "logs": [*state.get("logs", []), "Generated structured copy."]}
