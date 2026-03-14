"""整组视觉总导演节点。

文件位置：
- `src/workflows/nodes/style_director.py`

核心职责：
- 在单张图 prompt 生成之前，先定义整组图统一的视觉世界观。
- 输出并落盘 `style_architecture.json`。
- 把 `style_architecture` 写入 workflow state，供 `plan_shots / shot_prompt_refiner / render_images` 读取。

节点前后关系：
- 上游：`analyze_product`
- 下游：`plan_shots`

这次特别处理的问题：
- LLM 即使返回成功，也可能漏掉关键字段，导致日志里出现 `unspecified` 或 `-`
- 因此这里必须在程序层补齐 `main_light_direction / color_strategy / background_strategy / lens_strategy`
"""

from __future__ import annotations

import logging

from src.domain.style_architecture import StyleArchitecture
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

logger = logging.getLogger(__name__)


def style_director(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成整组图片统一的风格架构并落盘。"""
    task = state["task"]
    user_preferences = _resolve_user_preferences(state)
    logs = [
        *state.get("logs", []),
        f"[style_director] start platform={task.platform} user_preferences={user_preferences}",
        *format_connected_contract_logs(state, node_name="style_director"),
    ]
    provider_name, provider_model_id = planning_provider_identity(deps)
    cache_key, cache_context = build_node_cache_key(
        node_name="style_director",
        state=state,
        deps=deps,
        prompt_filename="style_director.md" if deps.text_provider_mode == "real" else None,
        prompt_version="mock-style-architecture-v1" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "platform": task.platform,
            "user_preferences": user_preferences,
        },
    )
    if should_use_cache(state):
        cached = deps.storage.load_cached_json_artifact("style_director", cache_key, StyleArchitecture)
        if cached is not None:
            cached = _normalize_style_architecture(
                architecture=cached,
                state=state,
                user_preferences=user_preferences,
            )
            deps.storage.save_json_artifact(task.task_id, "style_architecture.json", cached)
            logs.extend(
                [
                    f"[style_director] cache hit key={cache_key}",
                    f"[cache] node=style_director status=hit key={cache_key}",
                    "[style_director] saved style_architecture.json from cache",
                ]
            )
            logs.extend(_build_style_architecture_logs(task.platform, user_preferences, cached))
            logs.extend(format_connected_contract_logs({**state, "style_architecture": cached}, node_name="style_director"))
            return {"style_architecture": cached, "logs": logs}
        logs.extend(
            [
                f"[style_director] cache miss key={cache_key}",
                f"[cache] node=style_director status=miss key={cache_key}",
            ]
        )
    elif is_force_rerun(state):
        logs.extend(
            [
                "[style_director] ignore cache requested",
                "[cache] node=style_director status=ignored key=-",
            ]
        )

    if deps.text_provider_mode == "real":
        prompt = (
            "You are the group-level visual director for a fixed five-shot e-commerce product set.\n"
            "Produce one StyleArchitecture JSON object only.\n"
            "Do not write any single-shot prompt.\n"
            "The output must define the unified brand tone, space style, photography direction, emotion keywords, "
            "color strategy, explicit main light direction, lens language, prop system, background strategy, "
            "text-safe-zone strategy, and global negative rules.\n"
            f"task:\n{dump_pretty(task)}\n\n"
            f"product_analysis:\n{dump_pretty(state['product_analysis'])}\n\n"
            f"user_preferences:\n{dump_pretty(user_preferences)}"
        )
        architecture = deps.planning_provider.generate_structured(
            prompt,
            StyleArchitecture,
            system_prompt=load_prompt_text("style_director.md"),
        )
    else:
        architecture = _build_mock_style_architecture(state, user_preferences)

    architecture = _normalize_style_architecture(
        architecture=architecture,
        state=state,
        user_preferences=user_preferences,
    )
    deps.storage.save_json_artifact(task.task_id, "style_architecture.json", architecture)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("style_director", cache_key, architecture, metadata=cache_context)
    logs.extend(_build_style_architecture_logs(task.platform, user_preferences, architecture))
    logs.extend(format_connected_contract_logs({**state, "style_architecture": architecture}, node_name="style_director"))
    logs.append("[style_director] saved style_architecture.json")
    return {"style_architecture": architecture, "logs": logs}


def _resolve_user_preferences(state: WorkflowState) -> list[str]:
    """把 state 中可能出现的用户偏好归一化成字符串列表。"""
    explicit = state.get("user_preferences")
    if isinstance(explicit, list) and explicit:
        return [str(item).strip() for item in explicit if str(item).strip()]
    if isinstance(explicit, str) and explicit.strip():
        return [explicit.strip()]
    if isinstance(explicit, dict) and explicit:
        flattened = []
        for key, value in explicit.items():
            normalized = str(value).strip()
            if normalized:
                flattened.append(f"{key}:{normalized}")
        if flattened:
            return flattened

    task = state["task"]
    product_analysis = state["product_analysis"]
    preferences = ["premium", "gifting", "light"]
    if "young" in str(task.copy_tone).lower():
        preferences.append("young")
    primary_color = (product_analysis.primary_color or "").lower()
    if primary_color:
        preferences.append(primary_color)
    return preferences


def _build_mock_style_architecture(state: WorkflowState, user_preferences: list[str]) -> StyleArchitecture:
    """本地 mock 风格架构。"""
    product_analysis = state["product_analysis"]
    primary_color = product_analysis.primary_color or "red"
    return StyleArchitecture(
        platform=state["task"].platform,
        user_preferences=user_preferences,
        style_theme="premium tea gift box visual world with restrained commercial still life and gifting mood",
        main_light_direction="upper-left",
        color_strategy=[
            f"treat {primary_color} package as the only high-saturation focal point",
            "if the package is highly saturated, backgrounds must be desaturated",
            "background palette stays in ivory, linen, warm gray, pale wood, and stone",
            "props must stay low-saturation and subordinate to the package",
        ],
        lighting_strategy=[
            "main light direction fixed at upper-left across the full set",
            "soft directional commercial light with clean edge definition",
            "consistent soft shadow density across all shots",
        ],
        lens_strategy=[
            "50mm full-frame commercial lens feel across the full set",
            "consistent moderate depth of field",
            "avoid wide-angle distortion on the package",
        ],
        prop_system=[
            "tea tray, linen, neutral ceramic ware, muted wood accents",
            "same restrained prop family across the full set",
            "no cluttered or festive props that compete with the package",
        ],
        background_strategy=[
            "use desaturated premium backgrounds only",
            "prefer ivory, linen, warm gray, pale wood, and stone",
            "keep texture subtle so the package stays the visual center",
        ],
        text_strategy=[
            "text safe zones should prioritize upper-left, upper-right, and upper area",
            "text safe zones must stay away from the package label and center mass",
            "reserve clean negative space rather than busy textured areas",
        ],
        global_negative_rules=[
            "do not redesign the package structure",
            "do not redesign the label",
            "do not add competing saturated props",
            "do not break the fixed main light direction",
            "do not change the unified lens language",
        ],
    )


def _normalize_style_architecture(
    *,
    architecture: StyleArchitecture,
    state: WorkflowState,
    user_preferences: list[str],
) -> StyleArchitecture:
    """把 style_director 结果补齐成稳定 contract。

    这里的目标不是重写模型输出，而是保证核心字段永远可用：
    - `main_light_direction`
    - `background_strategy`
    - `color_strategy`
    - `lens_strategy`
    """
    product_analysis = state["product_analysis"]
    primary_color = getattr(product_analysis, "primary_color", "") or "red"
    main_light_direction = _extract_main_light_direction(architecture) or "upper-left"

    color_strategy = list(architecture.color_strategy or [])
    if not color_strategy:
        color_strategy = [
            f"treat the {primary_color} product package as the only high-saturation focal point",
            "if the package is highly saturated, backgrounds must stay desaturated",
            "background palette stays in ivory, linen, warm gray, pale wood, and stone",
        ]

    background_strategy = list(architecture.background_strategy or [])
    if not background_strategy:
        background_strategy = [
            "use desaturated premium backgrounds only",
            "prefer ivory, linen, warm gray, pale wood, and stone",
            "keep texture subtle so the package stays the visual center",
        ]

    lens_strategy = list(architecture.lens_strategy or [])
    if not lens_strategy:
        lens_strategy = [
            "keep a 50mm commercial lens feel across the full set",
            "use moderate depth of field and avoid package distortion",
        ]

    lighting_strategy = list(architecture.lighting_strategy or [])
    if not lighting_strategy:
        lighting_strategy = [
            f"main light direction fixed at {main_light_direction} across the full set",
            "use soft directional commercial light with clean edge definition",
        ]
    elif not any(main_light_direction in rule.lower() for rule in lighting_strategy):
        lighting_strategy = [
            f"main light direction fixed at {main_light_direction} across the full set",
            *lighting_strategy,
        ]

    prop_system = list(architecture.prop_system or [])
    if not prop_system:
        prop_system = [
            "tea tray, linen, neutral ceramic ware, muted wood accents",
            "same restrained prop family across the full set",
        ]

    text_strategy = list(architecture.text_strategy or [])
    if not text_strategy:
        text_strategy = [
            "text safe zones should prioritize upper-left, upper-right, and upper area",
            "reserve clean negative space rather than busy textured areas",
        ]

    global_negative_rules = list(architecture.global_negative_rules or [])
    if not global_negative_rules:
        global_negative_rules = [
            "do not redesign the package structure",
            "do not redesign the label",
            "do not add competing saturated props",
            "do not break the fixed main light direction",
            "do not change the unified lens language",
        ]

    style_theme = str(architecture.style_theme or "").strip()
    if not style_theme:
        style_theme = (
            "premium commercial still life with restrained atmosphere, "
            f"stable {main_light_direction} lighting, and unified low-saturation supporting scene"
        )

    return architecture.model_copy(
        update={
            "platform": architecture.platform or state["task"].platform,
            "user_preferences": list(architecture.user_preferences or user_preferences or ["premium", "light"]),
            "style_theme": style_theme,
            "main_light_direction": main_light_direction,
            "color_strategy": color_strategy,
            "lighting_strategy": lighting_strategy,
            "lens_strategy": lens_strategy,
            "prop_system": prop_system,
            "background_strategy": background_strategy,
            "text_strategy": text_strategy,
            "global_negative_rules": global_negative_rules,
        }
    )


def _build_style_architecture_logs(
    platform: str,
    user_preferences: list[str],
    architecture: StyleArchitecture,
) -> list[str]:
    """把 `style_architecture` 摘要化成便于排查的日志。"""
    return [
        "[style_director] style_architecture_generated=true",
        f"[style_director] platform_and_preferences=platform={platform} user_preferences={user_preferences}",
        f"[style_director] style_theme_summary={_truncate_text(architecture.style_theme)}",
        f"[style_director] main_light_direction={architecture.main_light_direction}",
        f"[style_director] color_strategy_summary={_summarize_rules(architecture.color_strategy)}",
        f"[style_director] background_strategy_summary={_summarize_rules(architecture.background_strategy)}",
        f"[style_director] lens_strategy_summary={_summarize_rules(architecture.lens_strategy)}",
    ]


def _extract_main_light_direction(architecture: StyleArchitecture) -> str:
    """从光线策略中提取主光方向；如果 contract 已显式带字段则优先使用。"""
    explicit = str(getattr(architecture, "main_light_direction", "") or "").strip().lower()
    if explicit and explicit not in {"-", "unspecified"}:
        return explicit
    for rule in architecture.lighting_strategy:
        lowered = rule.lower()
        if "upper-left" in lowered:
            return "upper-left"
        if "upper-right" in lowered:
            return "upper-right"
        if "top_left" in lowered:
            return "top_left"
        if "top_right" in lowered:
            return "top_right"
        if "left" in lowered:
            return "left"
        if "right" in lowered:
            return "right"
    return ""


def _summarize_rules(rules: list[str], limit: int = 2) -> str:
    """把策略列表压缩成短摘要，避免日志过长。"""
    if not rules:
        return "none"
    summary = " | ".join(rules[:limit])
    if len(rules) > limit:
        summary = f"{summary} | ..."
    return summary


def _truncate_text(text: str, limit: int = 140) -> str:
    """截断日志中的长文本摘要。"""
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."
