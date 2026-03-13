"""布局生成节点。"""

from __future__ import annotations

import logging

from src.domain.layout_plan import LayoutPlan
from src.services.planning.layout_generator import build_mock_layout_plan
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    hash_state_payload,
    is_force_rerun,
    should_use_cache,
)
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def generate_layout(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """根据 shot plan 和输出尺寸生成布局计划。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[generate_layout] 开始生成布局，输出尺寸={task.output_size}。"]
    cache_key, cache_context = build_node_cache_key(
        node_name="generate_layout",
        state=state,
        deps=deps,
        prompt_version="layout-rule-v1",
        provider_name="rule_layout_generator",
        model_id="rule-layout",
        extra_payload={
            "shot_plan_hash": hash_state_payload(state["shot_plan"]),
            "output_size": task.output_size,
        },
    )
    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("generate_layout", cache_key, LayoutPlan)
        if cached_plan is not None:
            deps.storage.save_json_artifact(task.task_id, "layout_plan.json", cached_plan)
            logger.info("generate_layout cache hit，key=%s", cache_key)
            logs.extend(
                [
                    f"[generate_layout] cache hit，命中节点缓存，key={cache_key}。",
                    "[generate_layout] 已从缓存恢复结果并写入 layout_plan.json。",
                ]
            )
            return {"layout_plan": cached_plan, "logs": logs}
        logger.info("generate_layout cache miss，key=%s", cache_key)
        logs.append(f"[generate_layout] cache miss，未命中节点缓存，key={cache_key}。")
    elif is_force_rerun(state):
        logger.info("generate_layout ignore cache，forced rerun")
        logs.append("[generate_layout] ignore cache，已忽略缓存并强制重跑。")

    layout_plan = build_mock_layout_plan(state["shot_plan"], task.output_size)
    deps.storage.save_json_artifact(task.task_id, "layout_plan.json", layout_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact(
            "generate_layout",
            cache_key,
            layout_plan,
            metadata=cache_context,
        )
    logger.info("布局生成完成，布局条目数=%s，输出尺寸=%s", len(layout_plan.items), task.output_size)
    logs.extend(
        [
            f"[generate_layout] 布局生成完成，items={len(layout_plan.items)}。",
            "[generate_layout] 已写入 layout_plan.json。",
        ]
    )
    return {"layout_plan": layout_plan, "logs": logs}
