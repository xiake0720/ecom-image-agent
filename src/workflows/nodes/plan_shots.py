"""图组规划节点。"""

from __future__ import annotations

import logging

from src.domain.shot_plan import ShotPlan
from src.services.planning.shot_planner import build_mock_shot_plan
from src.services.planning.tea_shot_planner import (
    build_tea_enrichment_context,
    build_tea_shot_plan,
    build_tea_shot_slots,
    merge_tea_slot_details,
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
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def plan_shots(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """根据商品分析结果生成图组规划。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[plan_shots] 开始图组规划，模式={deps.text_provider_mode}，目标张数={task.shot_count}。"]
    category_family = infer_category_family(state["product_analysis"])
    planning_context = build_plan_shots_context(task=task, product_analysis=state["product_analysis"])
    style_anchor_summary = planning_context["group_style_anchor_summary"]
    template_name = "plan_shots.md"
    template_source = describe_prompt_source(template_name)
    provider_name, provider_model_id = planning_provider_identity(deps)
    tea_slots = build_tea_shot_slots(task, state["product_analysis"]) if category_family == "tea" else []
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
            "planning_strategy": "tea_slots_then_enrich" if category_family == "tea" else "standard_generation",
        },
    )
    logger.info(
        "plan_shots 当前识别类目族群=%s，整组风格锚点摘要=%s，模板来源=%s",
        category_family,
        style_anchor_summary,
        template_source,
    )
    logs.extend(
        [
            f"[plan_shots] 当前识别到的类目族群：{category_family}。",
            f"[plan_shots] 当前选择的整组风格锚点摘要：{style_anchor_summary}。",
            f"[plan_shots] 当前使用的模板来源文件：{template_source}。",
        ]
    )
    if category_family == "tea":
        logs.append("[plan_shots] tea 类目优先走模板化槽位规划，仅允许模型少量补充单张图细节。")

    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("plan_shots", cache_key, ShotPlan)
        if cached_plan is not None:
            deps.storage.save_json_artifact(task.task_id, "shot_plan.json", cached_plan)
            core_count, extension_count = _count_core_and_extension_shots(cached_plan, planning_context)
            logger.info("plan_shots cache hit，key=%s", cache_key)
            logs.extend(
                [
                    f"[plan_shots] cache hit，命中节点缓存，key={cache_key}。",
                    f"[plan_shots] 当前生成的核心图型数量={core_count}，扩展图型数量={extension_count}。",
                    "[plan_shots] 已从缓存恢复结果并写入 shot_plan.json。",
                ]
            )
            return {"shot_plan": cached_plan, "logs": logs}
        logger.info("plan_shots cache miss，key=%s", cache_key)
        logs.append(f"[plan_shots] cache miss，未命中节点缓存，key={cache_key}。")
    elif is_force_rerun(state):
        logger.info("plan_shots ignore cache，forced rerun")
        logs.append("[plan_shots] ignore cache，已忽略缓存并强制重跑。")

    if deps.text_provider_mode == "real":
        if category_family == "tea":
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
        if category_family == "tea":
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
            f"[plan_shots] 图组规划完成，数量={len(shot_plan.shots)}，shot_ids={shot_ids or '-'}。",
            f"[plan_shots] 当前生成的核心图型数量={core_count}，扩展图型数量={extension_count}。",
            f"[plan_shots] 当前实际规划模型={deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}。",
            "[plan_shots] 已写入 shot_plan.json。",
        ]
    )
    return {"shot_plan": shot_plan, "logs": logs}


def _plan_tea_shots_real_mode(*, task, product_analysis, deps: WorkflowDependencies, planning_context: dict[str, object], logs: list[str], template_name: str, tea_slots: list) -> ShotPlan:
    enrichment_context = build_tea_enrichment_context(task, product_analysis, tea_slots, planning_context)
    logs.append(f"[plan_shots] tea 模板化槽位数量={len(tea_slots)}，当前仅补充 goal、focus、scene_direction、composition_direction。")
    prompt = (
        "当前是 tea 类目的图组规划。\n"
        "不要从零自由发散整套图组，必须先使用给定的标准 shot slots，再仅补充每张图的 goal、focus、scene_direction、composition_direction。\n"
        "不得新增、删除或替换任何 slot，不得改动 shot_type、shot_id、title、purpose、composition_hint、copy_goal。\n"
        f"结构化补充上下文:\n{dump_pretty(enrichment_context)}"
    )
    enriched_plan = deps.planning_provider.generate_structured(
        prompt,
        ShotPlan,
        system_prompt=load_prompt_text(template_name),
    )
    return merge_tea_slot_details(tea_slots, enriched_plan)


def _count_core_and_extension_shots(shot_plan: ShotPlan, planning_context: dict[str, object]) -> tuple[int, int]:
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
