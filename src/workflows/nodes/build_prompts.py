from __future__ import annotations

from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.workflows.state import WorkflowDependencies, WorkflowState


def build_prompts(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    task = state["task"]
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

