"""v2 生图 prompt 精修节点。

文件位置：
- `src/workflows/nodes/prompt_refine_v2.py`

职责：
- 把导演规划收口为可执行的逐图 prompt
- 同时生成主标题、副标题、卖点与版式提示
- 明确用户输入优先、防止参考图文案泄漏
"""

from __future__ import annotations

from src.core.config import get_settings
from src.domain.director_output import DirectorOutput, DirectorShot
from src.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from src.domain.task import CopyMode, Task
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import describe_prompt_source, dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

TITLE_FALLBACKS: dict[str, str] = {
    "hero": "东方雅礼",
    "packaging_feature": "细节见真",
    "dry_leaf_detail": "条索清晰",
    "tea_soup": "汤色透亮",
    "brewed_leaf_detail": "叶底鲜活",
    "gift_scene": "礼赠有面",
    "lifestyle": "日常雅饮",
    "process_or_quality": "品质把关",
}

SUBTITLE_FALLBACKS: dict[str, str] = {
    "hero": "主包装识别清晰稳定",
    "packaging_feature": "包装结构质感更清楚",
    "dry_leaf_detail": "干茶状态真实可辨",
    "tea_soup": "茶汤通透自然有质感",
    "brewed_leaf_detail": "叶底状态真实自然",
    "gift_scene": "礼赠场景高级得体",
    "lifestyle": "融入克制日常茶生活",
    "process_or_quality": "卖点说明聚焦更可信",
}


