"""v2 生图 prompt 精修节点。

文件位置：
- `src/workflows/nodes/prompt_refine_v2.py`

职责：
- 把导演规划收口为可执行的逐图 prompt
- 自动决定每张图的文案强弱、标题副标题和版式提示
- 明确禁止参考图文案泄漏，并区分产品参考图与背景风格参考图
"""

from __future__ import annotations

from backend.engine.core.config import get_settings
from backend.engine.domain.director_output import DirectorOutput, DirectorShot
from backend.engine.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from backend.engine.domain.task import Task
from backend.engine.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from backend.engine.workflows.nodes.prompt_utils import describe_prompt_source, dump_pretty, load_prompt_text
from backend.engine.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

TITLE_FALLBACKS: dict[str, str] = {
    "hero": "东方茶礼",
    "packaging_feature": "包装见质",
    "dry_leaf_detail": "",
    "tea_soup": "",
    "brewed_leaf_detail": "",
    "gift_scene": "礼赠有面",
    "lifestyle": "",
    "process_or_quality": "品质把关",
}

SUBTITLE_FALLBACKS: dict[str, str] = {
    "hero": "包装主体清晰高级耐看",
    "packaging_feature": "结构与材质细节更清楚",
    "dry_leaf_detail": "",
    "tea_soup": "",
    "brewed_leaf_detail": "",
    "gift_scene": "礼赠氛围高级得体",
    "lifestyle": "",
    "process_or_quality": "品质表达清晰可信",
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
    )
    logs = [
        *state.get("logs", []),
        f"[prompt_refine_v2] start shot_count={len(director_output.shots)}",
        f"[prompt_refine_v2] template_source={describe_prompt_source('prompt_refine_v2.md')}",
        f"[prompt_refine_v2] style_type={task.style_type}",
        f"[prompt_refine_v2] style_notes={task.style_notes or '-'}",
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
            "style_type": task.style_type,
            "style_notes": task.style_notes,
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
        "user_high_level_intent": {
            "brand_name": task.brand_name,
            "product_name": task.product_name,
            "style_type": task.style_type,
            "style_notes": task.style_notes,
        },
        "director_output": director_output,
        "fallback_plan": fallback_plan,
    }
    return (
        "请基于导演规划生成最终可执行的 PromptPlanV2。\n"
        "用户没有提供逐张图标题、副标题、卖点，文案必须由系统内部自动决定。\n"
        "必须保持 shot_id 与 shot_role 不变。\n"
        "必须根据 shot_role 自动决定哪些图 strong 文案，哪些图 light 文案，哪些图 none。\n"
        "hero 图可带主标题和短副标题；packaging_feature / process_or_quality / gift_scene 可带适量文案；"
        "dry_leaf_detail / tea_soup / brewed_leaf_detail / lifestyle 默认少字或无字。\n"
        "允许适度使用 brand_name / product_name 作为文案锚点，但不得抄参考图可见文字，也不得把包装标签文字当广告文案。\n"
        "render_prompt 必须可直接交给图片模型执行，并明确保护包装主体、品牌识别与文字留白。\n"
        "hero 图必须明确主体视觉面积约占画面 60%-70%，约等于 2/3。\n"
        "背景风格参考图只用于学习背景氛围、色调、场景语言和材质语言，不得替换产品包装，不得提供广告文字。\n\n"
        f"prompt_refine_context:\n{dump_pretty(context)}"
    )


