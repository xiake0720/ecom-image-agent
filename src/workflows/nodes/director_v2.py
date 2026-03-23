"""v2 电商导演节点。

文件位置：
- `src/workflows/nodes/director_v2.py`

核心职责：
- 为 v2 三步链路生成整组 8 图导演规划
- 输出并落盘 `director_output.json`
- 在不依赖视觉模型的前提下，复用已有类目策略、平台策略和参考图选择规则

节点边界：
- 当前不会接入主 graph
- 当前不会改动旧的 `analyze_product / style_director / plan_shots`
- 当前只写入 `director_output`，不替换 v1 的任何 state 字段
"""

from __future__ import annotations

import logging

from src.domain.director_output import DirectorOutput, DirectorShot
from src.domain.product_analysis import ProductAnalysis
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.assets.reference_selector import ReferenceSelection, select_reference_bundle
from src.services.prompting.context_builder import build_plan_shots_context, infer_category_family
from src.services.prompting.policy_loader import describe_policy_source, load_shot_type_policy
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import describe_prompt_source, dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

logger = logging.getLogger(__name__)


DIRECTOR_V2_DEFAULT_PLATFORM = "tmall"
DIRECTOR_V2_DEFAULT_SHOT_COUNT = 8
DIRECTOR_V2_MAX_REFERENCE_IMAGES = 2
DIRECTOR_V2_DEFAULT_ROLES: tuple[str, ...] = (
    "hero",
    "packaging_feature",
    "dry_leaf_detail",
    "tea_soup",
    "brewed_leaf_detail",
    "gift_scene",
    "lifestyle",
    "process_or_quality",
)

# 这里优先复用既有 shot type policy；对于没有完全同名 policy 的角色，映射到最接近的旧 policy。
DIRECTOR_ROLE_POLICY_ALIASES: dict[str, str] = {
    "hero": "hero",
    "packaging_feature": "feature_detail",
    "dry_leaf_detail": "dry_leaf_detail",
    "tea_soup": "tea_soup",
    "brewed_leaf_detail": "brewed_leaf_detail",
    "gift_scene": "lifestyle",
    "lifestyle": "lifestyle",
    "process_or_quality": "feature_detail",
}


