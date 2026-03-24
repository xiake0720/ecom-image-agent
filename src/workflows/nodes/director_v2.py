"""v2 图组导演节点。

文件位置：
- `src/workflows/nodes/director_v2.py`

职责：
- 基于任务与素材摘要生成固定 8 张图的导演规划
- 落盘 `director_output.json`
- 在导演阶段明确产品保真约束、背景风格参考约束与首图主体占比
"""

from __future__ import annotations

from src.domain.director_output import DirectorOutput, DirectorShot
from src.domain.task import CopyMode, Task
from src.services.assets.reference_selector import ReferenceSelection, select_reference_bundle
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
    selection = select_reference_bundle(state.get("assets", []), max_images=2, max_background_style_images=2)
    fallback_output = _build_fallback_director_output(task=task, selection=selection)
    logs = [
        *state.get("logs", []),
        f"[director_v2] start platform={task.platform} shot_count={task.shot_count}",
        f"[director_v2] template_source={describe_prompt_source('director_v2.md')}",
        f"[director_v2] product_reference_asset_ids={[asset.asset_id for asset in selection.product_reference_assets]}",
        f"[director_v2] background_style_asset_ids={selection.background_style_asset_ids}",
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
        extra_payload={
            "product_reference_asset_ids": [asset.asset_id for asset in selection.product_reference_assets],
            "background_style_asset_ids": selection.background_style_asset_ids,
            "fallback_hash": hash_state_payload(fallback_output),
        },
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
        director_output = _normalize_director_output(director_output, fallback_output, task=task)
    else:
        director_output = fallback_output

    deps.storage.save_json_artifact(task.task_id, "director_output.json", director_output)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("director_v2", cache_key, director_output, metadata=cache_context)
    logs.extend(_build_director_logs(director_output))
    logs.append("[director_v2] saved director_output.json")
    return {"director_output": director_output, "logs": logs}


def _build_director_prompt(*, task: Task, selection: ReferenceSelection, fallback_output: DirectorOutput) -> str:
    """构建导演节点提示词输入。"""

    context = {
        "brand_name": task.brand_name,
        "product_name": task.product_name,
        "platform": task.platform,
        "shot_count": task.shot_count,
        "style_type": task.style_type,
        "style_preferences": task.style_preferences,
        "custom_elements": task.custom_elements,
        "avoid_elements": task.avoid_elements,
        "copy_mode": task.copy_mode.value,
        "title_text": task.title_text,
        "subtitle_text": task.subtitle_text,
        "user_selling_points": task.selling_points,
        "product_reference_asset_ids": [asset.asset_id for asset in selection.product_reference_assets],
        "background_style_asset_ids": selection.background_style_asset_ids,
        "background_style_reference_usage": "只学习背景氛围、色调、场景语言，不得替换产品包装，也不得提取其中可见文字。",
        "fallback_output": fallback_output,
    }
    return (
        "请为当前电商商品生成一组固定 8 张图的导演规划。\n"
        "只输出符合 DirectorOutput schema 的 JSON。\n"
        "要保证每张图角色明确、整组风格统一、便于后续生成带文案的电商图。\n"
        "硬约束：忽略参考图中的可见文案内容，不得将其转写、复用、概括为广告文案。\n"
        "硬约束：参考图只用于学习包装结构、颜色、材质、陈列方式、氛围与风格，不用于提取广告文字。\n"
        "硬约束：产品参考图用于保持包装结构、材质、颜色与标签一致；背景风格参考图只用于背景氛围。\n"
        "硬约束：hero 图必须产品优先，主体视觉面积约占画面 60%-70%，约等于 2/3，不允许商品过小。\n\n"
        f"director_context:\n{dump_pretty(context)}"
    )


def _build_fallback_director_output(*, task: Task, selection: ReferenceSelection) -> DirectorOutput:
    """构建稳定可用的导演兜底结果。"""

    role_templates = {
        "hero": ("建立品牌第一视觉", "高端电商首图", "突出完整外包装与品牌识别"),
        "packaging_feature": ("展示包装细节", "确认包装工艺", "放大标签、材质或结构细节"),
        "dry_leaf_detail": ("展示干茶细节", "说明原料品质", "让干茶细节清晰可辨"),
        "tea_soup": ("展示冲泡效果", "建立饮用感", "让茶汤成为视觉焦点"),
        "brewed_leaf_detail": ("展示叶底状态", "强化真实感", "让叶底细节真实自然"),
        "gift_scene": ("强化礼赠价值", "提升送礼感知", "礼赠场景辅助商品，但不能喧宾夺主"),
        "lifestyle": ("建立日常饮用场景", "提升生活方式感", "让商品融入克制的生活方式场景"),
        "process_or_quality": ("补充品质背书", "承接转化说明", "让商品与品质说明同框出现"),
    }
    shots: list[DirectorShot] = []
    for index, role in enumerate(DIRECTOR_ROLES[: max(1, min(task.shot_count, len(DIRECTOR_ROLES)))], start=1):
        objective, audience, scene = role_templates[role]
        subject_ratio = 0.66 if role == "hero" else None
        product_scale_guideline = _resolve_product_scale_guideline(role)
        shots.append(
            DirectorShot(
                shot_id=f"shot_{index:02d}",
                shot_role=role,
                objective=objective,
                audience=audience,
                selling_points=_resolve_director_selling_points(task=task, shot_role=role),
                scene=scene,
                composition=_resolve_composition(task=task, shot_role=role),
                visual_focus=f"{task.brand_name} {task.product_name} 的包装主体与商业展示重点",
                copy_direction=_resolve_copy_direction(task=task, shot_role=role),
                compliance_notes=_resolve_compliance_notes(selection=selection),
                product_scale_guideline=product_scale_guideline,
                subject_occupancy_ratio=subject_ratio,
                layout_hint=_resolve_layout_hint(role),
                typography_hint=_resolve_typography_hint(role),
            )
        )
    return DirectorOutput(
        product_summary=(
            f"{task.brand_name} {task.product_name}，平台={task.platform}，需要输出 {len(shots)} 张电商图。"
            f"产品参考图 {len(selection.product_reference_assets)} 张，背景风格参考图 {len(selection.background_style_assets)} 张。"
        ),
        category=task.category,
        platform=task.platform,
        visual_style=_resolve_visual_style(task),
        shots=shots,
    )


def _normalize_director_output(candidate: DirectorOutput, fallback_output: DirectorOutput, *, task: Task) -> DirectorOutput:
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
                selling_points=_resolve_normalized_selling_points(current=current, fallback=fallback_shot, task=task),
                scene=_pick_text(current.scene, fallback_shot.scene),
                composition=_pick_text(current.composition, fallback_shot.composition),
                visual_focus=_pick_text(current.visual_focus, fallback_shot.visual_focus),
                copy_direction=_pick_text(current.copy_direction, fallback_shot.copy_direction),
                compliance_notes=current.compliance_notes or fallback_shot.compliance_notes,
                product_scale_guideline=_pick_text(current.product_scale_guideline, fallback_shot.product_scale_guideline),
                subject_occupancy_ratio=current.subject_occupancy_ratio or fallback_shot.subject_occupancy_ratio,
                layout_hint=_pick_text(current.layout_hint, fallback_shot.layout_hint),
                typography_hint=_pick_text(current.typography_hint, fallback_shot.typography_hint),
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
        logs.append(
            f"[director_v2] shot={shot.shot_id} role={shot.shot_role} objective={shot.objective} subject_occupancy_ratio={shot.subject_occupancy_ratio}"
        )
    return logs


def _resolve_visual_style(task: Task) -> str:
    """拼装整组视觉风格摘要。"""

    segments = [f"{task.platform} 电商风格", f"风格类型：{task.style_type}", "包装主体稳定", "光线干净", "整体高级克制"]
    if task.style_preferences:
        segments.append(f"风格偏好：{task.style_preferences}")
    if task.custom_elements:
        segments.append(f"可加入元素：{'、'.join(task.custom_elements)}")
    if task.avoid_elements:
        segments.append(f"避免元素：{'、'.join(task.avoid_elements)}")
    return "；".join(segments) + "。"


def _resolve_director_selling_points(*, task: Task, shot_role: str) -> list[str]:
    """确定导演层卖点输入来源。"""

    if task.selling_points:
        return list(task.selling_points)
    defaults: dict[str, list[str]] = {
        "hero": ["品牌识别", "包装质感"],
        "packaging_feature": ["包装细节", "材质工艺"],
        "dry_leaf_detail": ["干茶形态", "原料状态"],
        "tea_soup": ["汤色", "通透感"],
        "brewed_leaf_detail": ["叶底状态", "品质感"],
        "gift_scene": ["礼赠场景", "高端感"],
        "lifestyle": ["日常饮茶", "生活方式"],
        "process_or_quality": ["品质背书", "工艺感"],
    }
    return defaults.get(shot_role, ["包装主体", "品质感"])


def _resolve_composition(*, task: Task, shot_role: str) -> str:
    """生成各图位的导演层构图要求。"""

    if shot_role == "hero":
        return (
            "产品优先，商品主体明显放大，视觉面积约占画面 60%-70%，约等于 2/3；"
            "文字区只占次要区域，不能因为留白过大导致商品过小；装饰元素最弱。"
        )
    return (
        "遵循正常商业审美，主包装识别优先，保留清晰文字区，不让背景和装饰元素压过商品主体；"
        f"风格类型围绕“{task.style_type}”展开。"
    )


def _resolve_copy_direction(*, task: Task, shot_role: str) -> str:
    """生成导演层文案方向说明。"""

    if task.title_text or task.subtitle_text or task.selling_points:
        if task.copy_mode == CopyMode.MANUAL:
            return "图内广告文案只允许使用用户输入原文，不得改写，不得借用参考图可见文字。"
        return "用户输入文案优先，缺失字段才允许自动补齐；严禁借用参考图可见文字。"
    if shot_role == "hero":
        return "主标题精炼稳定，副标题承接核心卖点，必须由当前流程生成，禁止参考图文案泄漏。"
    return "副标题与卖点服务转化表达，必须由当前流程生成，禁止参考图文案泄漏。"


def _resolve_compliance_notes(*, selection: ReferenceSelection) -> list[str]:
    """生成导演层硬约束。"""

    notes = [
        "不改品牌识别",
        "不夸大功效",
        "不让场景压过商品主体",
        "忽略参考图中的可见文案内容，不得转写、复用、概括为广告文案",
        "参考图只用于学习包装结构、颜色、材质、陈列方式、氛围与风格，不用于提取广告文字",
    ]
    if selection.background_style_assets:
        notes.append("背景风格参考图只影响背景氛围，不得替换产品包装")
    return notes


def _resolve_product_scale_guideline(shot_role: str) -> str:
    """生成主体比例指导。"""

    if shot_role == "hero":
        return "产品主体大面积占据画面视觉中心，约占画面 2/3，商品必须先于背景被看见。"
    return "商品主体保持商业级清晰识别，主体尺寸服从正常转化构图，不必强制 2/3。"


def _resolve_layout_hint(shot_role: str) -> str:
    """生成导演层版式提示。"""

    if shot_role == "hero":
        return "左上或右上预留标题副标题区，卖点弱化排列，不遮挡主包装"
    if shot_role in {"gift_scene", "lifestyle"}:
        return "顶部或侧边保留简洁文案区，商品主体仍需先被看见"
    return "顶部或右侧预留清晰信息区，不遮挡关键产品区"


def _resolve_typography_hint(shot_role: str) -> str:
    """生成导演层文字层级提示。"""

    if shot_role == "hero":
        return "主标题最大，副标题次之，卖点最弱；整体克制、干净、商业化。"
    return "主标题或卖点信息要清晰，但不能压过产品主体；避免花哨字体效果。"


def _resolve_normalized_selling_points(*, current: DirectorShot, fallback: DirectorShot, task: Task) -> list[str]:
    """统一导演层卖点来源。"""

    if task.selling_points:
        return list(task.selling_points)
    return current.selling_points or fallback.selling_points


def _pick_text(candidate: str, fallback: str) -> str:
    """优先返回非空文本。"""

    return str(candidate or "").strip() or str(fallback or "").strip()