def _build_fallback_prompt_plan(
    *,
    task: Task,
    director_output: DirectorOutput,
    aspect_ratio: str,
    image_size: str,
) -> PromptPlanV2:
    """构建稳定可用的 v2 prompt 兜底计划。"""

    shots: list[PromptShot] = []
    for shot in director_output.shots:
        copy_bundle = _resolve_copy_bundle(task=task, shot=shot, candidate=None)
        layout_hint = _resolve_layout_hint(shot, copy_bundle["should_render_text"])
        typography_hint = _resolve_typography_hint(shot, copy_bundle["should_render_text"])
        subject_occupancy_ratio = shot.subject_occupancy_ratio if shot.subject_occupancy_ratio is not None else (0.66 if shot.shot_role == "hero" else None)
        shots.append(
            PromptShot(
                shot_id=shot.shot_id,
                shot_role=shot.shot_role,
                render_prompt=_build_render_prompt(
                    task=task,
                    visual_style=director_output.visual_style,
                    series_strategy=director_output.series_strategy,
                    background_style_strategy=director_output.background_style_strategy,
                    shot=shot,
                    copy_bundle=copy_bundle,
                    layout_hint=layout_hint,
                    typography_hint=typography_hint,
                ),
                copy_strategy=copy_bundle["copy_strategy"],
                text_density=copy_bundle["text_density"],
                should_render_text=copy_bundle["should_render_text"],
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
    visual_style: str,
    series_strategy: str,
    background_style_strategy: str,
    shot: DirectorShot,
    copy_bundle: dict[str, object],
    layout_hint: str,
    typography_hint: str,
) -> str:
    """拼装单张图的执行 prompt。"""

    product_label = _product_label(task)
    lines = [
        f"为 {product_label} 生成一张 {shot.shot_role} 电商图。",
        f"目标：{shot.objective}",
        f"受众：{shot.audience}",
        f"卖点方向：{'、'.join(shot.selling_point_direction)}",
        f"场景：{shot.scene}",
        f"构图：{shot.composition}",
        f"视觉焦点：{shot.visual_focus}",
        f"文案目标：{shot.copy_goal}",
        f"文案策略：{copy_bundle['copy_strategy']}",
        f"文字密度：{copy_bundle['text_density']}",
        f"主体比例要求：{shot.product_scale_guideline}",
        f"整组风格：{visual_style}",
        f"整套策略：{series_strategy}",
        f"背景风格策略：{background_style_strategy}",
        f"该图位背景参考策略：{shot.style_reference_policy}",
        f"版式提示：{layout_hint}",
        f"文字层级：{typography_hint}",
        "必须保留商品包装主体、品牌识别、颜色、材质与标签层级，不要夸大功效，不要让道具压过商品。",
        "严禁转写、复用、概括任何参考图可见文字，也不得把包装标签文字当作广告文案。",
        "产品参考图只用于保持产品主体真实一致；背景风格参考图只用于背景氛围，不得替换产品主体。",
    ]
    if task.style_notes:
        lines.append(f"风格补充说明：{task.style_notes}")
    if copy_bundle["should_render_text"]:
        lines.append("本图允许适度广告文字，但文字必须直接融入画面，不要做简陋文本框，不要遮挡关键产品区。")
    else:
        lines.append("本图优先不出现广告大字，必要时也只允许极轻的文字提示，重点呈现画面质感和产品细节。")
    return "\n".join(lines)


def _normalize_prompt_plan(candidate: PromptPlanV2, fallback_plan: PromptPlanV2, *, task: Task) -> PromptPlanV2:
    """对齐 shot_id，补齐缺失字段，并强制按图位执行自动文案策略。"""

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
                copy_strategy=copy_bundle["copy_strategy"],
                text_density=copy_bundle["text_density"],
                should_render_text=copy_bundle["should_render_text"],
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
            "[prompt_refine_v2] "
            f"shot={shot.shot_id} role={shot.shot_role} copy_strategy={shot.copy_strategy} "
            f"should_render_text={str(shot.should_render_text).lower()} copy_source={shot.copy_source} "
            f"title={shot.title_copy or '-'} subtitle={shot.subtitle_copy or '-'} selling_points={shot.selling_points_for_render}"
        )
    return logs


def _resolve_copy_bundle(
    *,
    task: Task,
    shot: DirectorShot | None,
    candidate: PromptShot | None,
    fallback: PromptShot | None = None,
) -> dict[str, object]:
    """统一处理系统自动文案策略。"""

    shot_role = shot.shot_role if shot is not None else (fallback.shot_role if fallback is not None else "")
    role_policy = _resolve_role_policy(shot_role)

    # 导演层已将细节图/茶汤图设为弱文案或无文案，这里必须继续收口，避免模型回摆。
    if not role_policy["should_render_text"]:
        return {
            "copy_strategy": "none",
            "text_density": "none",
            "should_render_text": False,
            "title_copy": "",
            "subtitle_copy": "",
            "selling_points_for_render": [],
            "copy_source": "system_auto",
        }

    title_candidate = candidate.title_copy if candidate is not None else ""
    subtitle_candidate = candidate.subtitle_copy if candidate is not None else ""
    selling_points_candidate = candidate.selling_points_for_render if candidate is not None else []

    title_fallback = _build_fallback_title(task=task, shot_role=shot_role)
    subtitle_fallback = _build_fallback_subtitle(task=task, shot_role=shot_role)
    title_copy = _normalize_auto_title(title_candidate, title_fallback)
    subtitle_copy = _normalize_auto_subtitle(subtitle_candidate, subtitle_fallback)
    selling_points_for_render = _normalize_selling_points(
        candidate_points=selling_points_candidate,
        fallback_points=(shot.selling_point_direction if shot is not None else fallback.selling_points_for_render if fallback else []),
        shot_role=shot_role,
    )

    copy_source = "system_brand_anchor" if _uses_brand_anchor(task, title_copy, subtitle_copy) else "system_auto"
    return {
        "copy_strategy": _normalize_copy_strategy(candidate.copy_strategy if candidate is not None else "", role_policy["copy_strategy"]),
        "text_density": _normalize_text_density(candidate.text_density if candidate is not None else "", role_policy["text_density"]),
        "should_render_text": True,
        "title_copy": title_copy,
        "subtitle_copy": subtitle_copy,
        "selling_points_for_render": selling_points_for_render,
        "copy_source": copy_source,
    }


