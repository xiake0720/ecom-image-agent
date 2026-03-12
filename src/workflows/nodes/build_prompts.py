"""图片提示词构建节点。

当前节点负责输出 `ImagePromptPlan`。
在 real 模式下，文本 provider 只负责生成结构化图片提示词；
正式中文仍由 `overlay_text` 节点统一处理。
"""

from __future__ import annotations

import logging

from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.layout_plan import LayoutItem
from src.domain.shot_plan import ShotSpec
from src.workflows.nodes.prompt_utils import describe_prompt_source, dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


DEFAULT_NEGATIVE_PROMPTS = [
    "plain white background",
    "deformed product",
    "wrong label layout",
    "wrong packaging structure",
    "wrong material appearance",
    "garbled text",
    "misspelled Chinese text",
    "low resolution",
    "blurry details",
    "overexposed lighting",
    "underexposed lighting",
    "cheap looking composition",
    "messy background",
    "exaggerated visual effects",
    "plastic cheap texture",
    "floating object composition",
    "illustration style",
    "cartoon style",
    "too many props",
    "harsh shadows",
    "props overpowering product",
]


def build_prompts(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘图片提示词计划。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[build_prompts] 开始构建图片提示词，模式={deps.text_provider_mode}。"]
    copy_map = {item.shot_id: item for item in state["copy_plan"].items}
    layout_map = {item.shot_id: item for item in state["layout_plan"].items}
    template_name = "build_image_prompts.md"
    template_source = describe_prompt_source(template_name)
    logger.info(
        "build_prompts 当前为纯结构化推理模式，不向文本模型发送图片输入，模板来源=%s",
        template_source,
    )
    logs.extend(
        [
            "[build_prompts] 当前为纯结构化推理模式，仅基于 task、product_analysis、shot、copy、layout 生成提示词。",
            "[build_prompts] 当前未向模型发送图片输入；真正的商品参考图会在 render_images 节点发送给图片模型。",
            f"[build_prompts] 当前使用的模板来源文件：{template_source}。",
        ]
    )
    if deps.text_provider_mode == "real":
        model_label = deps.planning_model_selection.label if deps.planning_model_selection else "-"
        model_id = deps.planning_model_selection.model_id if deps.planning_model_selection else "-"
        logger.info(
            "build_prompts 采用逐张 shot 的 AI 生成方式，provider=%s，模型=%s，model_id=%s，不再一次性生成整组 prompts，且当前未发送图片输入",
            deps.planning_provider_name or "unknown",
            model_label,
            model_id,
        )
        prompts = []
        total_shots = len(state["shot_plan"].shots)
        for index, shot in enumerate(state["shot_plan"].shots, start=1):
            copy_item = copy_map[shot.shot_id]
            layout_item = layout_map[shot.shot_id]
            prompt_input = _build_single_shot_prompt_input(
                task=task,
                product_analysis=state["product_analysis"],
                shot=shot,
                copy_item=copy_item,
                layout_item=layout_item,
            )
            logs.append(
                f"[build_prompts] 当前采用 per-shot AI 生成，正在处理第 {index}/{total_shots} 张：{shot.shot_id}。"
            )
            logger.info("开始逐张生成图片提示词，第 %s/%s 张，shot_id=%s", index, total_shots, shot.shot_id)
            shot_prompt = deps.planning_provider.generate_structured(
                prompt_input,
                ImagePrompt,
                system_prompt=load_prompt_text(template_name),
            )
            normalized_prompt = _normalize_image_prompt(
                task_output_size=task.output_size,
                shot=shot,
                layout_item=layout_item,
                product_analysis=state["product_analysis"],
                prompt=shot_prompt,
            )
            prompts.append(normalized_prompt)
            _save_shot_debug_artifacts(
                deps=deps,
                task_id=task.task_id,
                shot=shot,
                copy_item=copy_item,
                layout_item=layout_item,
                prompt=normalized_prompt,
            )
            logs.append(
                f"[build_prompts] 已完成第 {index}/{total_shots} 张提示词生成，并写入 artifacts/shots/{shot.shot_id}/prompt.json。"
            )
            logger.info(
                "逐张提示词生成完成，第 %s/%s 张，shot_id=%s，prompt 文件=artifacts/shots/%s/prompt.json",
                index,
                total_shots,
                shot.shot_id,
                shot.shot_id,
            )
        plan = ImagePromptPlan(prompts=prompts)
    else:
        logger.info("build_prompts 当前为 mock 文本模式，按逐张 shot 生成本地占位提示词")
        prompts = []
        total_shots = len(state["shot_plan"].shots)
        for index, shot in enumerate(state["shot_plan"].shots, start=1):
            layout_item = layout_map[shot.shot_id]
            logs.append(
                f"[build_prompts] 当前采用 per-shot 本地占位生成，正在处理第 {index}/{total_shots} 张：{shot.shot_id}。"
            )
            normalized_prompt = _normalize_image_prompt(
                task_output_size=task.output_size,
                shot=shot,
                layout_item=layout_item,
                product_analysis=state["product_analysis"],
                prompt=ImagePrompt(
                    shot_id=shot.shot_id,
                    shot_type=shot.shot_type,
                    prompt=(
                        f"Use the uploaded reference product as the exact hero subject, preserve the original package silhouette, "
                        f"label placement and main colors, create a high-end e-commerce commercial still life scene for {shot.title}, "
                        f"scene direction: {shot.scene_direction or shot.purpose}, focus on {shot.focus or shot.copy_goal}, "
                        f"composition: {shot.composition_direction or shot.composition_hint}, "
                        f"reserve clean readable negative space for Chinese e-commerce copy in the {_infer_text_space_hint(layout_item)} area, "
                        f"soft studio lighting, realistic premium product texture, clean layered background, restrained props."
                    ),
                    negative_prompt=DEFAULT_NEGATIVE_PROMPTS,
                    output_size=task.output_size,
                    preserve_rules=state["product_analysis"].visual_identity.must_preserve,
                    text_space_hint=_infer_text_space_hint(layout_item),
                    composition_notes=[
                        shot.composition_hint,
                        shot.composition_direction or "主体清晰，留白可读，产品不要过小",
                    ],
                    style_notes=[
                        *state["product_analysis"].visual_constraints.recommended_style_direction[:3],
                        "高端电商商业摄影质感",
                    ],
                ),
            )
            prompts.append(normalized_prompt)
            _save_shot_debug_artifacts(
                deps=deps,
                task_id=task.task_id,
                shot=shot,
                copy_item=copy_map[shot.shot_id],
                layout_item=layout_item,
                prompt=normalized_prompt,
            )
            logs.append(
                f"[build_prompts] 已完成第 {index}/{total_shots} 张占位提示词生成，并写入 artifacts/shots/{shot.shot_id}/prompt.json。"
            )
        plan = ImagePromptPlan(prompts=prompts)
    deps.storage.save_json_artifact(task.task_id, "image_prompt_plan.json", plan)
    prompt_shot_ids = ", ".join(item.shot_id for item in plan.prompts)
    logger.info("aggregate 图片提示词已更新，数量=%s，shot_ids=%s", len(plan.prompts), prompt_shot_ids or "-")
    logs.extend(
        [
            f"[build_prompts] 图片提示词构建完成，数量={len(plan.prompts)}，shot_ids={prompt_shot_ids or '-'}。",
            (
                "[build_prompts] 当前实际规划模型="
                f"{deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}。"
            ),
            "[build_prompts] 已写入 image_prompt_plan.json。",
        ]
    )
    return {"image_prompt_plan": plan, "logs": logs}


def _build_single_shot_prompt_input(
    *,
    task,
    product_analysis,
    shot: ShotSpec,
    copy_item,
    layout_item: LayoutItem,
) -> str:
    """构造单张图的 AI 提示词输入。"""
    text_space_hint = _infer_text_space_hint(layout_item)
    prompt_context = {
        "task": task,
        "product_analysis": product_analysis,
        "current_shot": shot,
        "current_copy": copy_item,
        "current_layout": layout_item,
        "build_prompt_rules": {
            "mode": "structured_reasoning_only",
            "image_input_sent_to_model": False,
            "reference_image_stage": "render_images",
            "platform_direction": _infer_platform_direction(task.platform),
            "text_space_hint": text_space_hint,
            "text_space_intent": "正式中文广告文案将由 Pillow 后贴字完成；当前图片必须预留干净、明亮、可读的文字区",
            "preserve_priority": product_analysis.visual_identity.must_preserve,
            "style_anchor": _build_shot_style_anchor(task.platform, product_analysis, shot),
            "negative_prompt_must_cover": DEFAULT_NEGATIVE_PROMPTS,
        },
    }
    return (
        "当前处于 build_prompts 节点，只能基于结构化结果为单张图生成提示词。\n"
        "注意：本节点不会向模型发送任何图片输入；真实商品参考图会在 render_images 节点再发送给图片模型。\n"
        "这不是整组图任务，不要输出多张图，不要写自由解释。\n\n"
        f"{dump_pretty(prompt_context)}"
    )


def _infer_text_space_hint(layout_item: LayoutItem) -> str:
    """根据当前布局推断文案留白方向。"""
    if not layout_item.blocks:
        return "top_right_clean_space"
    title_block = layout_item.blocks[0]
    horizontal = "left" if title_block.x <= layout_item.canvas_width // 2 else "right"
    vertical = "top" if title_block.y <= layout_item.canvas_height // 2 else "bottom"
    return f"{vertical}_{horizontal}_clean_space"


def _normalize_image_prompt(
    *,
    task_output_size: str,
    shot: ShotSpec,
    layout_item: LayoutItem,
    product_analysis,
    prompt: ImagePrompt,
) -> ImagePrompt:
    """对单张提示词结果做兼容归一化。"""
    preserve_rules = prompt.preserve_rules or product_analysis.visual_identity.must_preserve
    text_space_hint = prompt.text_space_hint or _infer_text_space_hint(layout_item)
    composition_notes = prompt.composition_notes or [
        shot.composition_hint,
        shot.composition_direction or "主体清晰稳定，留白区域干净可读",
    ]
    style_notes = prompt.style_notes or [
        *product_analysis.visual_constraints.recommended_style_direction[:3],
        "高端电商商业摄影风格",
    ]
    negative_prompt = prompt.negative_prompt or DEFAULT_NEGATIVE_PROMPTS
    return prompt.model_copy(
        update={
            "shot_type": prompt.shot_type or shot.shot_type or shot.title,
            "output_size": prompt.output_size or task_output_size,
            "negative_prompt": negative_prompt,
            "preserve_rules": preserve_rules,
            "text_space_hint": text_space_hint,
            "composition_notes": composition_notes,
            "style_notes": style_notes,
        }
    )


def _infer_platform_direction(platform: str) -> str:
    """根据平台名称推断平台审美方向。"""
    platform_map = {
        "tmall": "天猫风格，商业感强、干净、质感稳定",
        "taobao": "淘宝风格，主体明确、卖点直给、留白可读",
        "jd": "京东风格，规整清晰、可信赖、信息表达直接",
        "xiaohongshu": "小红书风格，生活方式感更强但仍需商业可用",
    }
    return platform_map.get(str(platform).lower(), f"{platform} 电商主图方向，强调主体清晰与商业转化")


def _build_shot_style_anchor(platform: str, product_analysis, shot: ShotSpec) -> dict:
    """构造单张图应继承的风格锚点。"""
    return {
        "platform": _infer_platform_direction(platform),
        "recommended_style_direction": product_analysis.visual_constraints.recommended_style_direction[:3],
        "avoid_direction": product_analysis.visual_constraints.avoid[:4],
        "visual_keywords": product_analysis.visual_style_keywords[:4],
        "dominant_colors": product_analysis.visual_identity.dominant_colors[:3],
        "shot_goal": shot.goal,
        "shot_focus": shot.focus,
        "scene_direction": shot.scene_direction,
        "composition_direction": shot.composition_direction,
    }


def _save_shot_debug_artifacts(
    *,
    deps: WorkflowDependencies,
    task_id: str,
    shot: ShotSpec,
    copy_item,
    layout_item: LayoutItem,
    prompt: ImagePrompt,
) -> None:
    """为单张图写入调试用 JSON 产物。"""
    base_dir = f"artifacts/shots/{shot.shot_id}"
    deps.storage.save_json_artifact(task_id, f"{base_dir}/shot.json", shot)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/copy.json", copy_item)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/layout.json", layout_item)
    deps.storage.save_json_artifact(task_id, f"{base_dir}/prompt.json", prompt)
