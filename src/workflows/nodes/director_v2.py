"""v2 图组导演节点。

文件位置：
- `src/workflows/nodes/director_v2.py`

职责：
- 基于产品参考图、高层风格意图与背景风格参考图生成整套导演规划
- 在导演阶段决定每张图的角色、卖点方向、文案密度与首图主体策略
- 落盘 `director_output.json`
"""

from __future__ import annotations

from src.domain.director_output import DirectorOutput, DirectorShot
from src.domain.task import Task
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

ROLE_TEMPLATES: dict[str, dict[str, object]] = {
    "hero": {
        "objective": "建立整套图的第一视觉与产品识别",
        "audience": "首次浏览商品详情页的转化型用户",
        "selling_point_direction": ["品牌识别", "包装质感", "高端印象"],
        "scene": "干净高级的电商主图场景",
        "visual_focus": "完整外包装与品牌识别必须第一眼被看见",
        "copy_goal": "用短标题建立品牌感，用短副标题补足商品识别",
    },
    "packaging_feature": {
        "objective": "放大包装细节与工艺感",
        "audience": "关注材质与包装做工的购买决策用户",
        "selling_point_direction": ["包装结构", "材质工艺", "细节品质"],
        "scene": "包装局部放大或结构展示场景",
        "visual_focus": "包装细节、边角、开合结构或材料质感",
        "copy_goal": "适度带字，强调包装细节卖点，不需要堆很多字",
    },
    "dry_leaf_detail": {
        "objective": "建立干茶细节与原料真实感",
        "audience": "在意原料形态和品质细节的用户",
        "selling_point_direction": ["干茶形态", "原料状态", "自然质感"],
        "scene": "干茶细节特写或与包装克制同框的质感场景",
        "visual_focus": "干茶条索、色泽、净度和真实质感",
        "copy_goal": "优先弱化广告文字，让画面本身表达品质感",
    },
    "tea_soup": {
        "objective": "展示茶汤通透度与饮用吸引力",
        "audience": "关注冲泡体验和口感想象的用户",
        "selling_point_direction": ["汤色通透", "冲泡质感", "饮用愉悦感"],
        "scene": "茶汤杯盏、茶席局部或通透液体表现",
        "visual_focus": "茶汤颜色、透亮感和杯盏质感",
        "copy_goal": "优先用画面表达，不强求广告文案",
    },
    "brewed_leaf_detail": {
        "objective": "补充叶底状态与真实可信度",
        "audience": "需要更多品质细节来确认购买的用户",
        "selling_point_direction": ["叶底状态", "真实可信", "细节背书"],
        "scene": "叶底近景或冲泡后的细节展示场景",
        "visual_focus": "叶底纹理、舒展状态和真实自然感",
        "copy_goal": "尽量少字或无字，避免破坏细节观感",
    },
    "gift_scene": {
        "objective": "强化礼赠属性与送礼场景想象",
        "audience": "礼赠需求明确的用户",
        "selling_point_direction": ["礼赠价值", "体面高级", "场景氛围"],
        "scene": "礼赠或节日氛围的高级场景",
        "visual_focus": "包装主体与礼赠氛围并存，但商品仍是主角",
        "copy_goal": "可带适量文案，表达礼赠感和档次感",
    },
    "lifestyle": {
        "objective": "把商品嵌入克制的生活方式场景",
        "audience": "受生活方式氛围影响的感性用户",
        "selling_point_direction": ["日常雅饮", "生活方式", "场景融合"],
        "scene": "自然克制的生活方式饮茶场景",
        "visual_focus": "商品融入场景后的质感与协调性",
        "copy_goal": "文案要弱，优先保留画面呼吸感",
    },
    "process_or_quality": {
        "objective": "补充品质说明或工艺背书图位",
        "audience": "需要更多可信理由才能下单的用户",
        "selling_point_direction": ["品质背书", "工艺感", "可信说明"],
        "scene": "品质说明或工艺感表达的转化型场景",
        "visual_focus": "商品与品质信息关系明确，信息结构清楚",
        "copy_goal": "适度带字，强调可信表达与信息清晰度",
    },
}


