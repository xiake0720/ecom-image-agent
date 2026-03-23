"""v2 生图 prompt 精修节点。

文件位置：
- `src/workflows/nodes/prompt_refine_v2.py`

核心职责：
- 读取 `director_output`，为每张图生成最终可执行的生图 prompt
- 同时生成图内主标题、副标题和版式提示，落盘为 `prompt_plan_v2.json`
- 在不依赖旧 `copy_plan / layout_plan / image_prompt_plan` 的前提下，给 v2 三步链路提供稳定输入

节点边界：
- 当前不改旧的 `generate_copy / generate_layout / shot_prompt_refiner / build_prompts`
- 当前不接入主 graph，由后续 PR 统一接线
"""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.director_output import DirectorOutput, DirectorShot
from src.domain.product_analysis import ProductAnalysis
from src.domain.prompt_plan_v2 import PromptPlanV2, PromptShot
from src.services.analysis.product_analyzer import build_mock_product_analysis
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


PROMPT_REFINE_V2_TITLE_MIN = 4
PROMPT_REFINE_V2_TITLE_MAX = 8
PROMPT_REFINE_V2_SUBTITLE_MIN = 8
PROMPT_REFINE_V2_SUBTITLE_MAX = 15

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

ROLE_COPY_GUIDANCE: dict[str, str] = {
    "hero": "文案更偏品牌感、高级感和第一视觉转化。",
    "gift_scene": "文案更偏礼赠场景、高级感和品牌气质。",
    "lifestyle": "文案更偏生活方式、品牌感和长期陪伴感。",
    "packaging_feature": "文案更偏卖点转化，突出包装细节和结构价值。",
    "process_or_quality": "文案更偏卖点转化，强调工艺、品质和可信度。",
}


