"""v2 生图 prompt 精修节点。

文件位置：
- `src/workflows/nodes/prompt_refine_v2.py`

职责：
- 把导演规划收口为可执行的逐图 prompt
- 同时生成主标题、副标题与版式提示
- 落盘 `prompt_plan_v2.json`
"""

from __future__ import annotations

from src.core.config import get_settings
from src.domain.director_output import DirectorOutput
from src.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
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
    "hero": "东方茶礼",
    "packaging_feature": "细节见真",
    "dry_leaf_detail": "条索清晰",
    "tea_soup": "汤色透亮",
    "brewed_leaf_detail": "叶底鲜活",
    "gift_scene": "礼赠有面",
    "lifestyle": "日常雅饮",
    "process_or_quality": "品质把关",
}

SUBTITLE_FALLBACKS: dict[str, str] = {
    "hero": "主包装识别一眼清晰",
    "packaging_feature": "包装细节与质感更清楚",
    "dry_leaf_detail": "干茶状态真实可辨",
    "tea_soup": "茶汤通透自然有质感",
    "brewed_leaf_detail": "叶底状态真实自然",
    "gift_scene": "礼赠场景更显高级得体",
    "lifestyle": "融入克制的日常饮茶场景",
    "process_or_quality": "卖点说明更聚焦更可信",
}


def prompt_refine_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """基于导演规划生成 v2 最终 prompt 计划。"""

    task = state["task"]
    director_output = state.get("director_output")
    if director_output is None:
        raise RuntimeError("prompt_refine_v2 requires director_output")

    settings = get_settings()
    fallback_plan = _build_fallback_prompt_plan(
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
        extra_payload={"director_output_hash": hash_state_payload(director_output)},
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
        prompt = _build_prompt(director_output=director_output, fallback_plan=fallback_plan)
        prompt_plan = deps.planning_provider.generate_structured(
            prompt,
            PromptPlanV2,
            system_prompt=load_prompt_text("prompt_refine_v2.md"),
        )
        prompt_plan = _normalize_prompt_plan(prompt_plan, fallback_plan)
    else:
        prompt_plan = fallback_plan

    deps.storage.save_json_artifact(task.task_id, "prompt_plan_v2.json", prompt_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("prompt_refine_v2", cache_key, prompt_plan, metadata=cache_context)
    logs.extend(_build_prompt_logs(prompt_plan))
    logs.append("[prompt_refine_v2] saved prompt_plan_v2.json")
    return {"prompt_plan_v2": prompt_plan, "logs": logs}


def _build_prompt(*, director_output: DirectorOutput, fallback_plan: PromptPlanV2) -> str:
    """构建 v2 prompt 计划节点提示词。"""

    context = {"director_output": director_output, "fallback_plan": fallback_plan}
    return (
        "请基于导演规划生成最终可执行的 PromptPlanV2。\n"
        "必须保持 shot_id 与 shot_role 不变。\n"
        "主标题建议 4-8 字，副标题建议 8-15 字。\n"
        "render_prompt 必须可直接交给图片模型执行，并明确保护包装主体、品牌识别与文案留白。\n\n"
        f"prompt_refine_context:\n{dump_pretty(context)}"
    )


def _build_fallback_prompt_plan(
    *,
    director_output: DirectorOutput,
    aspect_ratio: str,
    image_size: str,
    brand_name: str,
    product_name: str,
) -> PromptPlanV2:
    """构建稳定可用的 v2 prompt 兜底计划。"""

    shots = [
        PromptShot(
            shot_id=shot.shot_id,
            shot_role=shot.shot_role,
            render_prompt=_build_render_prompt(
                brand_name=brand_name,
                product_name=product_name,
                visual_style=director_output.visual_style,
                shot=shot,
            ),
            title_copy=TITLE_FALLBACKS.get(shot.shot_role, "质感好茶"),
            subtitle_copy=SUBTITLE_FALLBACKS.get(shot.shot_role, "包装主体稳定，卖点表达清晰"),
            layout_hint=_resolve_layout_hint(shot.shot_role),
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        for shot in director_output.shots
    ]
    return PromptPlanV2(shots=shots)


def _build_render_prompt(*, brand_name: str, product_name: str, visual_style: str, shot) -> str:
    """拼装单张图的执行 prompt。"""

    return "\n".join(
        [
            f"为 {brand_name} {product_name} 生成一张 {shot.shot_role} 电商图。",
            f"目标：{shot.objective}",
            f"受众：{shot.audience}",
            f"卖点：{'、'.join(shot.selling_points)}",
            f"场景：{shot.scene}",
            f"构图：{shot.composition}",
            f"视觉焦点：{shot.visual_focus}",
            f"文案方向：{shot.copy_direction}",
            f"整组风格：{visual_style}",
            "必须保留商品包装主体、品牌识别与标签层级，不要夸大功效，不要让道具压过商品。",
            "画面需要给主标题与副标题预留清晰可读的留白区域。",
        ]
    )


def _normalize_prompt_plan(candidate: PromptPlanV2, fallback_plan: PromptPlanV2) -> PromptPlanV2:
    """对齐 shot_id 并补齐缺失字段。"""

    shot_by_id = {shot.shot_id: shot for shot in candidate.shots}
    normalized: list[PromptShot] = []
    for fallback in fallback_plan.shots:
        current = shot_by_id.get(fallback.shot_id)
        if current is None:
            normalized.append(fallback)
            continue
        normalized.append(
            PromptShot(
                shot_id=fallback.shot_id,
                shot_role=fallback.shot_role,
                render_prompt=_pick_text(current.render_prompt, fallback.render_prompt),
                title_copy=_normalize_title(_pick_text(current.title_copy, fallback.title_copy), fallback.title_copy),
                subtitle_copy=_normalize_subtitle(_pick_text(current.subtitle_copy, fallback.subtitle_copy), fallback.subtitle_copy),
                layout_hint=_pick_text(current.layout_hint, fallback.layout_hint),
                aspect_ratio=_pick_text(current.aspect_ratio, fallback.aspect_ratio),
                image_size=_pick_text(current.image_size, fallback.image_size),
            )
        )
    return PromptPlanV2(shots=normalized)


def _build_prompt_logs(prompt_plan: PromptPlanV2) -> list[str]:
    """输出 prompt 计划摘要日志。"""

    logs = [f"[prompt_refine_v2] shot_count={len(prompt_plan.shots)}"]
    for shot in prompt_plan.shots:
        logs.append(
            f"[prompt_refine_v2] shot={shot.shot_id} role={shot.shot_role} title={shot.title_copy} subtitle={shot.subtitle_copy}"
        )
    return logs


def _resolve_layout_hint(shot_role: str) -> str:
    """返回各 shot 的默认留白位置。"""

    if shot_role in {"hero", "gift_scene"}:
        return "top_left clean copy space"
    if shot_role in {"packaging_feature", "process_or_quality"}:
        return "top_right clean copy space"
    return "top_left keep away from product subject"


def _normalize_title(candidate: str, fallback: str) -> str:
    """把主标题约束到 4-8 字附近。"""

    text = "".join(str(candidate or "").split())
    if 4 <= len(text) <= 8:
        return text
    return fallback


def _normalize_subtitle(candidate: str, fallback: str) -> str:
    """把副标题约束到 8-15 字附近。"""

    text = "".join(str(candidate or "").split())
    if 8 <= len(text) <= 15:
        return text
    return fallback


def _pick_text(candidate: str, fallback: str) -> str:
    """优先返回非空文本。"""

    return str(candidate or "").strip() or str(fallback or "").strip()
