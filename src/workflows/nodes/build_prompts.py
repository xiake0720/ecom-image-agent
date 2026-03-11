"""图片提示词构建节点。

当前节点负责输出 `ImagePromptPlan`。
在 real 模式下，文本 provider 只负责生成结构化图片提示词；
正式中文仍由 `overlay_text` 节点统一处理。
"""

from __future__ import annotations

from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState


def build_prompts(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘图片提示词计划。"""
    task = state["task"]
    if deps.text_provider_mode == "real":
        prompt = (
            "请为当前茶叶商品图任务输出结构化图片提示词。\n"
            "要求保留商品主体一致性、留出文案区域，不要让图片模型直接输出正式中文。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"商品分析:\n{dump_pretty(state['product_analysis'])}\n\n"
            f"图组规划:\n{dump_pretty(state['shot_plan'])}\n\n"
            f"文案规划:\n{dump_pretty(state['copy_plan'])}"
        )
        plan = deps.text_provider.generate_structured(
            prompt,
            ImagePromptPlan,
            system_prompt=load_prompt_text("build_image_prompts.md"),
        )
        # 对真实返回结果做最小归一化，确保后续图片节点仍能读取稳定字段。
        normalized_prompts = []
        for item in plan.prompts:
            normalized_prompts.append(
                item.model_copy(
                    update={
                        "output_size": item.output_size or task.output_size,
                        "negative_prompt": item.negative_prompt or "garbled text, watermark, distorted product",
                    }
                )
            )
        plan = ImagePromptPlan(prompts=normalized_prompts)
    else:
        prompts = []
        for shot in state["shot_plan"].shots:
            prompts.append(
                ImagePrompt(
                    shot_id=shot.shot_id,
                    prompt=f"{task.brand_name} {task.product_name}, tea ecommerce, {shot.composition_hint}, clean premium style",
                    negative_prompt="garbled text, watermark, distorted product",
                    output_size=task.output_size,
                )
            )
        plan = ImagePromptPlan(prompts=prompts)
    deps.storage.save_json_artifact(task.task_id, "image_prompt_plan.json", plan)
    return {"image_prompt_plan": plan, "logs": [*state.get("logs", []), "Built image prompts."]}
