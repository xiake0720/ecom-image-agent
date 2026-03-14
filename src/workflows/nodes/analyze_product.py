"""Product analysis node."""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.product_analysis import ProductAnalysis
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.assets.reference_selector import ReferenceSelection, select_reference_bundle
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
    """Generate and persist product analysis."""
    task = state["task"]
    logs = [*state.get("logs", []), f"[analyze_product] start mode={deps.vision_provider_mode}"]
    provider_name, provider_model_id = vision_provider_identity(deps)
    selection = _select_analysis_assets(state)
    selected_assets = selection.selected_assets
    selected_asset_ids = selection.selected_asset_ids
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
    logs.extend(_format_selection_logs(node_name="analyze_product", selection=selection))

    if should_use_cache(state):
        cached_analysis = deps.storage.load_cached_json_artifact("analyze_product", cache_key, ProductAnalysis)
        if cached_analysis is not None:
            deps.storage.save_json_artifact(task.task_id, "product_analysis.json", cached_analysis)
            logs.extend(
                [
                    f"[analyze_product] cache hit key={cache_key}",
                    f"[cache] node=analyze_product status=hit key={cache_key}",
                    "[analyze_product] restored cached product_analysis.json",
                ]
            )
            return {
                "product_analysis": cached_analysis,
                "analyze_reference_asset_ids": selected_asset_ids,
                "analyze_selected_main_asset_id": selection.selected_main_asset_id,
                "analyze_selected_detail_asset_id": selection.selected_detail_asset_id,
                "analyze_reference_selection_reason": selection.selection_reason,
                "logs": logs,
            }
        logs.extend(
            [
                f"[analyze_product] cache miss key={cache_key}",
                f"[cache] node=analyze_product status=miss key={cache_key}",
            ]
        )
    elif is_force_rerun(state):
        logs.extend(
            [
                "[analyze_product] ignore cache requested",
                "[cache] node=analyze_product status=ignored key=-",
            ]
        )

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
        analysis = analysis.model_copy(update={"source_asset_ids": selected_asset_ids})

    deps.storage.save_json_artifact(task.task_id, "product_analysis.json", analysis)
    if state.get("cache_enabled"):
        deps.storage.save_cached_json_artifact("analyze_product", cache_key, analysis, metadata=cache_context)
    logs.extend(
        [
            (
                "[analyze_product] completed "
                f"category={analysis.category} "
                f"subcategory={analysis.subcategory} "
                f"product_form={analysis.product_form} "
                f"must_preserve={len(analysis.visual_identity.must_preserve)}"
            ),
            f"[analyze_product] vision_model={deps.vision_model_selection.model_id if deps.vision_model_selection else '-'}",
            "[analyze_product] saved product_analysis.json",
        ]
    )
    return {
        "product_analysis": analysis,
        "analyze_reference_asset_ids": selected_asset_ids,
        "analyze_selected_main_asset_id": selection.selected_main_asset_id,
        "analyze_selected_detail_asset_id": selection.selected_detail_asset_id,
        "analyze_reference_selection_reason": selection.selection_reason,
        "logs": logs,
    }


def _resolve_analyze_max_reference_images(state: WorkflowState) -> int:
    explicit_value = state.get("analyze_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    return max(1, int(get_settings().analyze_max_reference_images))


def _select_analysis_assets(state: WorkflowState) -> ReferenceSelection:
    return select_reference_bundle(
        state.get("assets", []),
        max_images=_resolve_analyze_max_reference_images(state),
    )


def _format_selection_logs(*, node_name: str, selection: ReferenceSelection) -> list[str]:
    return [
        (
            f"[{node_name}] selected_main_asset_id={selection.selected_main_asset_id or '-'} "
            f"selected_detail_asset_id={selection.selected_detail_asset_id or '-'} "
            f"selected_reference_asset_ids={selection.selected_asset_ids or []}"
        ),
        f"[{node_name}] selection_reason={selection.selection_reason}",
    ]
