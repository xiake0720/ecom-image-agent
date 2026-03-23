"""v2 图组导演节点。

文件位置：
- `src/workflows/nodes/director_v2.py`

职责：
- 基于任务与素材摘要生成固定 8 张图的导演规划
- 落盘 `director_output.json`
- 不再依赖旧的 analyze/style/plan 节点
"""

from __future__ import annotations

from src.domain.director_output import DirectorOutput, DirectorShot
from src.services.assets.reference_selector import select_reference_bundle
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import describe_prompt_source, dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

DIRECTOR_ROLES: tuple[str, ...] = (
    "hero",
    "packaging_feature",
    "dry_leaf_detail",
    "tea_soup",
    "brewed_leaf_detail",
    "gift_scene",
    "lifestyle",
    "process_or_quality",
)


def director_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成 v2 导演规划并落盘。"""

    task = state["task"]
    selection = select_reference_bundle(state.get("assets", []), max_images=2)
    fallback_output = _build_fallback_director_output(
        brand_name=task.brand_name,
        product_name=task.product_name,
        platform=task.platform,
        shot_count=task.shot_count,
    )
    logs = [
        *state.get("logs", []),
        f"[director_v2] start platform={task.platform} shot_count={task.shot_count}",
        f"[director_v2] template_source={describe_prompt_source('director_v2.md')}",
        f"[director_v2] reference_asset_ids={selection.selected_asset_ids}",
        *format_connected_contract_logs(state, node_name="director_v2"),
    ]

    provider_name, provider_model_id = planning_provider_identity(deps)
    cache_key, cache_context = build_node_cache_key(
        node_name="director_v2",
        state=state,
        deps=deps,
        prompt_filename="director_v2.md" if deps.text_provider_mode == "real" else None,
        prompt_version="mock-director-v2" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={"reference_asset_ids": selection.selected_asset_ids, "fallback_hash": hash_state_payload(fallback_output)},
    )
    if should_use_cache(state):
        cached = deps.storage.load_cached_json_artifact("director_v2", cache_key, DirectorOutput)
        if cached is not None:
            deps.storage.save_json_artifact(task.task_id, "director_output.json", cached)
            return {
                "director_output": cached,
                "logs": [*logs, f"[cache] node=director_v2 status=hit key={cache_key}", "[director_v2] saved director_output.json"],
            }
        logs.append(f"[cache] node=director_v2 status=miss key={cache_key}")
    elif is_force_rerun(state):
        logs.append("[cache] node=director_v2 status=ignored key=-")

    if deps.text_provider_mode == "real":
        prompt = _build_director_prompt(task=task, selection=selection, fallback_output=fallback_output)
        director_output = deps.planning_provider.generate_structured(
            prompt,
            DirectorOutput,
            system_prompt=load_prompt_text("director_v2.md"),
        )
        director_output = _normalize_director_output(director_output, fallback_output)
    else:
        director_output = fallback_output

    deps.storage.save_json_artifact(task.task_id, "director_output.json", director_output)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("director_v2", cache_key, director_output, metadata=cache_context)
    logs.extend(_build_director_logs(director_output))
    logs.append("[director_v2] saved director_output.json")
    return {"director_output": director_output, "logs": logs}


def _build_director_prompt(*, task, selection, fallback_output: DirectorOutput) -> str:
    """构建导演节点提示词输入。"""

    context = {
        "brand_name": task.brand_name,
        "product_name": task.product_name,
        "platform": task.platform,
        "shot_count": task.shot_count,
        "reference_assets": selection.selected_asset_ids,
        "fallback_output": fallback_output,
    }
    return (
        "请为当前电商商品生成一组固定 8 张图的导演规划。\n"
        "只输出符合 DirectorOutput schema 的 JSON。\n"
        "要保证每张图角色明确、整组风格统一、便于后续生成带文案的电商图。\n\n"
        f"director_context:\n{dump_pretty(context)}"
    )


def _build_fallback_director_output(*, brand_name: str, product_name: str, platform: str, shot_count: int) -> DirectorOutput:
    """构建稳定可用的导演兜底结果。"""

    role_templates = {
        "hero": ("建立品牌第一视觉", "高端电商首图", ["品牌识别", "包装质感"], "突出完整外包装与品牌识别"),
        "packaging_feature": ("展示包装细节", "确认包装工艺", ["包装细节", "材质工艺"], "放大标签、材质或结构细节"),
        "dry_leaf_detail": ("展示干茶细节", "说明原料品质", ["干茶形态", "原料状态"], "让干茶细节清晰可辨"),
        "tea_soup": ("展示冲泡效果", "建立饮用感", ["汤色", "通透感"], "让茶汤成为视觉焦点"),
        "brewed_leaf_detail": ("展示叶底状态", "强化真实感", ["叶底状态", "品质感"], "让叶底细节真实自然"),
        "gift_scene": ("强化礼赠价值", "提升送礼感知", ["礼赠场景", "高端感"], "礼赠场景辅助商品，但不能喧宾夺主"),
        "lifestyle": ("建立日常饮用场景", "提升生活方式感", ["日常饮茶", "生活方式"], "让商品融入克制的生活方式场景"),
        "process_or_quality": ("补充品质背书", "承接转化说明", ["品质背书", "工艺感"], "让商品与品质说明同框出现"),
    }
    shots: list[DirectorShot] = []
    for index, role in enumerate(DIRECTOR_ROLES[: max(1, min(shot_count, len(DIRECTOR_ROLES)))], start=1):
        objective, audience, selling_points, scene = role_templates[role]
        shots.append(
            DirectorShot(
                shot_id=f"shot_{index:02d}",
                shot_role=role,
                objective=objective,
                audience=audience,
                selling_points=selling_points,
                scene=scene,
                composition="保留清晰文案留白，主包装识别优先",
                visual_focus=f"{brand_name} {product_name} 的包装主体与商业展示重点",
                copy_direction="主标题精炼、副标题承接卖点，整体克制而商业化",
                compliance_notes=["不改品牌识别", "不夸大功效", "不让场景压过商品主体"],
            )
        )
    return DirectorOutput(
        product_summary=f"{brand_name} {product_name}，平台={platform}，需要输出 {len(shots)} 张电商图。",
        category="tea",
        platform=platform,
        visual_style="天猫电商风格，包装主体稳定，光线干净，整体高级克制。",
        shots=shots,
    )


def _normalize_director_output(candidate: DirectorOutput, fallback_output: DirectorOutput) -> DirectorOutput:
    """按 shot_id 对齐并补齐导演结果。"""

    shot_by_id = {shot.shot_id: shot for shot in candidate.shots}
    normalized_shots: list[DirectorShot] = []
    for fallback_shot in fallback_output.shots:
        current = shot_by_id.get(fallback_shot.shot_id)
        if current is None:
            normalized_shots.append(fallback_shot)
            continue
        normalized_shots.append(
            DirectorShot(
                shot_id=fallback_shot.shot_id,
                shot_role=fallback_shot.shot_role,
                objective=_pick_text(current.objective, fallback_shot.objective),
                audience=_pick_text(current.audience, fallback_shot.audience),
                selling_points=current.selling_points or fallback_shot.selling_points,
                scene=_pick_text(current.scene, fallback_shot.scene),
                composition=_pick_text(current.composition, fallback_shot.composition),
                visual_focus=_pick_text(current.visual_focus, fallback_shot.visual_focus),
                copy_direction=_pick_text(current.copy_direction, fallback_shot.copy_direction),
                compliance_notes=current.compliance_notes or fallback_shot.compliance_notes,
            )
        )
    return DirectorOutput(
        product_summary=_pick_text(candidate.product_summary, fallback_output.product_summary),
        category=_pick_text(candidate.category, fallback_output.category),
        platform=_pick_text(candidate.platform, fallback_output.platform),
        visual_style=_pick_text(candidate.visual_style, fallback_output.visual_style),
        shots=normalized_shots,
    )


def _build_director_logs(director_output: DirectorOutput) -> list[str]:
    """输出导演结果摘要日志。"""

    logs = [
        f"[director_v2] shot_count={len(director_output.shots)}",
        f"[director_v2] visual_style={director_output.visual_style}",
    ]
    for shot in director_output.shots:
        logs.append(f"[director_v2] shot={shot.shot_id} role={shot.shot_role} objective={shot.objective}")
    return logs


def _pick_text(candidate: str, fallback: str) -> str:
    """优先返回非空文本。"""

    return str(candidate or "").strip() or str(fallback or "").strip()
