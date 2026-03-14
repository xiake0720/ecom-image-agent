"""图组规划节点。

文件位置：
- `src/workflows/nodes/plan_shots.py`

核心职责：
- 根据商品分析结果生成 `shot_plan.json`
- 茶叶类 Phase 1 固定输出 5 个标准图位，模型只允许补每个图位的细节字段

节点前后关系：
- 上游节点：`style_director`
- 下游节点：`generate_copy`

关键输入/输出：
- 输入：`task`、`product_analysis`，以及可选的 `style_architecture`
- 输出：`shot_plan` 写回 state，并落盘为 `shot_plan.json`
"""

from __future__ import annotations

import logging

from src.domain.shot_plan import ShotPlan, ShotSpec, TeaShotEnrichmentPlan
from src.services.planning.shot_planner import build_mock_shot_plan
from src.services.planning.tea_shot_planner import (
    build_tea_enrichment_context,
    build_tea_shot_plan,
    build_tea_shot_slots,
    merge_tea_slot_details,
    resolve_tea_package_template_family,
)
from src.services.prompting.context_builder import build_plan_shots_context, infer_category_family
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


def plan_shots(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """根据商品分析结果生成图组规划。

    调用链位置：
    - 由 `graph.py` 在 `style_director` 之后调用
    - 结果会被 `generate_copy / generate_layout / shot_prompt_refiner` 继续消费

    关键副作用：
    - 落盘 `shot_plan.json`
    - 写入调试日志，明确本次是否走了茶叶固定五图模板
    """
    task = state["task"]
    logs = [*state.get("logs", []), f"[plan_shots] start mode={deps.text_provider_mode} target_shot_count={task.shot_count}"]
    logs.extend(format_connected_contract_logs(state, node_name="plan_shots"))
    category_family = infer_category_family(state["product_analysis"])
    planning_context = build_plan_shots_context(task=task, product_analysis=state["product_analysis"])
    style_anchor_summary = planning_context["group_style_anchor_summary"]
    style_theme_summary = getattr(state.get("style_architecture"), "style_theme", "")
    template_name = "plan_shots.md"
    template_source = describe_prompt_source(template_name)
    provider_name, provider_model_id = planning_provider_identity(deps)
    tea_template_enabled = category_family == "tea"
    tea_slots = build_tea_shot_slots(task, state["product_analysis"]) if tea_template_enabled else []
    package_template_family = (
        resolve_tea_package_template_family(state["product_analysis"]) if tea_template_enabled else ""
    )
    shot_type_summary = ", ".join(f"{shot.shot_id}:{shot.shot_type}" for shot in tea_slots) or "-"
    fixed_shot_ids = [shot.shot_id for shot in tea_slots]
    cache_key, cache_context = build_node_cache_key(
        node_name="plan_shots",
        state=state,
        deps=deps,
        prompt_filename=template_name if deps.text_provider_mode == "real" else None,
        prompt_version="mock-shot-plan-v1" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "planning_context_hash": hash_state_payload(planning_context),
            "tea_slot_hash": hash_state_payload(tea_slots),
            "planning_strategy": "tea_fixed_five_then_enrich" if tea_template_enabled else "standard_generation",
        },
    )
    logger.info(
        "plan_shots category_family=%s group_style_anchor_summary=%s template_source=%s tea_fixed_template=%s",
        category_family,
        style_anchor_summary,
        template_source,
        tea_template_enabled,
    )
    logs.extend(
        [
            f"[plan_shots] category_family={category_family}",
            f"[plan_shots] group_style_anchor_summary={style_anchor_summary}",
            f"[plan_shots] style_architecture_theme_summary={style_theme_summary or '-'}",
            f"[plan_shots] template_source={template_source}",
            f"[plan_shots] tea_fixed_phase1_template={str(tea_template_enabled).lower()}",
            f"[plan_shots] package_template_family={package_template_family or '-'}",
        ]
    )
    if tea_template_enabled:
        # 这组日志是为了让调试时一眼看出当前不是“自由生成图型”，而是“固定模板 + 模型补细节”。
        logs.extend(
            [
                f"[plan_shots] fixed_shot_ids={fixed_shot_ids}",
                f"[plan_shots] shot_type_summary={shot_type_summary}",
                f"[plan_shots] fixed_template_name={package_template_family or 'tea_gift_box'}",
                "[plan_shots] model_enrichment_only=true fields=goal,focus,scene_direction,composition_direction,text_safe_zone_preference",
            ]
        )

    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("plan_shots", cache_key, ShotPlan)
        if cached_plan is not None:
            deps.storage.save_json_artifact(task.task_id, "shot_plan.json", cached_plan)
            core_count, extension_count = _count_core_and_extension_shots(cached_plan, planning_context)
            logger.info("plan_shots cache hit, key=%s", cache_key)
            logs.extend(
                [
                    f"[cache] node=plan_shots status=hit key={cache_key}",
                    f"[plan_shots] core_count={core_count} extension_count={extension_count}",
                    "[plan_shots] restored cached shot_plan.json",
                ]
            )
            return {"shot_plan": cached_plan, "logs": logs}
        logger.info("plan_shots cache miss, key=%s", cache_key)
        logs.append(f"[cache] node=plan_shots status=miss key={cache_key}")
    elif is_force_rerun(state):
        logger.info("plan_shots ignore cache due to forced rerun")
        logs.append("[cache] node=plan_shots status=ignored reason=force_rerun")

    if deps.text_provider_mode == "real":
        if tea_template_enabled:
            shot_plan = _plan_tea_shots_real_mode(
                task=task,
                product_analysis=state["product_analysis"],
                deps=deps,
                planning_context=planning_context,
                logs=logs,
                template_name=template_name,
                tea_slots=tea_slots,
            )
        else:
            prompt = (
                "请基于结构化商品分析结果规划当前任务的电商图组。\n"
                "先在内部确定类目族群、整组统一风格锚点、核心图型与扩展图型，再只输出符合 ShotPlan schema 的 JSON。\n"
                f"任务信息:\n{dump_pretty(task)}\n\n"
                f"商品分析:\n{dump_pretty(state['product_analysis'])}\n\n"
                f"结构化规划上下文:\n{dump_pretty(planning_context)}"
            )
            shot_plan = deps.planning_provider.generate_structured(
                prompt,
                ShotPlan,
                system_prompt=load_prompt_text(template_name),
            )
    else:
        if tea_template_enabled:
            shot_plan = build_tea_shot_plan(task, state["product_analysis"])
        else:
            shot_plan = build_mock_shot_plan(state["product_analysis"], task.shot_count)

    deps.storage.save_json_artifact(task.task_id, "shot_plan.json", shot_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("plan_shots", cache_key, shot_plan, metadata=cache_context)
    shot_ids = ", ".join(shot.shot_id for shot in shot_plan.shots)
    core_count, extension_count = _count_core_and_extension_shots(shot_plan, planning_context)
    logs.extend(
        [
            f"[plan_shots] completed count={len(shot_plan.shots)} shot_ids={shot_ids or '-'}",
            f"[plan_shots] core_count={core_count} extension_count={extension_count}",
            f"[plan_shots] planning_model={deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}",
            "[plan_shots] saved shot_plan.json",
        ]
    )
    return {"shot_plan": shot_plan, "logs": logs}


def _plan_tea_shots_real_mode(
    *,
    task,
    product_analysis,
    deps: WorkflowDependencies,
    planning_context: dict[str, object],
    logs: list[str],
    template_name: str,
    tea_slots: list[ShotSpec],
) -> ShotPlan:
    """茶叶类 real 模式：固定模板，仅允许模型补细节字段。"""
    enrichment_context = build_tea_enrichment_context(task, product_analysis, tea_slots, planning_context)
    logs.append(
        "[plan_shots] tea fixed five-shot template active; model enriches only goal/focus/scene_direction/composition_direction/text_safe_zone_preference"
    )
    prompt = (
        "当前是 tea 类目的图组规划。\n"
        "不要从零自由发散整套图组，必须先使用给定的固定五图 shot slots。\n"
        "你只能补每张图的 goal、focus、scene_direction、composition_direction、text_safe_zone_preference。\n"
        "不得新增、删除或替换任何 slot，不得改动 shot_id、shot_type、title、purpose、composition_hint、copy_goal、required_subjects、optional_props。\n"
        f"结构化补充上下文:\n{dump_pretty(enrichment_context)}"
    )
    enriched_plan = deps.planning_provider.generate_structured(
        prompt,
        TeaShotEnrichmentPlan,
        system_prompt=load_prompt_text(template_name),
    )
    return merge_tea_slot_details(tea_slots, enriched_plan)


def _count_core_and_extension_shots(shot_plan: ShotPlan, planning_context: dict[str, object]) -> tuple[int, int]:
    """统计核心图型和扩展图型数量，便于日志和调试。"""
    category_policy = planning_context.get("category_policy", {})
    core_set = set(category_policy.get("core_shot_types", []))
    extension_set = set(category_policy.get("optional_shot_types", []))
    core_count = 0
    extension_count = 0
    for shot in shot_plan.shots:
        if shot.shot_type in core_set:
            core_count += 1
        elif shot.shot_type in extension_set:
            extension_count += 1
        else:
            extension_count += 1
    return core_count, extension_count