def prompt_refine_v2(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """基于导演规划生成 v2 最终生图计划。

    上游：
    - `director_v2`
    - 可选 `product_analysis`

    下游：
    - `render_images` 的 v2 分支
    - `overlay_text` 的 fallback 分支

    为什么这个节点要合并旧链路职责：
    - v2 不再拆成 copy/layout/prompt 多个节点
    - 图片模型需要一次看到“最终 prompt + 标题 + 副标题 + 版式提示”
    - 但仍要保留结构化输出，方便 QC 和调试
    """
    task = state["task"]
    director_output = state.get("director_output")
    if director_output is None:
        raise RuntimeError("prompt_refine_v2 requires `director_output` in workflow state.")

    settings = get_settings()
    product_analysis = _resolve_product_context(state)
    planning_context = build_plan_shots_context(task=task, product_analysis=product_analysis)
    category_family = infer_category_family(product_analysis)
    fallback_plan = _build_fallback_prompt_plan(
        director_output=director_output,
        product_analysis=product_analysis,
        planning_context=planning_context,
    )
    logs = [
        *state.get("logs", []),
        (
            "[prompt_refine_v2] start "
            f"platform={director_output.platform or settings.default_platform} "
            f"shot_count={len(director_output.shots)} "
            f"mode={deps.text_provider_mode}"
        ),
        f"[prompt_refine_v2] category_family={category_family}",
        f"[prompt_refine_v2] template_source={describe_prompt_source('prompt_refine_v2.md')}",
        f"[prompt_refine_v2] default_aspect_ratio={settings.default_image_aspect_ratio}",
        f"[prompt_refine_v2] default_image_size={settings.default_image_size}",
        *format_connected_contract_logs(state, node_name="prompt_refine_v2"),
    ]

    provider_name, provider_model_id = planning_provider_identity(deps)
    cache_key, cache_context = build_node_cache_key(
        node_name="prompt_refine_v2",
        state=state,
        deps=deps,
        prompt_filename="prompt_refine_v2.md" if deps.text_provider_mode == "real" else None,
        prompt_version="mock-prompt-plan-v2" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "director_output_hash": hash_state_payload(director_output),
            "product_analysis_hash": hash_state_payload(product_analysis),
            "planning_context_hash": hash_state_payload(planning_context),
        },
    )
    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("prompt_refine_v2", cache_key, PromptPlanV2)
        if cached_plan is not None:
            # 缓存命中后仍然做一次 normalize，避免旧缓存缺字段或字段越界，
            # 影响后续 render/QC。
            normalized_cached_plan = _normalize_prompt_plan(
                prompt_plan=cached_plan,
                fallback_plan=fallback_plan,
            )
            deps.storage.save_json_artifact(task.task_id, "prompt_plan_v2.json", normalized_cached_plan)
            logs.extend(
                [
                    f"[prompt_refine_v2] cache hit key={cache_key}",
                    f"[cache] node=prompt_refine_v2 status=hit key={cache_key}",
                    "[prompt_refine_v2] restored cached prompt_plan_v2.json",
                    *_build_prompt_plan_logs(normalized_cached_plan),
                ]
            )
            return {"prompt_plan_v2": normalized_cached_plan, "logs": logs}
        logs.extend(
            [
                f"[prompt_refine_v2] cache miss key={cache_key}",
                f"[cache] node=prompt_refine_v2 status=miss key={cache_key}",
            ]
        )
    elif is_force_rerun(state):
        logs.extend(
            [
                "[prompt_refine_v2] ignore cache requested",
                "[cache] node=prompt_refine_v2 status=ignored key=-",
            ]
        )

    if deps.text_provider_mode == "real":
        if not hasattr(deps.planning_provider, "generate_structured"):
            raise RuntimeError("prompt_refine_v2 requires a planning provider with `generate_structured()`.")
        # real 模式下仍然把 fallback plan 一并传给模型，目的是给模型一个
        # 稳定的参考下限，降低完全跑偏的概率。
        prompt = _build_prompt_refine_prompt(
            director_output=director_output,
            product_analysis=product_analysis,
            planning_context=planning_context,
            fallback_plan=fallback_plan,
        )
        prompt_plan = deps.planning_provider.generate_structured(
            prompt,
            PromptPlanV2,
            system_prompt=load_prompt_text("prompt_refine_v2.md"),
        )
    else:
        prompt_plan = fallback_plan

    normalized_plan = _normalize_prompt_plan(
        prompt_plan=prompt_plan,
        fallback_plan=fallback_plan,
    )
    deps.storage.save_json_artifact(task.task_id, "prompt_plan_v2.json", normalized_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("prompt_refine_v2", cache_key, normalized_plan, metadata=cache_context)
    logs.extend(_build_prompt_plan_logs(normalized_plan))
    logs.append("[prompt_refine_v2] saved prompt_plan_v2.json")
    return {"prompt_plan_v2": normalized_plan, "logs": logs}


def _resolve_product_context(state: WorkflowState) -> ProductAnalysis:
    """优先复用已有商品分析；没有时退回到轻量 mock 上下文。"""
    product_analysis = state.get("product_analysis")
    if product_analysis is not None:
        return product_analysis
    task = state["task"]
    return build_mock_product_analysis(state.get("assets", []), task.product_name)


def _build_prompt_refine_prompt(
    *,
    director_output: DirectorOutput,
    product_analysis: ProductAnalysis,
    planning_context: dict[str, object],
    fallback_plan: PromptPlanV2,
) -> str:
    """构建 prompt_refine_v2 的结构化提示词输入。"""
    prompt_context = {
        "director_output": director_output,
        "product_analysis": product_analysis,
        "planning_context": planning_context,
        "copy_constraints": {
            "title_length_recommendation": f"{PROMPT_REFINE_V2_TITLE_MIN}-{PROMPT_REFINE_V2_TITLE_MAX} chars",
            "subtitle_length_recommendation": f"{PROMPT_REFINE_V2_SUBTITLE_MIN}-{PROMPT_REFINE_V2_SUBTITLE_MAX} chars",
            "direct_text_on_image": True,
            "overlay_fallback_enabled": True,
        },
        "fallback_reference_plan": fallback_plan,
        "required_render_prompt_constraints": [
            "产品包装结构不要变",
            "标签和品牌识别不要乱改",
            "画面风格与整套图统一",
            "符合天猫茶叶电商审美",
            "文案融入画面，不要做简陋文本框",
            "优先保留产品主体，不允许文案压住关键产品区",
        ],
    }
    return (
        "请基于导演规划输出最终可执行的 v2 生图计划。\n"
        "你必须只输出一个符合 PromptPlanV2 schema 的 JSON，不要输出解释文字。\n"
        "每张图都必须保留原有 shot_id 和 shot_role，并输出 render_prompt、title_copy、subtitle_copy、layout_hint、aspect_ratio、image_size。\n"
        "render_prompt 必须是直接给图片模型执行的描述，且必须包含产品锁定、品牌识别、整套风格统一、天猫茶叶电商审美、图内融字和主产品不被文案遮挡这些约束。\n"
        "title_copy 建议控制在 4-8 字，subtitle_copy 建议控制在 8-15 字，但如果为了语义完整略有浮动也要优先保证可读和转化。\n"
        "layout_hint 必须说清楚文案的大致区域，例如左上留白、顶部留白、右下弱化横条、不要遮挡主包装等。\n"
        "hero / gift_scene / lifestyle 更偏品牌感、高级感；packaging_feature / process_or_quality 更偏卖点转化。\n\n"
        f"prompt_refine_v2_context:\n{dump_pretty(prompt_context)}"
    )


def _build_fallback_prompt_plan(
    *,
    director_output: DirectorOutput,
    product_analysis: ProductAnalysis,
    planning_context: dict[str, object],
) -> PromptPlanV2:
    """基于导演规划和轻量规则构造稳定的 v2 兜底 prompt 计划。

    这个兜底计划既服务于：
    - mock 模式下的直接输出
    - real 模式下的 normalize/fallback 参考

    这样即使模型没有完全遵守 schema 或文案长度建议，链路仍然可跑通。
    """
    settings = get_settings()
    platform_policy = planning_context.get("platform_policy", {}) if isinstance(planning_context, dict) else {}
    style_anchor_summary = str(planning_context.get("group_style_anchor_summary", "") or "").strip()
    platform_direction = str(platform_policy.get("aesthetic_direction", "") or director_output.platform).strip()
    shots = [
        _build_fallback_prompt_shot(
            director_shot=director_shot,
            director_output=director_output,
            product_analysis=product_analysis,
            style_anchor_summary=style_anchor_summary,
            platform_direction=platform_direction,
            default_aspect_ratio=settings.default_image_aspect_ratio,
            default_image_size=settings.default_image_size,
        )
        for director_shot in director_output.shots
    ]
    return PromptPlanV2(shots=shots)


def _build_fallback_prompt_shot(
    *,
    director_shot: DirectorShot,
    director_output: DirectorOutput,
    product_analysis: ProductAnalysis,
    style_anchor_summary: str,
    platform_direction: str,
    default_aspect_ratio: str,
    default_image_size: str,
) -> PromptShot:
    """按固定角色模板为单张图构造最终生图提示。"""
    role_defaults = _build_role_defaults(director_shot.shot_role)
    package_type = product_analysis.package_type or "茶叶包装"
    package_color = product_analysis.primary_color or "原始主色"
    brand_texts = "、".join(product_analysis.must_preserve_texts[:3]) if product_analysis.must_preserve_texts else "现有品牌识别"
    locked_elements = "、".join(product_analysis.locked_elements[:4]) if product_analysis.locked_elements else "包装结构与主标签"
    must_preserve = "、".join(product_analysis.visual_identity.must_preserve[:4]) if product_analysis.visual_identity.must_preserve else "主包装轮廓"
    compliance_summary = "；".join(director_shot.compliance_notes[:3]) if director_shot.compliance_notes else "不要夸大功能，不要改变包装识别。"
    copy_strategy = ROLE_COPY_GUIDANCE.get(
        director_shot.shot_role,
        "文案需要在转化表达和高级感之间保持平衡。",
    )
    policy_summary = _build_role_policy_summary(director_shot.shot_role)
    render_prompt = "\n".join(
        [
            f"为天猫茶叶电商生成一张 {director_shot.shot_role} 图位图片。",
            f"画面目标：{director_shot.objective}",
            f"目标人群：{director_shot.audience}",
            f"关键卖点：{'、'.join(director_shot.selling_points)}",
            f"场景方向：{director_shot.scene}",
            f"构图方向：{director_shot.composition}",
            f"视觉焦点：{director_shot.visual_focus}",
            f"整体风格：{director_output.visual_style}",
            f"平台审美：{platform_direction or director_output.platform}",
            f"风格锚点：{style_anchor_summary or '整套图统一的高级茶叶商业视觉'}",
            f"角色策略：{copy_strategy}",
            f"参考 policy：{policy_summary['intent'] or '突出商业转化和结构清晰度'}",
            f"文本留白建议：{role_defaults['layout_hint']}",
            (
                "产品锁定：保持产品包装结构不要变，保持标签和品牌识别不要乱改，"
                f"保留包装类型={package_type}、主色={package_color}、必须保留文本={brand_texts}、"
                f"锁定元素={locked_elements}、视觉识别={must_preserve}。"
            ),
            "整套图风格必须统一，画面符合天猫茶叶电商审美，质感高级、克制、转化导向明确。",
            "文案直接融入画面，不要做简陋文本框，不要贴廉价海报块，不要让文案压住关键产品区。",
            f"合规提醒：{compliance_summary}",
        ]
    )
    return PromptShot(
        shot_id=director_shot.shot_id,
        shot_role=director_shot.shot_role,
        render_prompt=_ensure_required_render_constraints(render_prompt),
        title_copy=role_defaults["title_copy"],
        subtitle_copy=role_defaults["subtitle_copy"],
        layout_hint=role_defaults["layout_hint"],
        aspect_ratio=default_aspect_ratio,
        image_size=default_image_size,
    )


def _build_role_defaults(shot_role: str) -> dict[str, str]:
    """为不同图位角色提供标题、副标题和版式兜底模板。"""
    defaults: dict[str, dict[str, str]] = {
        "hero": {
            "title_copy": "东方茶礼",
            "subtitle_copy": "礼盒质感一眼高级",
            "layout_hint": "顶部或右上留白融字，文案贴合背景，不遮挡主包装正面和品牌名。",
        },
        "packaging_feature": {
            "title_copy": "细节见真",
            "subtitle_copy": "包装结构细节清晰可见",
            "layout_hint": "右上或左上小面积留白融字，靠近细节区但不要压住标签关键识别。",
        },
        "dry_leaf_detail": {
            "title_copy": "条索清晰",
            "subtitle_copy": "干茶形态细节更直观",
            "layout_hint": "在纯净背景区轻融文字，不要压在茶叶纹理最密集区域。",
        },
        "tea_soup": {
            "title_copy": "汤色透亮",
            "subtitle_copy": "冲泡观感清透有质感",
            "layout_hint": "上方留白或侧边轻量融字，避开杯盏主体和汤色高光区。",
        },
        "brewed_leaf_detail": {
            "title_copy": "叶底鲜活",
            "subtitle_copy": "叶底细节真实可辨识",
            "layout_hint": "顶部留白或角落融字，避免遮挡叶底展开层次。",
        },
        "gift_scene": {
            "title_copy": "礼赠有面",
            "subtitle_copy": "送礼场景更显高级体面",
            "layout_hint": "左上或顶部留白融字，礼赠氛围弱辅助，商品主包装仍是中心。",
        },
        "lifestyle": {
            "title_copy": "日常雅饮",
            "subtitle_copy": "轻松融入日常饮茶时刻",
            "layout_hint": "在桌面留白区融字，文字跟随场景节奏，不遮挡商品主体和器具焦点。",
        },
        "process_or_quality": {
            "title_copy": "工艺把关",
            "subtitle_copy": "品质卖点表达更可信",
            "layout_hint": "顶部或侧边稳定留白融字，可轻弱化底部横条，但不要盖住主包装。",
        },
    }
    return defaults.get(shot_role, defaults["packaging_feature"]).copy()


def _build_role_policy_summary(shot_role: str) -> dict[str, object]:
    """把既有 shot type policy 压缩为 prompt_refine_v2 可消费的摘要。"""
    policy_name = DIRECTOR_ROLE_POLICY_ALIASES.get(shot_role, "feature_detail")
    policy = load_shot_type_policy(policy_name)
    return {
        "policy_name": policy_name,
        "policy_source": describe_policy_source("shot_types", policy_name),
        "intent": policy.get("intent", ""),
        "text_space_guidance": policy.get("text_space_guidance", ""),
    }


def _normalize_prompt_plan(*, prompt_plan: PromptPlanV2, fallback_plan: PromptPlanV2) -> PromptPlanV2:
    """把模型输出补齐成稳定可执行的 v2 prompt 计划。

    归一化策略：
    - 优先按 `shot_id` 对齐，避免图位顺序漂移
    - 若 `shot_id` 缺失，再按 `shot_role` 兜底
    - 文案长度超出建议范围时，回退到规则兜底文案
    - `render_prompt` 永远强制补齐 v2 必需的产品锁定约束
    """
    shot_by_id = {shot.shot_id: shot for shot in prompt_plan.shots}
    shot_by_role = {shot.shot_role: shot for shot in prompt_plan.shots}
    normalized_shots: list[PromptShot] = []
    for fallback_shot in fallback_plan.shots:
        candidate = shot_by_id.get(fallback_shot.shot_id) or shot_by_role.get(fallback_shot.shot_role)
        if candidate is None:
            normalized_shots.append(fallback_shot)
            continue
        normalized_shots.append(
            PromptShot(
                shot_id=fallback_shot.shot_id,
                shot_role=fallback_shot.shot_role,
                render_prompt=_ensure_required_render_constraints(
                    _pick_text(candidate.render_prompt, fallback_shot.render_prompt)
                ),
                title_copy=_normalize_copy_text(
                    candidate.title_copy,
                    fallback_shot.title_copy,
                    min_length=PROMPT_REFINE_V2_TITLE_MIN,
                    max_length=PROMPT_REFINE_V2_TITLE_MAX,
                ),
                subtitle_copy=_normalize_copy_text(
                    candidate.subtitle_copy,
                    fallback_shot.subtitle_copy,
                    min_length=PROMPT_REFINE_V2_SUBTITLE_MIN,
                    max_length=PROMPT_REFINE_V2_SUBTITLE_MAX,
                ),
                layout_hint=_pick_text(candidate.layout_hint, fallback_shot.layout_hint),
                aspect_ratio=_pick_text(candidate.aspect_ratio, fallback_shot.aspect_ratio),
                image_size=_pick_text(candidate.image_size, fallback_shot.image_size),
            )
        )
    return PromptPlanV2(shots=normalized_shots)


def _build_prompt_plan_logs(prompt_plan: PromptPlanV2) -> list[str]:
    """输出每张图的关键生图计划摘要，便于后续排查 render/QC 问题。"""
    logs = [f"[prompt_refine_v2] shot_count={len(prompt_plan.shots)}"]
    for shot in prompt_plan.shots:
        logs.append(
            (
                f"[prompt_refine_v2] shot={shot.shot_id} role={shot.shot_role} "
                f"title={shot.title_copy!r} subtitle={shot.subtitle_copy!r} "
                f"title_len={_visible_length(shot.title_copy)} subtitle_len={_visible_length(shot.subtitle_copy)} "
                f"aspect_ratio={shot.aspect_ratio} image_size={shot.image_size}"
            )
        )
    return logs


def _normalize_copy_text(candidate: str, fallback: str, *, min_length: int, max_length: int) -> str:
    """对标题和副标题做软约束归一化，超出推荐范围时优先回退到兜底文案。"""
    normalized = _pick_text(candidate, fallback)
    length = _visible_length(normalized)
    if min_length <= length <= max_length:
        return normalized
    return fallback


def _pick_text(candidate: str, fallback: str) -> str:
    """优先使用模型输出，缺失时回退到兜底值。"""
    normalized = " ".join(str(candidate or "").split())
    if normalized:
        return normalized
    return " ".join(str(fallback or "").split())


def _visible_length(text: str) -> int:
    """估算文案有效长度，忽略空白字符。"""
    return len("".join(str(text or "").split()))


def _ensure_required_render_constraints(render_prompt: str) -> str:
    """确保最终 render prompt 一定带上 v2 必需的产品锁定和图内文字约束。

    这里不依赖模型“自觉遵守”，而是在程序层做最后一道补丁。
    目的不是追求 prompt 优雅，而是优先保证执行稳定性。
    """
    required_lines = [
        "产品包装结构不要变。",
        "标签和品牌识别不要乱改。",
        "整套图风格必须统一。",
        "画面要符合天猫茶叶电商审美。",
        "文案融入画面，不要做简陋文本框。",
        "优先保留产品主体，不允许文案压住关键产品区。",
    ]
    normalized = str(render_prompt or "").strip()
    for line in required_lines:
        if line.rstrip("。") not in normalized:
            normalized = f"{normalized}\n{line}".strip()
    return normalized
