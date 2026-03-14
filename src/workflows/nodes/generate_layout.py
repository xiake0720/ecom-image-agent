"""布局生成节点。

文件位置：
- `src/workflows/nodes/generate_layout.py`

核心职责：
- 根据 shot plan 和输出尺寸生成 `layout_plan.json`
- 为每张图选择更稳定的文字安全区 `text_safe_zone`
- 输出安全区打分明细，便于调试“为什么选这个区域”

节点前后关系：
- 上游节点：`generate_copy`
- 下游节点：`shot_prompt_refiner`
"""

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
    logs = [*state.get("logs", []), f"[generate_layout] start output_size={task.output_size}"]
    cache_key, cache_context = build_node_cache_key(
        node_name="generate_layout",
        state=state,
        deps=deps,
        prompt_version="layout-rule-v2",
        provider_name="rule_layout_generator",
        model_id="rule-layout",
        extra_payload={
            "shot_plan_hash": hash_state_payload(state["shot_plan"]),
            "output_size": task.output_size,
            "product_analysis_hash": hash_state_payload(state.get("product_analysis")),
        },
    )
    if should_use_cache(state):
        cached_plan = deps.storage.load_cached_json_artifact("generate_layout", cache_key, LayoutPlan)
        if cached_plan is not None:
            deps.storage.save_json_artifact(task.task_id, "layout_plan.json", cached_plan)
            logger.info("generate_layout cache hit, key=%s", cache_key)
            logs.extend(
                [
                    f"[generate_layout] cache hit key={cache_key}",
                    "[generate_layout] restored cached layout_plan.json",
                ]
            )
            return {"layout_plan": cached_plan, "logs": logs}
        logger.info("generate_layout cache miss, key=%s", cache_key)
        logs.append(f"[generate_layout] cache miss key={cache_key}")
    elif is_force_rerun(state):
        logger.info("generate_layout ignore cache, forced rerun")
        logs.append("[generate_layout] ignore cache requested")

    layout_plan = build_mock_layout_plan(
        state["shot_plan"],
        task.output_size,
        product_analysis=state.get("product_analysis"),
    )
    deps.storage.save_json_artifact(task.task_id, "layout_plan.json", layout_plan)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact(
            "generate_layout",
            cache_key,
            layout_plan,
            metadata=cache_context,
        )
    logger.info("布局生成完成，items=%s，output_size=%s", len(layout_plan.items), task.output_size)
    for item in layout_plan.items:
        score_summary = ", ".join(
            (
                f"{score.zone}:{score.total_score:.2f}"
                f"(distance={score.distance_from_subject_score:.2f},"
                f"uniformity={score.background_uniformity_score:.2f},"
                f"readability={score.text_readability_score:.2f},"
                f"label_penalty={score.label_overlap_penalty:.2f},"
                f"bias={score.composition_bias_score:.2f})"
            )
            for score in item.safe_zone_score_breakdown
        )
        rejected_summary = ", ".join(item.rejected_zones) if item.rejected_zones else "-"
        logs.append(
            (
                "[generate_layout] "
                f"shot_id={item.shot_id} "
                f"chosen_text_safe_zone={item.text_safe_zone} "
                f"selection_reason={item.selection_reason} "
                f"safe_zone_score_breakdown={score_summary or '-'} "
                f"rejected_zones={rejected_summary}"
            )
        )
    logs.extend(
        [
            f"[generate_layout] completed items={len(layout_plan.items)}",
            "[generate_layout] saved layout_plan.json",
        ]
    )
    return {"layout_plan": layout_plan, "logs": logs}
