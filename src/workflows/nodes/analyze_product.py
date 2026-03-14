"""商品分析节点。

文件位置：
- `src/workflows/nodes/analyze_product.py`

核心职责：
- 选择用于分析的参考图
- 调用视觉分析 provider 或 mock 规则
- 输出 `product_analysis.json`

节点前后关系：
- 上游节点：`ingest_assets`
- 下游节点：`style_director`

关键输入/输出：
- 输入：`task`、`assets`
- 输出：`product_analysis` 及分析用参考图调试字段
"""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.domain.product_analysis import ProductAnalysis
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.services.assets.reference_selector import ReferenceSelection, select_reference_bundle
from src.services.planning.tea_shot_planner import resolve_tea_package_template_family
from src.workflows.nodes.cache_utils import (
    build_node_cache_key,
    is_force_rerun,
    should_use_cache,
    vision_provider_identity,
)
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text
from src.workflows.state import WorkflowDependencies, WorkflowState, format_connected_contract_logs

logger = logging.getLogger(__name__)


def analyze_product(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘商品分析结果。

    参数：
    - state：当前 workflow 状态，必须包含 `task` 和 `assets`
    - deps：依赖注入对象，内部提供视觉分析 provider 和 storage

    返回值：
    - 包含 `product_analysis` 以及参考图选择调试字段的字典

    关键副作用：
    - 调用真实视觉分析 provider 或 mock 分析逻辑
    - 写入 `product_analysis.json`
    - 记录参考图选择日志，便于后续排查“主图为什么选错”
    """
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
                "product_lock": cached_analysis,
                "analyze_reference_asset_ids": selected_asset_ids,
                "analyze_selected_main_asset_id": selection.selected_main_asset_id,
                "analyze_selected_detail_asset_id": selection.selected_detail_asset_id,
                "analyze_reference_selection_reason": selection.selection_reason,
                "logs": [*logs, *format_connected_contract_logs({"product_analysis": cached_analysis, "product_lock": cached_analysis}, node_name="analyze_product")],
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
        analysis = _normalize_product_lock_fields(analysis.model_copy(update={"source_asset_ids": selected_asset_ids}))
    else:
        analysis = build_mock_product_analysis(state.get("assets", []), task.product_name)
        analysis = _normalize_product_lock_fields(analysis.model_copy(update={"source_asset_ids": selected_asset_ids}))

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
                f"package_template_family={analysis.package_template_family or '-'} "
                f"must_preserve={len(analysis.visual_identity.must_preserve)}"
            ),
            f"[analyze_product] vision_model={deps.vision_model_selection.model_id if deps.vision_model_selection else '-'}",
            "[analyze_product] saved product_analysis.json",
        ]
    )
    logs.extend(format_connected_contract_logs({"product_analysis": analysis, "product_lock": analysis}, node_name="analyze_product"))
    return {
        "product_analysis": analysis,
        "product_lock": analysis,
        "analyze_reference_asset_ids": selected_asset_ids,
        "analyze_selected_main_asset_id": selection.selected_main_asset_id,
        "analyze_selected_detail_asset_id": selection.selected_detail_asset_id,
        "analyze_reference_selection_reason": selection.selection_reason,
        "logs": logs,
    }


def _resolve_analyze_max_reference_images(state: WorkflowState) -> int:
    """解析分析阶段可使用的参考图数量上限。"""
    explicit_value = state.get("analyze_max_reference_images")
    if explicit_value is not None:
        return max(1, int(explicit_value))
    return max(1, int(get_settings().analyze_max_reference_images))


def _select_analysis_assets(state: WorkflowState) -> ReferenceSelection:
    """分析阶段和渲染阶段共用同一套参考图选择规则。"""
    return select_reference_bundle(
        state.get("assets", []),
        max_images=_resolve_analyze_max_reference_images(state),
    )


def _format_selection_logs(*, node_name: str, selection: ReferenceSelection) -> list[str]:
    """统一输出参考图选择日志，便于 UI 和任务日志同时查看。"""
    return [
        (
            f"[{node_name}] selected_main_asset_id={selection.selected_main_asset_id or '-'} "
            f"selected_detail_asset_id={selection.selected_detail_asset_id or '-'} "
            f"selected_reference_asset_ids={selection.selected_asset_ids or []}"
        ),
        f"[{node_name}] selection_reason={selection.selection_reason}",
    ]


def _normalize_product_lock_fields(analysis: ProductAnalysis) -> ProductAnalysis:
    """把旧分析结果补齐成当前 image_edit 链路需要的 product_lock 字段。

    这样做的原因：
    - 历史分析结构和当前图生图链路需要的字段并不完全一致
    - 在这里统一归一化后，后面的 style/prompt/render 节点就可以稳定消费
    """
    package_type = analysis.package_type or analysis.packaging_structure.primary_container
    primary_color = analysis.primary_color or (analysis.visual_identity.dominant_colors[0] if analysis.visual_identity.dominant_colors else "")
    material = analysis.material or analysis.material_guess.container_material
    label_structure = analysis.label_structure or (
        f"{analysis.visual_identity.label_position} label / ratio={analysis.visual_identity.label_ratio}"
    )
    locked_elements = analysis.locked_elements or [
        *analysis.visual_identity.must_preserve,
        "package silhouette",
        "front label layout",
    ]
    editable_elements = analysis.editable_elements or ["background", "props", "lighting", "crop"]
    package_template_family = analysis.package_template_family or resolve_tea_package_template_family(
        analysis.model_copy(
            update={
                "package_type": package_type,
                "primary_color": primary_color,
                "material": material,
                "label_structure": label_structure,
            }
        )
    )
    return analysis.model_copy(
        update={
            "locked_elements": locked_elements,
            "must_preserve_texts": analysis.must_preserve_texts or [],
            "editable_elements": editable_elements,
            "package_type": package_type,
            "package_template_family": package_template_family,
            "primary_color": primary_color,
            "material": material,
            "label_structure": label_structure,
        }
    )
