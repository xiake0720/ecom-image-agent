"""文案生成节点。"""

from __future__ import annotations

import logging

from src.domain.copy_plan import CopyPlan
from src.services.planning.copy_generator import build_mock_copy_plan
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    planning_provider_identity,
    should_use_cache,
)
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def generate_copy(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘结构化中文文案。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[generate_copy] 开始生成文案，模式={deps.text_provider_mode}。"]
    provider_name, provider_model_id = planning_provider_identity(deps)
    cache_key, cache_context = build_node_cache_key(
        node_name="generate_copy",
        state=state,
        deps=deps,
        prompt_filename="generate_copy.md" if deps.text_provider_mode == "real" else None,
        prompt_version="mock-copy-plan-v1" if deps.text_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "product_analysis_hash": hash_state_payload(state["product_analysis"]),
            "shot_plan_hash": hash_state_payload(state["shot_plan"]),
        },
    )
    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("generate_copy", cache_key, CopyPlan)
        if cached_plan is not None:
            deps.storage.save_json_artifact(task.task_id, "copy_plan.json", cached_plan)
            logger.info("generate_copy cache hit，key=%s", cache_key)
            logs.extend(
                [
                    f"[generate_copy] cache hit，命中节点缓存，key={cache_key}。",
                    "[generate_copy] 已从缓存恢复结果并写入 copy_plan.json。",
                ]
            )
            return {"copy_plan": cached_plan, "logs": logs}
        logger.info("generate_copy cache miss，key=%s", cache_key)
        logs.append(f"[generate_copy] cache miss，未命中节点缓存，key={cache_key}。")
    elif is_force_rerun(state):
        logger.info("generate_copy ignore cache，forced rerun")
        logs.append("[generate_copy] ignore cache，已忽略缓存并强制重跑。")

    if deps.text_provider_mode == "real":
        model_label = deps.planning_model_selection.label if deps.planning_model_selection else "-"
        model_id = deps.planning_model_selection.model_id if deps.planning_model_selection else "-"
        logger.info(
            "generate_copy 当前走结构化规划 real 模式，provider=%s，模型=%s，model_id=%s",
            deps.planning_provider_name or "unknown",
            model_label,
            model_id,
        )
        prompt = (
            "请基于任务信息、商品分析和图组规划，为每个 shot 生成一条结构化中文文案。\n"
            "只生成 CopyPlan，不要重新规划图组，不要输出布局建议，不要输出自由文本解释。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"商品分析:\n{dump_pretty(state['product_analysis'])}\n\n"
            f"图组规划:\n{dump_pretty(state['shot_plan'])}"
        )
        copy_plan = deps.planning_provider.generate_structured(
            prompt,
            CopyPlan,
            system_prompt=load_prompt_text("generate_copy.md"),
        )
    else:
        copy_plan = build_mock_copy_plan(task, state["shot_plan"])

    deps.storage.save_json_artifact(task.task_id, "copy_plan.json", copy_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact(
            "generate_copy",
            cache_key,
            copy_plan,
            metadata=cache_context,
        )
    first_title = copy_plan.items[0].title if copy_plan.items else ""
    logger.info("文案生成完成，条目数=%s，首条标题=%r", len(copy_plan.items), first_title)
    logs.extend(
        [
            f"[generate_copy] 文案生成完成，items={len(copy_plan.items)}，first_title={first_title!r}。",
            (
                "[generate_copy] 当前实际规划模型="
                f"{deps.planning_model_selection.model_id if deps.planning_model_selection else '-'}。"
            ),
            "[generate_copy] 已写入 copy_plan.json。",
        ]
    )
    return {"copy_plan": copy_plan, "logs": logs}