def director_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成 v2 整组导演规划并落盘。"""
    task = state["task"]
    platform = _resolve_platform(task)
    shot_count = _resolve_shot_count(task)
    if shot_count != DIRECTOR_V2_DEFAULT_SHOT_COUNT:
        logger.info("director_v2 will use shot_count=%s instead of default=%s", shot_count, DIRECTOR_V2_DEFAULT_SHOT_COUNT)

    product_analysis = _resolve_product_context(state)
    category_family = infer_category_family(product_analysis)
    reference_selection = _select_director_assets(state)
    planning_context = build_plan_shots_context(task=task.model_copy(update={"platform": platform}), product_analysis=product_analysis)
    shot_roles = _resolve_director_roles(shot_count)
    role_template = _build_role_template(
        task=task,
        platform=platform,
        product_analysis=product_analysis,
        shot_roles=shot_roles,
        planning_context=planning_context,
    )
    logs = [
        *state.get("logs", []),
        f"[director_v2] start platform={platform} shot_count={shot_count} mode={deps.text_provider_mode}",
        f"[director_v2] category_family={category_family}",
        f"[director_v2] template_source={describe_prompt_source('director_v2.md')}",
        f"[director_v2] selected_main_asset_id={reference_selection.selected_main_asset_id or '-'} selected_detail_asset_id={reference_selection.selected_detail_asset_id or '-'} selected_reference_asset_ids={reference_selection.selected_asset_ids or []}",
        f"[director_v2] selection_reason={reference_selection.selection_reason}",
        f"[director_v2] shot_roles={list(shot_roles)}",
        f"[director_v2] policy_sources={planning_context.get('policy_sources', {})}",
        *format_connected_contract_logs(state, node_name='director_v2'),
    ]
    if category_family != "tea":
        logs.append("[director_v2] category_family is not tea; continue with tea-oriented director template for v2 compatibility")

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
            "platform": platform,
            "shot_roles": list(shot_roles),
            "reference_asset_ids": reference_selection.selected_asset_ids,
            "product_analysis_hash": hash_state_payload(product_analysis),
            "planning_context_hash": hash_state_payload(planning_context),
        },
    )
    if should_use_cache(state):
        cached_output = deps.storage.load_cached_json_artifact("director_v2", cache_key, DirectorOutput)
        if cached_output is not None:
            normalized_cached_output = _normalize_director_output(
                director_output=cached_output,
                fallback_output=role_template,
                platform=platform,
                product_analysis=product_analysis,
            )
            deps.storage.save_json_artifact(task.task_id, "director_output.json", normalized_cached_output)
            logs.extend(
                [
                    f"[director_v2] cache hit key={cache_key}",
                    f"[cache] node=director_v2 status=hit key={cache_key}",
                    "[director_v2] restored cached director_output.json",
                    *_build_director_output_logs(normalized_cached_output),
                ]
            )
            return {"director_output": normalized_cached_output, "logs": logs}
        logs.extend(
            [
                f"[director_v2] cache miss key={cache_key}",
                f"[cache] node=director_v2 status=miss key={cache_key}",
            ]
        )
    elif is_force_rerun(state):
        logs.extend(
            [
                "[director_v2] ignore cache requested",
                "[cache] node=director_v2 status=ignored key=-",
            ]
        )

    if deps.text_provider_mode == "real":
        prompt = _build_director_prompt(
            task=task,
            platform=platform,
            product_analysis=product_analysis,
            planning_context=planning_context,
            reference_selection=reference_selection,
            role_template=role_template,
        )
        director_output = deps.planning_provider.generate_structured(
            prompt,
            DirectorOutput,
            system_prompt=load_prompt_text("director_v2.md"),
        )
    else:
        director_output = role_template

    director_output = _normalize_director_output(
        director_output=director_output,
        fallback_output=role_template,
        platform=platform,
        product_analysis=product_analysis,
    )
    deps.storage.save_json_artifact(task.task_id, "director_output.json", director_output)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("director_v2", cache_key, director_output, metadata=cache_context)
    logs.extend(_build_director_output_logs(director_output))
    logs.append("[director_v2] saved director_output.json")
    return {"director_output": director_output, "logs": logs}


def _resolve_platform(task) -> str:
    """优先使用任务平台，缺失时回退到 v2 默认平台。"""
    platform = str(getattr(task, "platform", "") or "").strip().lower()
    return platform or DIRECTOR_V2_DEFAULT_PLATFORM


def _resolve_shot_count(task) -> int:
    """解析导演规划目标图数，并约束到当前 v2 默认模板上限。"""
    explicit_count = getattr(task, "shot_count", None)
    if explicit_count is None:
        return DIRECTOR_V2_DEFAULT_SHOT_COUNT
    normalized_count = max(1, int(explicit_count))
    return min(normalized_count, len(DIRECTOR_V2_DEFAULT_ROLES))


def _resolve_director_roles(shot_count: int) -> tuple[str, ...]:
    """返回当前 director_v2 需要输出的固定角色顺序。"""
    return DIRECTOR_V2_DEFAULT_ROLES[:shot_count]


def _resolve_product_context(state: WorkflowState) -> ProductAnalysis:
    """优先复用已有商品分析；没有时退回到基于任务名的轻量 mock 分析。"""
    product_analysis = state.get("product_analysis")
    if product_analysis is not None:
        return product_analysis
    task = state["task"]
    return build_mock_product_analysis(state.get("assets", []), task.product_name)


def _select_director_assets(state: WorkflowState) -> ReferenceSelection:
    """复用统一参考图选择规则，为导演节点提供稳定的输入摘要。"""
    return select_reference_bundle(
        state.get("assets", []),
        max_images=DIRECTOR_V2_MAX_REFERENCE_IMAGES,
    )


def _build_director_prompt(
    *,
    task,
    platform: str,
    product_analysis: ProductAnalysis,
    planning_context: dict[str, object],
    reference_selection: ReferenceSelection,
    role_template: DirectorOutput,
) -> str:
    """构建 director_v2 的结构化提示词输入。"""
    prompt_context = {
        "task": task,
        "platform": platform,
        "product_analysis": product_analysis,
        "planning_context": planning_context,
        "reference_assets": _build_reference_assets_payload(reference_selection),
        "reference_note": "The text model only receives asset metadata, not image pixels. Keep planning conservative and do not hallucinate unseen details.",
        "shot_role_template": role_template,
    }
    return (
        "请为当前茶叶电商商品生成一套 v2 导演规划。\n"
        "这一步不是单张 prompt 编写，而是整组 8 张图的导演级规划。\n"
        "必须严格遵守给定的 shot_id / shot_role 模板，且只输出符合 DirectorOutput schema 的 JSON。\n"
        "每张图都必须明确 objective、audience、selling_points、scene、composition、visual_focus、copy_direction、compliance_notes。\n"
        "如果某些输入只提供了素材元数据而没有实际图像内容，必须保守规划，不要虚构未确认的结构细节。\n\n"
        f"director_v2_context:\n{dump_pretty(prompt_context)}"
    )


def _build_reference_assets_payload(reference_selection: ReferenceSelection) -> list[dict[str, object]]:
    """把参考图选择结果压缩成稳定的 prompt 上下文。"""
    payload: list[dict[str, object]] = []
    for asset in reference_selection.selected_assets:
        payload.append(
            {
                "asset_id": asset.asset_id,
                "filename": asset.filename,
                "asset_type": asset.asset_type.value,
                "width": asset.width,
                "height": asset.height,
                "tags": asset.tags,
            }
        )
    return payload


def _build_role_template(
    *,
    task,
    platform: str,
    product_analysis: ProductAnalysis,
    shot_roles: tuple[str, ...],
    planning_context: dict[str, object],
) -> DirectorOutput:
    """基于业务固定角色和既有 policy 构造稳定的导演模板。"""
    product_name = str(getattr(task, "product_name", "") or "").strip() or "茶叶商品"
    package_type = product_analysis.package_type or product_analysis.packaging_structure.primary_container or "tea package"
    package_template_family = product_analysis.package_template_family or "tea_gift_box"
    style_anchor_summary = str(planning_context.get("group_style_anchor_summary", "") or "").strip()
    platform_direction = str(planning_context.get("platform_policy", {}).get("aesthetic_direction", "") or platform).strip()
    common_compliance_notes = _build_common_compliance_notes(product_analysis)
    shots: list[DirectorShot] = []
    for index, shot_role in enumerate(shot_roles, start=1):
        role_policy = _build_role_policy_summary(shot_role)
        role_defaults = _build_role_defaults(
            shot_role=shot_role,
            product_name=product_name,
            package_type=package_type,
            package_template_family=package_template_family,
            style_anchor_summary=style_anchor_summary,
            platform_direction=platform_direction,
            role_policy=role_policy,
        )
        shots.append(
            DirectorShot(
                shot_id=f"shot_{index:02d}",
                shot_role=shot_role,
                objective=role_defaults["objective"],
                audience=role_defaults["audience"],
                selling_points=role_defaults["selling_points"],
                scene=role_defaults["scene"],
                composition=role_defaults["composition"],
                visual_focus=role_defaults["visual_focus"],
                copy_direction=role_defaults["copy_direction"],
                compliance_notes=[*common_compliance_notes, *role_defaults["compliance_notes"]],
            )
        )
    return DirectorOutput(
        product_summary=(
            f"{product_name}，当前按茶叶电商图组规划处理，包装类型={package_type}，"
            f"平台={platform}，整套导向={platform_direction}。"
        ),
        category=product_analysis.category or "tea",
        platform=platform,
        visual_style=(
            f"整套图保持高级克制、商业感强、利于天猫转化；"
            f"风格锚点={style_anchor_summary or '统一高级茶叶商业静物风格'}。"
        ),
        shots=shots,
    )


def _build_role_policy_summary(shot_role: str) -> dict[str, object]:
    """把既有 shot type policy 映射成 director_v2 可消费的轻量摘要。"""
    policy_name = DIRECTOR_ROLE_POLICY_ALIASES.get(shot_role, "feature_detail")
    policy = load_shot_type_policy(policy_name)
    return {
        "policy_name": policy_name,
        "policy_source": describe_policy_source("shot_types", policy_name),
        "intent": policy.get("intent", ""),
        "composition_defaults": list(policy.get("composition_defaults", [])),
        "prop_guidance": list(policy.get("prop_guidance", [])),
        "text_space_guidance": policy.get("text_space_guidance", ""),
    }


def _build_common_compliance_notes(product_analysis: ProductAnalysis) -> list[str]:
    """构建全局通用合规提示。"""
    notes = [
        "不要虚构功效、医疗暗示或绝对化承诺",
        "不要改动产品包装结构、品牌识别和标签主信息",
        "不要让道具、人物或场景抢过商品主体",
    ]
    if product_analysis.must_preserve_texts:
        notes.append(f"涉及包装文字时优先保留这些识别信息：{', '.join(product_analysis.must_preserve_texts[:3])}")
    if product_analysis.visual_constraints.avoid:
        notes.extend(str(item).strip() for item in product_analysis.visual_constraints.avoid[:2] if str(item).strip())
    return notes


def _build_role_defaults(
    *,
    shot_role: str,
    product_name: str,
    package_type: str,
    package_template_family: str,
    style_anchor_summary: str,
    platform_direction: str,
    role_policy: dict[str, object],
) -> dict[str, object]:
    """根据固定角色生成导演模板默认值。"""
    # 这里先给出稳定的业务兜底，真实模型返回不完整时也能保证 8 张导演规划可用。
    fallback_map: dict[str, dict[str, object]] = {
        "hero": {
            "objective": f"建立 {product_name} 的第一视觉和高端品牌感。",
            "audience": "天猫首屏浏览、先看包装与品牌气质的茶叶购买用户。",
            "selling_points": ["品牌识别", "包装质感", "礼赠或高端自饮定位"],
            "scene": f"高级简洁棚拍主图场景，整体审美={platform_direction}，风格锚点={style_anchor_summary or '高级茶叶商业静物'}。",
            "composition": "主体居中或略偏下，顶部与右侧保留干净留白，避免背景元素过多。",
            "visual_focus": f"{package_type} 正面包装、品牌名称、整体轮廓和主要识别面。",
            "copy_direction": "强调高级感、品牌感、送礼体面或高品质自饮价值。",
            "compliance_notes": ["不要把主图做成低价促销海报感。"],
        },
        "packaging_feature": {
            "objective": f"放大 {package_type} 的结构、标签、材质或工艺卖点。",
            "audience": "已经有兴趣、需要进一步确认包装细节和质感的用户。",
            "selling_points": ["结构细节", "材质工艺", "标签识别"],
            "scene": "近景或局部 3/4 角度商业细节场景，背景干净，道具退后。",
            "composition": "聚焦标签、边缘、开合或材质信息，并集中预留一块可读文案区。",
            "visual_focus": "包装结构、标签局部、材质纹理、印刷与工艺细节。",
            "copy_direction": "偏卖点转化，突出做工、材质、包装可信度。",
            "compliance_notes": ["不要虚构不存在的工艺、认证或材质信息。"],
        },
        "dry_leaf_detail": {
            "objective": "展示干茶形态、条索细节与原料品质感。",
            "audience": "关注茶叶真实形态和品质判断的理性购买用户。",
            "selling_points": ["干茶形态", "条索完整度", "品质感"],
            "scene": "微距或近景细节场景，茶叶与包装线索同框但主次清楚。",
            "composition": "干茶主体清楚，包装线索弱关联，背景尽量简洁避免纹理干扰。",
            "visual_focus": "干茶条索、色泽、完整度，以及包装与茶叶的关联。",
            "copy_direction": "偏品质表达，强调原料、形态、精拣或品类特征。",
            "compliance_notes": ["不要把干茶做成过度舞台化或不真实的概念摆拍。"],
        },
        "tea_soup": {
            "objective": "展示冲泡后茶汤色泽、清透感与饮用氛围。",
            "audience": "关注口感联想和冲泡结果的茶叶用户。",
            "selling_points": ["汤色清透", "饮用氛围", "冲泡表现"],
            "scene": "杯盏克制的冲泡展示场景，器具简洁，背景干净且有留白。",
            "composition": "杯盏稳定、茶汤通透，避免复杂席面，留出上方或侧方文案区。",
            "visual_focus": "茶汤颜色、杯盏轮廓和与产品相关的轻量线索。",
            "copy_direction": "偏体验表达，突出汤色、气韵和饮用感受。",
            "compliance_notes": ["不要暗示医疗功效或夸大功能性结果。"],
        },
        "brewed_leaf_detail": {
            "objective": "展示叶底状态与冲泡后的真实品质细节。",
            "audience": "懂茶或愿意通过叶底判断品质的用户。",
            "selling_points": ["叶底状态", "原料真实感", "品类特征"],
            "scene": "近景真实叶底细节场景，器具克制，避免多余装饰。",
            "composition": "叶底主体清楚且自然展开，背景与器具不压主角。",
            "visual_focus": "叶底纹理、舒展状态、色泽与真实冲泡后的质感。",
            "copy_direction": "偏品质背书，强调真实、细节、可验证感。",
            "compliance_notes": ["不要把叶底修成不真实的统一完美状态。"],
        },
        "gift_scene": {
            "objective": "把商品放进礼赠语境，强化送礼体面感和节庆价值。",
            "audience": "关注送礼场景、体面度与品牌礼品属性的用户。",
            "selling_points": ["礼赠属性", "场景化价值", "高级体面"],
            "scene": (
                "礼赠氛围场景，但保持商业感和克制度。"
                if package_template_family == "tea_gift_box"
                else "适度礼赠场景，强调成组陈列或礼品桌面，而不是强行节庆堆砌。"
            ),
            "composition": "商品主体仍然占主导，礼赠道具只做弱辅助，留白区必须清楚可写文案。",
            "visual_focus": "产品包装与礼赠氛围的关系，不能让人物或礼品道具压过主体。",
            "copy_direction": "更偏品牌感、礼赠感和高级感，弱化直白促销口吻。",
            "compliance_notes": ["不要出现过度节庆堆砌或廉价礼品感。"],
        },
        "lifestyle": {
            "objective": "建立真实可感的日常饮茶或桌面生活方式场景。",
            "audience": "关注日常饮用方式和生活方式质感的用户。",
            "selling_points": ["生活方式", "日常可用性", "品牌气质延展"],
            "scene": "安静克制的桌面或轻生活场景，商品仍然是画面主角。",
            "composition": "场景真实可用，产品与辅助器具关系清楚，复杂纹理区域不要承担文字区。",
            "visual_focus": "产品主体、使用场景气氛和可信的饮茶上下文。",
            "copy_direction": "偏品牌感和生活方式表达，强调自然、高级、克制。",
            "compliance_notes": ["不要让场景变成与商品脱节的氛围摄影。"],
        },
        "process_or_quality": {
            "objective": "为品质、工艺或原料背书建立一张更偏转化说明的图。",
            "audience": "需要额外证据判断品质与可信度的用户。",
            "selling_points": ["品质背书", "工艺说明", "可信度强化"],
            "scene": "洁净、有秩序的品质说明场景，可用少量原料或工艺线索辅助。",
            "composition": "商品主体保留清楚，同时给品质说明型文案预留稳定可读区域。",
            "visual_focus": "产品主体与品质符号、工艺细节或原料线索的组合关系。",
            "copy_direction": "偏卖点转化和品质说明，强调专业、可信、可理解。",
            "compliance_notes": ["不要编造工艺流程、产地认证或虚假等级背书。"],
        },
    }
    role_defaults = fallback_map.get(shot_role, fallback_map["packaging_feature"]).copy()
    composition_defaults = role_policy.get("composition_defaults", [])
    text_space_guidance = role_policy.get("text_space_guidance", "")
    if composition_defaults:
        role_defaults["composition"] = f"{role_defaults['composition']} 参考既有构图规则：{'；'.join(str(item) for item in composition_defaults[:2])}。"
    if text_space_guidance:
        role_defaults["composition"] = f"{role_defaults['composition']} 文案留白建议：{text_space_guidance}。"
    return role_defaults


def _normalize_director_output(
    *,
    director_output: DirectorOutput,
    fallback_output: DirectorOutput,
    platform: str,
    product_analysis: ProductAnalysis,
) -> DirectorOutput:
    """把模型输出补齐成稳定可落盘的 v2 导演 contract。"""
    shot_by_id = {shot.shot_id: shot for shot in director_output.shots}
    shot_by_role = {shot.shot_role: shot for shot in director_output.shots}
    normalized_shots: list[DirectorShot] = []
    for fallback_shot in fallback_output.shots:
        candidate = shot_by_id.get(fallback_shot.shot_id) or shot_by_role.get(fallback_shot.shot_role)
        if candidate is None:
            normalized_shots.append(fallback_shot)
            continue
        normalized_shots.append(
            DirectorShot(
                shot_id=fallback_shot.shot_id,
                shot_role=fallback_shot.shot_role,
                objective=_pick_text(candidate.objective, fallback_shot.objective),
                audience=_pick_text(candidate.audience, fallback_shot.audience),
                selling_points=_pick_list(candidate.selling_points, fallback_shot.selling_points),
                scene=_pick_text(candidate.scene, fallback_shot.scene),
                composition=_pick_text(candidate.composition, fallback_shot.composition),
                visual_focus=_pick_text(candidate.visual_focus, fallback_shot.visual_focus),
                copy_direction=_pick_text(candidate.copy_direction, fallback_shot.copy_direction),
                compliance_notes=_merge_list_values(candidate.compliance_notes, fallback_shot.compliance_notes),
            )
        )
    return DirectorOutput(
        product_summary=_pick_text(director_output.product_summary, fallback_output.product_summary),
        category=_pick_text(director_output.category, product_analysis.category or fallback_output.category),
        platform=platform,
        visual_style=_pick_text(director_output.visual_style, fallback_output.visual_style),
        shots=normalized_shots,
    )


def _build_director_output_logs(director_output: DirectorOutput) -> list[str]:
    """把导演结果压缩成便于排查的日志摘要。"""
    logs = [
        f"[director_v2] product_summary={_truncate_text(director_output.product_summary)}",
        f"[director_v2] visual_style={_truncate_text(director_output.visual_style)}",
        f"[director_v2] shot_count={len(director_output.shots)}",
    ]
    for shot in director_output.shots:
        logs.append(
            (
                f"[director_v2] shot={shot.shot_id} role={shot.shot_role} "
                f"objective={_truncate_text(shot.objective, limit=80)} "
                f"copy_direction={_truncate_text(shot.copy_direction, limit=60)} "
                f"selling_points={shot.selling_points[:3]}"
            )
        )
    return logs


def _pick_text(candidate: str, fallback: str) -> str:
    """优先取模型返回值，缺失时回退到模板值。"""
    normalized = str(candidate or "").strip()
    return normalized or str(fallback or "").strip()


def _pick_list(candidate: list[str], fallback: list[str]) -> list[str]:
    """优先取非空列表，否则回退到模板值。"""
    normalized = [str(item).strip() for item in (candidate or []) if str(item).strip()]
    if normalized:
        return normalized
    return [str(item).strip() for item in (fallback or []) if str(item).strip()]


def _merge_list_values(candidate: list[str], fallback: list[str]) -> list[str]:
    """合并模型输出和模板默认值，避免丢掉基础合规提醒。"""
    merged: list[str] = []
    for item in [*(fallback or []), *(candidate or [])]:
        normalized = str(item).strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def _truncate_text(text: str, limit: int = 140) -> str:
    """截断日志中的长文本，避免单行过长。"""
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."
