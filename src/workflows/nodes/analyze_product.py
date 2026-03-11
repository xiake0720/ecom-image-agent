"""商品分析节点。

当前节点位于 workflow 文本链路起点，负责输出 `ProductAnalysis`。
在 mock 模式下走本地规则，在 real 模式下走真实文本 provider。
"""

from __future__ import annotations

from src.domain.product_analysis import ProductAnalysis
from src.services.analysis.product_analyzer import build_mock_product_analysis
from src.workflows.state import WorkflowDependencies, WorkflowState
from src.workflows.nodes.prompt_utils import dump_pretty, load_prompt_text


def analyze_product(state: WorkflowState, deps: WorkflowDependencies) -> dict:
    """生成并落盘商品分析结果。"""
    task = state["task"]
    logs = [*state.get("logs", []), f"[analyze_product] start mode={deps.text_provider_mode}."]
    if deps.text_provider_mode == "real":
        assets_payload = [
            {
                "asset_id": asset.asset_id,
                "filename": asset.filename,
                "asset_type": asset.asset_type.value,
                "width": asset.width,
                "height": asset.height,
                "tags": asset.tags,
            }
            for asset in state.get("assets", [])
        ]
        prompt = (
            "请基于当前茶叶商品任务输出结构化商品分析结果。\n"
            f"任务信息:\n{dump_pretty(task)}\n\n"
            f"素材信息:\n{dump_pretty(assets_payload)}"
        )
        # 真实模式下要求 provider 直接返回可被 schema 校验的结构化 JSON。
        analysis = deps.text_provider.generate_structured(
            prompt,
            ProductAnalysis,
            system_prompt=load_prompt_text("analyze_product.md"),
        )
        analysis = analysis.model_copy(
            update={"source_asset_ids": [asset.asset_id for asset in state.get("assets", [])]}
        )
    else:
        analysis = build_mock_product_analysis(state.get("assets", []), task.product_name)
    deps.storage.save_json_artifact(task.task_id, "product_analysis.json", analysis)
    logs.extend(
        [
            (
                "[analyze_product] result "
                f"category={analysis.category}, product_type={analysis.product_type}, "
                f"selling_points={len(analysis.selling_points)}, focuses={len(analysis.recommended_focuses)}."
            ),
            "[analyze_product] saved product_analysis.json.",
        ]
    )
    return {"product_analysis": analysis, "logs": logs}