def director_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成 v2 导演规划并落盘。"""

    task = state["task"]
    selection = select_reference_bundle(state.get("assets", []), max_images=2, max_background_style_images=2)
    fallback_output = _build_fallback_director_output(task=task, selection=selection)
    logs = [
        *state.get("logs", []),
        f"[director_v2] start platform={task.platform} shot_count={task.shot_count}",
        f"[director_v2] template_source={describe_prompt_source('director_v2.md')}",
        f"[director_v2] style_type={task.style_type}",
        f"[director_v2] style_notes={task.style_notes or '-'}",
        f"[director_v2] product_reference_asset_ids={[asset.asset_id for asset in selection.product_reference_assets]}",
        f"[director_v2] background_style_asset_ids={selection.background_style_asset_ids}",
        *format_connected_contract_logs(state, node_name='director_v2'),
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
            "style_type": task.style_type,
            "style_notes": task.style_notes,
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
        director_output = _normalize_director_output(director_output, fallback_output)
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
        "style_notes": task.style_notes,
        "product_reference_asset_ids": [asset.asset_id for asset in selection.product_reference_assets],
        "background_style_asset_ids": selection.background_style_asset_ids,
        "background_style_reference_usage": "背景风格参考图只用于背景氛围、光线、色调、场景语言和材质语言，不能提取文案，不能替换产品主体。",
        "fallback_output": fallback_output,
    }
    return (
        "请为当前商品自动规划一整套固定 8 张电商图导演方案。\n"
        "用户输入的是整套图的高层意图，不是逐张图文案参数。\n"
        "只输出符合 DirectorOutput schema 的 JSON。\n"
        "必须自动决定每张图的 shot_role 目标、卖点方向、文案密度、是否适合带字、版式倾向和整套统一策略。\n"
        "硬约束：忽略参考图中的可见文字，不得转写、复用、概括或继承为广告文案。\n"
        "硬约束：产品参考图用于保持包装结构、材质、颜色和标签一致；背景风格参考图只用于背景氛围。\n"
        "硬约束：hero 图必须产品优先，主体视觉面积约占画面 60%-70%，约等于 2/3，不允许商品过小。\n"
        "硬约束：dry_leaf_detail / tea_soup / brewed_leaf_detail / lifestyle 默认弱文案或无文案。\n"
        "硬约束：packaging_feature / process_or_quality / gift_scene 可带适量文案，但不能堆字。\n\n"
        f"director_context:\n{dump_pretty(context)}"
    )


def _build_fallback_director_output(*, task: Task, selection: ReferenceSelection) -> DirectorOutput:
    """构建稳定可用的导演兜底结果。"""

    shots: list[DirectorShot] = []
    for index, role in enumerate(DIRECTOR_ROLES[: max(1, min(task.shot_count, len(DIRECTOR_ROLES)))], start=1):
        template = ROLE_TEMPLATES[role]
        copy_policy = _resolve_copy_policy(role)
        subject_ratio = 0.66 if role == "hero" else None
        shots.append(
            DirectorShot(
                shot_id=f"shot_{index:02d}",
                shot_role=role,
                objective=str(template["objective"]),
                audience=str(template["audience"]),
                selling_point_direction=list(template["selling_point_direction"]),
                scene=str(template["scene"]),
                composition=_resolve_composition(task=task, shot_role=role),
                visual_focus=str(template["visual_focus"]),
                copy_goal=str(template["copy_goal"]),
                copy_strategy=copy_policy["copy_strategy"],
                text_density=copy_policy["text_density"],
                should_render_text=copy_policy["should_render_text"],
                compliance_notes=_resolve_compliance_notes(selection=selection),
                product_scale_guideline=_resolve_product_scale_guideline(role),
                subject_occupancy_ratio=subject_ratio,
                layout_hint=_resolve_layout_hint(role),
                typography_hint=_resolve_typography_hint(role),
                style_reference_policy=_resolve_style_reference_policy(role),
            )
        )
    return DirectorOutput(
        product_summary=_build_product_summary(task=task, selection=selection, shot_count=len(shots)),
        category=task.category,
        platform=task.platform,
        visual_style=_resolve_visual_style(task),
        series_strategy=_resolve_series_strategy(task),
        background_style_strategy=_resolve_background_style_strategy(selection=selection),
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
        copy_policy = _resolve_copy_policy(fallback_shot.shot_role)
        normalized_shots.append(
            DirectorShot(
                shot_id=fallback_shot.shot_id,
                shot_role=fallback_shot.shot_role,
                objective=_pick_text(current.objective, fallback_shot.objective),
                audience=_pick_text(current.audience, fallback_shot.audience),
                selling_point_direction=current.selling_point_direction or fallback_shot.selling_point_direction,
                scene=_pick_text(current.scene, fallback_shot.scene),
                composition=_pick_text(current.composition, fallback_shot.composition),
                visual_focus=_pick_text(current.visual_focus, fallback_shot.visual_focus),
                copy_goal=_pick_text(current.copy_goal, fallback_shot.copy_goal),
                copy_strategy=_normalize_copy_strategy(current.copy_strategy, copy_policy["copy_strategy"]),
                text_density=_normalize_text_density(current.text_density, copy_policy["text_density"]),
                should_render_text=_normalize_should_render_text(
                    current.should_render_text,
                    fallback=fallback_shot.should_render_text,
                    role_default=copy_policy["should_render_text"],
                ),
                compliance_notes=current.compliance_notes or fallback_shot.compliance_notes,
                product_scale_guideline=_pick_text(current.product_scale_guideline, fallback_shot.product_scale_guideline),
                subject_occupancy_ratio=_normalize_subject_ratio(
                    current.subject_occupancy_ratio,
                    fallback_shot.subject_occupancy_ratio,
                    fallback_shot.shot_role,
                ),
                layout_hint=_pick_text(current.layout_hint, fallback_shot.layout_hint),
                typography_hint=_pick_text(current.typography_hint, fallback_shot.typography_hint),
                style_reference_policy=_pick_text(current.style_reference_policy, fallback_shot.style_reference_policy),
            )
        )
    return DirectorOutput(
        product_summary=_pick_text(candidate.product_summary, fallback_output.product_summary),
        category=_pick_text(candidate.category, fallback_output.category),
        platform=_pick_text(candidate.platform, fallback_output.platform),
        visual_style=_pick_text(candidate.visual_style, fallback_output.visual_style),
        series_strategy=_pick_text(candidate.series_strategy, fallback_output.series_strategy),
        background_style_strategy=_pick_text(candidate.background_style_strategy, fallback_output.background_style_strategy),
        shots=normalized_shots,
    )


def _build_director_logs(director_output: DirectorOutput) -> list[str]:
    """输出导演结果摘要日志。"""

    logs = [
        f"[director_v2] shot_count={len(director_output.shots)}",
        f"[director_v2] visual_style={director_output.visual_style}",
        f"[director_v2] series_strategy={director_output.series_strategy}",
    ]
    for shot in director_output.shots:
        logs.append(
            "[director_v2] "
            f"shot={shot.shot_id} role={shot.shot_role} copy_strategy={shot.copy_strategy} "
            f"text_density={shot.text_density} should_render_text={str(shot.should_render_text).lower()} "
            f"subject_occupancy_ratio={shot.subject_occupancy_ratio}"
        )
    return logs


def _build_product_summary(*, task: Task, selection: ReferenceSelection, shot_count: int) -> str:
    """生成导演层商品摘要。"""

    product_label = " ".join(part for part in [task.brand_name, task.product_name] if part).strip() or "当前商品"
    return (
        f"{product_label}，平台={task.platform}，自动生成 {shot_count} 张电商图。"
        f"产品参考图 {len(selection.product_reference_assets)} 张，背景风格参考图 {len(selection.background_style_assets)} 张。"
    )


def _resolve_visual_style(task: Task) -> str:
    """拼装整组视觉风格摘要。"""

    segments = [f"{task.platform} 电商风格", f"风格类型：{task.style_type}", "整套统一", "高级克制", "包装主体稳定"]
    if task.style_notes:
        segments.append(f"补充风格：{task.style_notes}")
    return "；".join(segments) + "。"


def _resolve_series_strategy(task: Task) -> str:
    """生成整套图统一策略。"""

    base = "整套图先建立包装识别，再补充细节、冲泡质感、礼赠与品质说明，形成统一且可转化的商品叙事。"
    if task.style_notes:
        return f"{base} 全套风格围绕“{task.style_type}”展开，并吸收“{task.style_notes}”的气质。"
    return f"{base} 全套风格围绕“{task.style_type}”展开。"


def _resolve_background_style_strategy(*, selection: ReferenceSelection) -> str:
    """生成背景风格参考图策略说明。"""

    if selection.background_style_assets:
        return "背景风格参考图只学习背景氛围、光线、色调、空间层次和材质语言，禁止提取文字，禁止替换产品主体。"
    return "无背景风格参考图时，背景风格完全由 style_type 和 style_notes 推导。"


def _resolve_composition(*, task: Task, shot_role: str) -> str:
    """生成各图位的导演层构图要求。"""

    if shot_role == "hero":
        return (
            "产品优先，商品主体明显放大，视觉面积约占画面 60%-70%，约等于 2/3；"
            "保留必要标题区，但不允许因为留白过大导致商品过小；装饰元素最弱。"
        )
    if shot_role in {"dry_leaf_detail", "tea_soup", "brewed_leaf_detail"}:
        return (
            "以细节质感为主，商品或细节主体清晰可辨，文字可弱化甚至取消；"
            f"整体风格继续服从“{task.style_type}”。"
        )
    return (
        "遵循正常商业审美，商品主体识别优先，留出克制信息区，避免背景和装饰元素压过商品；"
        f"整体风格继续服从“{task.style_type}”。"
    )


def _resolve_compliance_notes(*, selection: ReferenceSelection) -> list[str]:
    """生成导演层硬约束。"""

    notes = [
        "不改品牌识别",
        "不夸大功效",
        "不让场景压过商品主体",
        "忽略参考图中的可见文案内容，不得转写、复用、概括为广告文案",
        "产品参考图只用于保持包装结构、颜色、材质与标签一致",
        "背景风格参考图只用于学习背景氛围、色调、光线与场景语言",
    ]
    if selection.background_style_assets:
        notes.append("背景风格参考图不能替换产品主体，也不能改变品牌识别")
    return notes


def _resolve_product_scale_guideline(shot_role: str) -> str:
    """生成主体比例指导。"""

    if shot_role == "hero":
        return "产品主体大面积占据画面视觉中心，约占画面 2/3，商品必须先于背景被看见。"
    return "商品主体保持商业级清晰识别，主体尺寸服从该图位目的，不必强制 2/3。"


def _resolve_layout_hint(shot_role: str) -> str:
    """生成导演层版式提示。"""

    policy = _resolve_copy_policy(shot_role)
    if shot_role == "hero":
        return "左上或右上保留标题副标题区，卖点弱化排列，不遮挡主包装"
    if not policy["should_render_text"]:
        return "优先保留干净画面和主体细节，如需文字只允许很小范围弱提示"
    if shot_role in {"gift_scene", "lifestyle"}:
        return "顶部或侧边预留克制信息区，商品主体仍需先被看见"
    return "顶部或右侧预留清晰信息区，不遮挡关键产品区"


def _resolve_typography_hint(shot_role: str) -> str:
    """生成导演层文字层级提示。"""

    policy = _resolve_copy_policy(shot_role)
    if shot_role == "hero":
        return "主标题最大，副标题次之，卖点最弱；整体克制、干净、商业化。"
    if not policy["should_render_text"]:
        return "若出现文字，应极少、极轻，不破坏细节质感。"
    return "标题和卖点要清晰，但不能压过产品主体；避免花哨字体效果。"


def _resolve_style_reference_policy(shot_role: str) -> str:
    """描述该图位如何使用背景风格参考图。"""

    if shot_role == "hero":
        return "背景风格参考图只影响背景气质和光线，不改变主包装结构、颜色和品牌识别。"
    return "可参考背景风格图的色调、材质语言和空间层次，但禁止继承其中任何文字内容。"


def _resolve_copy_policy(shot_role: str) -> dict[str, object]:
    """按图位给出默认文案策略。"""

    if shot_role == "hero":
        return {"copy_strategy": "strong", "text_density": "medium", "should_render_text": True}
    if shot_role in {"packaging_feature", "process_or_quality"}:
        return {"copy_strategy": "strong", "text_density": "medium", "should_render_text": True}
    if shot_role == "gift_scene":
        return {"copy_strategy": "light", "text_density": "low", "should_render_text": True}
    return {"copy_strategy": "none", "text_density": "none", "should_render_text": False}


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


def _normalize_should_render_text(candidate: bool, *, fallback: bool, role_default: bool) -> bool:
    """统一布尔策略，避免模型把应无字图位写成重文案。"""

    if isinstance(candidate, bool):
        if role_default is False:
            return False
        return candidate
    if role_default is False:
        return False
    return fallback


def _normalize_subject_ratio(candidate: float | None, fallback: float | None, shot_role: str) -> float | None:
    """统一主体占比，保留 hero 硬规则。"""

    if shot_role == "hero":
        return 0.66
    return candidate if candidate is not None else fallback


def _pick_text(candidate: str, fallback: str) -> str:
    """优先返回非空文本。"""

    return str(candidate or "").strip() or str(fallback or "").strip()