def _resolve_layout_hint(shot: DirectorShot, should_render_text: bool) -> str:
    """返回各 shot 的默认文字区域与层级提示。"""

    if shot.shot_role == "hero":
        return "产品主体约占画面 2/3，标题副标题放左上或右上，卖点弱化纵向排列，不遮挡主包装"
    if not should_render_text:
        return "尽量保持干净留白，不设置大面积文案区，不遮挡产品或细节主体"
    if shot.shot_role in {"gift_scene", "lifestyle"}:
        return "顶部或侧边保留简洁文字区，信息轻量，不打断场景氛围"
    return shot.layout_hint or "顶部或右侧预留信息区，不遮挡关键产品区"


def _resolve_typography_hint(shot: DirectorShot, should_render_text: bool) -> str:
    """返回各 shot 的默认字体层级提示。"""

    if shot.typography_hint and should_render_text:
        return shot.typography_hint
    if not should_render_text:
        return "优先无字；若必须带字，仅允许极轻提示，不可喧宾夺主。"
    if shot.shot_role == "hero":
        return "主标题最大且最醒目，副标题次之，卖点最弱；整体干净克制。"
    return "标题和卖点保持商业级清晰，可读但不喧宾夺主。"


def _resolve_role_policy(shot_role: str) -> dict[str, object]:
    """按图位返回自动文案策略。"""

    if shot_role == "hero":
        return {"copy_strategy": "strong", "text_density": "medium", "should_render_text": True}
    if shot_role in {"packaging_feature", "process_or_quality"}:
        return {"copy_strategy": "strong", "text_density": "medium", "should_render_text": True}
    if shot_role == "gift_scene":
        return {"copy_strategy": "light", "text_density": "low", "should_render_text": True}
    return {"copy_strategy": "none", "text_density": "none", "should_render_text": False}


def _build_fallback_title(*, task: Task, shot_role: str) -> str:
    """生成系统兜底标题。"""

    if shot_role == "hero":
        product_token = _pick_product_token(task)
        return _trim_text(product_token or TITLE_FALLBACKS[shot_role], min_len=3, max_len=8, fallback=TITLE_FALLBACKS[shot_role])
    return TITLE_FALLBACKS.get(shot_role, "")


def _build_fallback_subtitle(*, task: Task, shot_role: str) -> str:
    """生成系统兜底副标题。"""

    if shot_role == "hero":
        subject = "".join(part for part in [task.product_name or "", "包装主体清晰高级"] if part)
        return _trim_text(subject, min_len=8, max_len=15, fallback=SUBTITLE_FALLBACKS[shot_role])
    if shot_role == "gift_scene" and task.brand_name:
        subject = f"{task.brand_name}礼赠场景高级得体"
        return _trim_text(subject, min_len=8, max_len=15, fallback=SUBTITLE_FALLBACKS[shot_role])
    return SUBTITLE_FALLBACKS.get(shot_role, "")


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


def _normalize_selling_points(*, candidate_points: list[str], fallback_points: list[str], shot_role: str) -> list[str]:
    """把卖点短语收敛为适合图内表达的长度。"""

    if shot_role not in {"hero", "packaging_feature", "gift_scene", "process_or_quality"}:
        return []

    source = [str(item).strip() for item in candidate_points or fallback_points or [] if str(item).strip()]
    normalized: list[str] = []
    for item in source[:2]:
        compact = item.replace(" ", "")
        if len(compact) <= 8:
            normalized.append(compact)
        else:
            normalized.append(compact[:8])
    return normalized


def _normalize_copy_strategy(candidate: str, fallback: str) -> str:
    """把文案策略限制在预期集合内。"""

    value = str(candidate or "").strip().lower()
    if value in {"strong", "light", "none"}:
        return value
    return fallback


def _normalize_text_density(candidate: str, fallback: str) -> str:
    """把文字密度限制在预期集合内。"""

    value = str(candidate or "").strip().lower()
    if value in {"heavy", "medium", "low", "none"}:
        return value
    return fallback


def _product_label(task: Task) -> str:
    """生成 prompt 中的商品名称。"""

    return " ".join(part for part in [task.brand_name, task.product_name] if part).strip() or "当前商品"


def _pick_product_token(task: Task) -> str:
    """为 hero 标题挑选短的商品锚点。"""

    for token in (task.product_name, task.brand_name):
        compact = "".join(str(token or "").split())
        if 3 <= len(compact) <= 8:
            return compact
    return ""


def _trim_text(text: str, *, min_len: int, max_len: int, fallback: str) -> str:
    """把文本收敛到期望长度区间。"""

    compact = "".join(str(text or "").split())
    if min_len <= len(compact) <= max_len:
        return compact
    if len(compact) > max_len:
        return compact[:max_len]
    return fallback


def _uses_brand_anchor(task: Task, title_copy: str, subtitle_copy: str) -> bool:
    """判断自动文案是否借助了品牌/商品名锚点。"""

    anchor_parts = [part for part in [task.brand_name, task.product_name] if part]
    combined = f"{title_copy}{subtitle_copy}"
    return any(part and part in combined for part in anchor_parts)


def _pick_text(candidate: str, fallback: str) -> str:
    """优先返回非空文本。"""

    return str(candidate or "").strip() or str(fallback or "").strip()
