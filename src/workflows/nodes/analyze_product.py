"""商品分析节点。"""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.product_analysis import ProductAnalysis
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.assets.reference_selector import select_reference_assets
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    is_force_rerun,
    should_use_cache,
    vision_provider_identity,
)
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState

logger = logging.getLogger(__name__)


def analyze_product(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘商品分析结果。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[analyze_product] 开始商品分析，模式={deps.vision_provider_mode}。"]
    provider_name, provider_model_id = vision_provider_identity(deps)
    selected_assets = _select_analysis_assets(state)
    selected_asset_ids = [asset.asset_id for asset in selected_assets]
    cache_key, cache_context = build_node_cache_key(
        node_name="analyze_product",
        state=state,
        deps=deps,
        prompt_filename="analyze_product.md" if deps.vision_provider_mode == "real" else None,
        prompt_version="mock-product-analysis-v1" if deps.vision_provider_mode != "real" else None,
        provider_name=provider_name,
        model_id=provider_model_id,
        extra_payload={
            "selected_asset_ids": selected_asset_ids,
            "analyze_max_reference_images": _resolve_analyze_max_reference_images(state),
        },
    )

    if should_use_cache(state):
        cached_analysis = deps.storage.load_cached_json_artifact("analyze_product", cache_key, ProductAnalysis)
        if cached_analysis is not None:
            deps.storage.save_json_artifact(task.task_id, "product_analysis.json", cached_analysis)
            logs.extend(
                [
                    f"[analyze_product] cache hit，命中节点缓存，key={cache_key}。",
                    f"[analyze_product] 本次视觉分析实际参考图 asset_id={selected_asset_ids or ['-']}。",
                    "[analyze_product] 已从缓存恢复结果并写入 product_analysis.json。",
                ]
            )
            return {"product_analysis": cached_analysis, "logs": logs}
        logs.append(f"[analyze_product] cache miss，未命中节点缓存，key={cache_key}。")
    elif is_force_rerun(state):
        logs.append("[analyze_product] ignore cache，已忽略缓存并强制重跑。")

    if deps.vision_provider_mode == "real":
        assets_payload = [
            {
                "asset_id": asset.asset_id,
                "filename": asset.filename,
                "asset_type": asset.asset_type.value,
                "width": asset.width,
                "height": asset.height,
                "tags": asset.tags,
            }
            for asset in selected_assets
        ]
        prompt = (
            "请基于当前上传商品图做 SKU 级视觉分析，并输出结构化商品分析结果。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"素材信息:\n{dump_pretty(assets_payload)}"
        )
        if deps.vision_analysis_provider is None:
            raise RuntimeError("Vision provider is required when ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE=real.")
        analysis = deps.vision_analysis_provider.generate_structured_from_assets(
            prompt,
            ProductAnalysis,
            assets=selected_assets,
            system_prompt=load_prompt_text("analyze_product.md"),
        )
        analysis = analysis.model_copy(update={"source_asset_ids": selected_asset_ids})
    else:
        analysis = build_mock_product_analysis(state.get("assets", []), task.product_name)

    deps.storage.save_json_artifact(task.task_id, "product_analysis.json", analysis)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("analyze_product", cache_key, analysis, metadata=cache_context)
    logs.extend(
        [
            f"[analyze_product] 本次视觉分析实际参考图 asset_id={selected_asset_ids or ['-']}。",
            (
                "[analyze_product] 商品分析完成，"
                f"category={analysis.category}, subcategory={analysis.subcategory}, "
                f"product_form={analysis.product_form}, "
                f"must_preserve={len(analysis.visual_identity.must_preserve)}。"
            ),
            (
                "[analyze_product] 当前实际视觉模型="
                f"{deps.vision_model_selection.model_id if deps.vision_model_selection else '-'}。"
            ),
            "[analyze_product] 已写入 product_analysis.json。",
        ]
    )
    return {"product_analysis": analysis, "logs": logs}


def _resolve_analyze_max_reference_images(state: WorkflowState) -> int:
    explicit_value = state.get("analyze_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    return max(1, int(get_settings().analyze_max_reference_images))


def _select_analysis_assets(state: WorkflowState) -> list:
    return select_reference_assets(
        state.get("assets", []),
        max_images=_resolve_analyze_max_reference_images(state),
    )