def prompt_refine_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """基于导演规划生成 v2 最终 prompt 计划。"""

    task = state["task"]
    director_output = state.get("director_output")
    if director_output is None:
        raise RuntimeError("prompt_refine_v2 requires director_output")

    settings = get_settings()
    fallback_plan = _build_fallback_prompt_plan(
        task=task,
        director_output=director_output,
        aspect_ratio=task.aspect_ratio or settings.default_image_aspect_ratio,
        image_size=task.image_size or settings.default_image_size,
        brand_name=task.brand_name,
        product_name=task.product_name,
    )
    logs = [
        *state.get("logs", []),
        f"[prompt_refine_v2] start shot_count={len(director_output.shots)}",
        f"[prompt_refine_v2] template_source={describe_prompt_source('prompt_refine_v2.md')}",
        f"[prompt_refine_v2] copy_mode={task.copy_mode.value}",
        *format_connected_contract_logs(state, node_name="prompt_refine_v2"),
    ]

    provider_name, provider_model_id = planning_provider_identity(deps)
    cache_key, cache_context = build_node_cache_key(
        node_name="prompt_refine_v2",
        state=state,
        deps=deps,
        prompt_filename="prompt_refine_v2.md" if deps.text_provider_mode == "real" else None,
        prompt_version="mock-prompt-refine-v2" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "director_output_hash": hash_state_payload(director_output),
            "copy_mode": task.copy_mode.value,
        },
    )
    if should_use_cache(state):
        cached = deps.storage.load_cached_json_artifact("prompt_refine_v2", cache_key, PromptPlanV2)
        if cached is not None:
            deps.storage.save_json_artifact(task.task_id, "prompt_plan_v2.json", cached)
            return {
                "prompt_plan_v2": cached,
                "logs": [*logs, f"[cache] node=prompt_refine_v2 status=hit key={cache_key}", "[prompt_refine_v2] saved prompt_plan_v2.json"],
            }
        logs.append(f"[cache] node=prompt_refine_v2 status=miss key={cache_key}")
    elif is_force_rerun(state):
        logs.append("[cache] node=prompt_refine_v2 status=ignored key=-")

    if deps.text_provider_mode == "real":
        prompt = _build_prompt(task=task, director_output=director_output, fallback_plan=fallback_plan)
        prompt_plan = deps.planning_provider.generate_structured(
            prompt,
            PromptPlanV2,
            system_prompt=load_prompt_text("prompt_refine_v2.md"),
        )
        prompt_plan = _normalize_prompt_plan(prompt_plan, fallback_plan, task=task)
    else:
        prompt_plan = fallback_plan

    deps.storage.save_json_artifact(task.task_id, "prompt_plan_v2.json", prompt_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("prompt_refine_v2", cache_key, prompt_plan, metadata=cache_context)
    logs.extend(_build_prompt_logs(prompt_plan))
    logs.append("[prompt_refine_v2] saved prompt_plan_v2.json")
    return {"prompt_plan_v2": prompt_plan, "logs": logs}


def _build_prompt(*, task: Task, director_output: DirectorOutput, fallback_plan: PromptPlanV2) -> str:
    """构建 v2 prompt 计划节点提示词。"""

    context = {
        "task_copy_controls": {
            "copy_mode": task.copy_mode.value,
            "title_text": task.title_text,
            "subtitle_text": task.subtitle_text,
            "selling_points": task.selling_points,
        },
        "style_controls": {
            "style_type": task.style_type,
            "style_preferences": task.style_preferences,
            "custom_elements": task.custom_elements,
            "avoid_elements": task.avoid_elements,
        },
        "director_output": director_output,
        "fallback_plan": fallback_plan,
    }
    return (
        "请基于导演规划生成最终可执行的 PromptPlanV2。\n"
        "必须保持 shot_id 与 shot_role 不变。\n"
        "主标题建议 4-8 字，副标题建议 8-15 字。\n"
        "如果用户提供了 title_text / subtitle_text / selling_points，必须优先使用原文，不得替换或重写。\n"
        "如果用户未提供，才允许由当前流程自动生成。\n"
        "忽略参考图中的可见文案内容，不得将其转写、复用、概括为广告文案。\n"
        "参考图只用于学习包装结构、颜色、材质、陈列方式、氛围与风格，不用于提取广告文字。\n"
        "hero 图必须明确主体视觉面积约占画面 60%-70%，约等于 2/3，商品必须先于背景被看见。\n"
        "render_prompt 必须可直接交给图片模型执行，并明确保护包装主体、品牌识别与文案留白。\n\n"
        f"prompt_refine_context:\n{dump_pretty(context)}"
    )


def _build_fallback_prompt_plan(
    *,
    task: Task,
    director_output: DirectorOutput,
    aspect_ratio: str,
    image_size: str,
    brand_name: str,
    product_name: str,
) -> PromptPlanV2:
    """构建稳定可用的 v2 prompt 兜底计划。"""

    shots: list[PromptShot] = []
    for shot in director_output.shots:
        copy_bundle = _resolve_copy_bundle(task=task, shot=shot, candidate=None)
        layout_hint = _resolve_layout_hint(shot)
        typography_hint = _resolve_typography_hint(shot)
        subject_occupancy_ratio = shot.subject_occupancy_ratio if shot.subject_occupancy_ratio is not None else (0.66 if shot.shot_role == "hero" else None)
        shots.append(
            PromptShot(
                shot_id=shot.shot_id,
                shot_role=shot.shot_role,
                render_prompt=_build_render_prompt(
                    task=task,
                    brand_name=brand_name,
                    product_name=product_name,
                    visual_style=director_output.visual_style,
                    shot=shot,
                    layout_hint=layout_hint,
                    typography_hint=typography_hint,
                ),
                title_copy=copy_bundle["title_copy"],
                subtitle_copy=copy_bundle["subtitle_copy"],
                selling_points_for_render=copy_bundle["selling_points_for_render"],
                layout_hint=layout_hint,
                typography_hint=typography_hint,
                copy_source=copy_bundle["copy_source"],
                subject_occupancy_ratio=subject_occupancy_ratio,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
        )
    return PromptPlanV2(shots=shots)


def _build_render_prompt(
    *,
    task: Task,
    brand_name: str,
    product_name: str,
    visual_style: str,
    shot: DirectorShot,
    layout_hint: str,
    typography_hint: str,
) -> str:
    """拼装单张图的执行 prompt。"""

    lines = [
        f"为 {brand_name} {product_name} 生成一张 {shot.shot_role} 电商图。",
        f"目标：{shot.objective}",
        f"受众：{shot.audience}",
        f"卖点方向：{'、'.join(shot.selling_points)}",
        f"场景：{shot.scene}",
        f"构图：{shot.composition}",
        f"视觉焦点：{shot.visual_focus}",
        f"文案方向：{shot.copy_direction}",
        f"主体比例要求：{shot.product_scale_guideline}",
        f"整组风格：{visual_style}",
        f"版式提示：{layout_hint}",
        f"文字层级：{typography_hint}",
        "必须保留商品包装主体、品牌识别与标签层级，不要夸大功效，不要让道具压过商品。",
        "忽略参考图中的可见文案内容，不得将其转写、复用、概括为广告文案。",
        "参考图只用于学习包装结构、颜色、材质、陈列方式、氛围与风格，不用于提取广告文字。",
        "产品参考图只用于保持包装结构、材质、颜色与标签一致；背景风格参考图只用于背景氛围，不得替换产品包装。",
        "文案直接融入画面，不要做简陋文本框。",
        "文字区域要清晰可读，但不允许压住关键产品区。",
    ]
    if task.style_preferences:
        lines.append(f"额外风格偏好：{task.style_preferences}")
    if task.custom_elements:
        lines.append(f"可加入元素：{'、'.join(task.custom_elements)}")
    if task.avoid_elements:
        lines.append(f"避免元素：{'、'.join(task.avoid_elements)}")
    return "\n".join(lines)


def _normalize_prompt_plan(candidate: PromptPlanV2, fallback_plan: PromptPlanV2, *, task: Task) -> PromptPlanV2:
    """对齐 shot_id，补齐缺失字段，并强制用户输入优先。"""

    shot_by_id = {shot.shot_id: shot for shot in candidate.shots}
    normalized: list[PromptShot] = []
    for fallback in fallback_plan.shots:
        current = shot_by_id.get(fallback.shot_id)
        copy_bundle = _resolve_copy_bundle(task=task, shot=None, candidate=current, fallback=fallback)
        normalized.append(
            PromptShot(
                shot_id=fallback.shot_id,
                shot_role=fallback.shot_role,
                render_prompt=_pick_text(current.render_prompt if current else "", fallback.render_prompt),
                title_copy=copy_bundle["title_copy"],
                subtitle_copy=copy_bundle["subtitle_copy"],
                selling_points_for_render=copy_bundle["selling_points_for_render"],
                layout_hint=_pick_text(current.layout_hint if current else "", fallback.layout_hint),
                typography_hint=_pick_text(current.typography_hint if current else "", fallback.typography_hint),
                copy_source=copy_bundle["copy_source"],
                subject_occupancy_ratio=(current.subject_occupancy_ratio if current else None) or fallback.subject_occupancy_ratio,
                aspect_ratio=_pick_text(current.aspect_ratio if current else "", fallback.aspect_ratio),
                image_size=_pick_text(current.image_size if current else "", fallback.image_size),
            )
        )
    return PromptPlanV2(shots=normalized)


def _build_prompt_logs(prompt_plan: PromptPlanV2) -> list[str]:
    """输出 prompt 计划摘要日志。"""

    logs = [f"[prompt_refine_v2] shot_count={len(prompt_plan.shots)}"]
    for shot in prompt_plan.shots:
        logs.append(
            f"[prompt_refine_v2] shot={shot.shot_id} role={shot.shot_role} copy_source={shot.copy_source} title={shot.title_copy} subtitle={shot.subtitle_copy} selling_points={shot.selling_points_for_render}"
        )
    return logs


def _resolve_copy_bundle(
    *,
    task: Task,
    shot: DirectorShot | None,
    candidate: PromptShot | None,
    fallback: PromptShot | None = None,
) -> dict[str, object]:
    """统一处理手动文案优先级与自动补位逻辑。"""

    user_title = str(task.title_text or "").strip()
    user_subtitle = str(task.subtitle_text or "").strip()
    user_selling_points = list(task.selling_points or [])
    shot_role = shot.shot_role if shot is not None else (fallback.shot_role if fallback is not None else "")

    if user_title:
        title_copy = user_title
    elif task.copy_mode == CopyMode.MANUAL:
        title_copy = ""
    else:
        candidate_title = candidate.title_copy if candidate is not None else ""
        fallback_title = fallback.title_copy if fallback is not None else TITLE_FALLBACKS.get(shot_role, "质感好茶")
        title_copy = _normalize_auto_title(candidate_title, fallback_title)

    if user_subtitle:
        subtitle_copy = user_subtitle
    elif task.copy_mode == CopyMode.MANUAL:
        subtitle_copy = ""
    else:
        candidate_subtitle = candidate.subtitle_copy if candidate is not None else ""
        fallback_subtitle = fallback.subtitle_copy if fallback is not None else SUBTITLE_FALLBACKS.get(shot_role, "包装主体稳定卖点清晰")
        subtitle_copy = _normalize_auto_subtitle(candidate_subtitle, fallback_subtitle)

    if user_selling_points:
        selling_points_for_render = user_selling_points
    elif task.copy_mode == CopyMode.MANUAL:
        selling_points_for_render = []
    else:
        if candidate is not None and candidate.selling_points_for_render:
            selling_points_for_render = candidate.selling_points_for_render
        elif shot is not None and shot.selling_points:
            selling_points_for_render = shot.selling_points
        elif fallback is not None and fallback.selling_points_for_render:
            selling_points_for_render = fallback.selling_points_for_render
        else:
            selling_points_for_render = []

    if user_title or user_subtitle or user_selling_points:
        copy_source = "user"
    elif task.copy_mode == CopyMode.MANUAL:
        copy_source = "manual_empty"
    else:
        copy_source = "auto"
    return {
        "title_copy": title_copy,
        "subtitle_copy": subtitle_copy,
        "selling_points_for_render": selling_points_for_render,
        "copy_source": copy_source,
    }


def _resolve_layout_hint(shot: DirectorShot) -> str:
    """返回各 shot 的默认文字区域与层级提示。"""

    if shot.shot_role == "hero":
        return "产品主体约占画面 2/3，标题副标题放左上或右上，卖点弱化纵向排列，不遮挡主包装"
    if shot.shot_role in {"gift_scene", "lifestyle"}:
        return "顶部或侧边保留简洁文字区，主标题最强，副标题次之，卖点最弱"
    return shot.layout_hint or "顶部或右侧预留信息区，不遮挡关键产品区"


def _resolve_typography_hint(shot: DirectorShot) -> str:
    """返回各 shot 的默认字体层级提示。"""

    if shot.typography_hint:
        return shot.typography_hint
    if shot.shot_role == "hero":
        return "主标题最大且最醒目，副标题次之，卖点最弱；整体干净克制。"
    return "主标题和卖点信息保持商业级清晰，可读但不喧宾夺主。"


def _normalize_auto_title(candidate: str, fallback: str) -> str:
    """把自动生成主标题约束到 4-8 字附近。"""

    text = "".join(str(candidate or "").split())
    if 4 <= len(text) <= 8:
        return text
    return fallback


def _normalize_auto_subtitle(candidate: str, fallback: str) -> str:
    """把自动生成副标题约束到 8-15 字附近。"""

    text = "".join(str(candidate or "").split())
    if 8 <= len(text) <= 15:
        return text
    return fallback


def _pick_text(candidate: str, fallback: str) -> str:
    """优先返回非空文本。"""

    return str(candidate or "").strip() or str(fallback or "").strip()
