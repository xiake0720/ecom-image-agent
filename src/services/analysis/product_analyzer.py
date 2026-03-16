"""商品分析 mock 构造工具。

文件位置：
- `src/services/analysis/product_analyzer.py`

核心职责：
- 为 mock 模式生成 `ProductAnalysis`。
- 这次额外承担茶叶包装模板族的基础判定，让后续 `plan_shots` 不再把所有茶叶都当礼盒。

主要被谁调用：
- `src/workflows/nodes/analyze_product.py`

关键输入/输出：
- 输入：上传资产列表、商品名
- 输出：带有 `package_type / material / package_template_family` 的 `ProductAnalysis`
"""

from __future__ import annotations

from src.domain.asset import Asset, AssetType
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)
from src.services.planning.tea_shot_planner import resolve_tea_package_template_family


def build_mock_product_analysis(assets: list[Asset], product_name: str) -> ProductAnalysis:
    """构造本地 mock 的 SKU 级商品锁定分析结果。"""
    asset_ids = [asset.asset_id for asset in assets]
    has_detail_asset = any(asset.asset_type == AssetType.DETAIL for asset in assets)
    product_name_lower = str(product_name or "").lower()
    # 这里先用轻量关键词做包型判断，目标不是精准 CV 识别，而是给 shot planning 足够稳定的模板输入。
    if any(token in product_name_lower for token in ("tin", "can", "罐", "金属罐", "铁罐")):
        package_type = "cylindrical metal tin"
        primary_container = "tin_can"
        container_material = "metal tin"
        material = "cylindrical metal tin"
        visual_keywords = ["premium", "tea tin", "cylindrical can"]
        recommended_focuses = ["tin hero view", "package detail", "dry leaf", "tea soup"]
        label_structure = "front-centered tin label with cylindrical wrap"
    elif any(token in product_name_lower for token in ("pouch", "bag", "袋", "袋装", "自立袋")):
        package_type = "tea pouch"
        primary_container = "pouch"
        container_material = "matte pouch"
        material = "matte tea pouch"
        visual_keywords = ["premium", "tea pouch", "portable packaging"]
        recommended_focuses = ["pouch hero view", "package detail", "dry leaf", "tea soup"]
        label_structure = "front pouch label with zipper-top structure"
    else:
        package_type = "gift_box"
        primary_container = "gift_box"
        container_material = "paper gift box"
        material = "paper gift box with metallic accents"
        visual_keywords = ["premium", "gift box", "tea packaging"]
        recommended_focuses = ["package hero view", "open box structure", "dry leaf", "tea soup"]
        label_structure = "front-centered hero label with secondary side panels"

    analysis = ProductAnalysis(
        analysis_scope="sku_level",
        intended_for="all_future_shots",
        category="tea",
        subcategory=product_name or "unknown",
        product_type=product_name or "unknown",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container=primary_container,
            has_outer_box="yes" if primary_container == "gift_box" else "no",
            has_visible_lid="yes" if primary_container in {"gift_box", "tin_can"} else "no",
            container_count=str(len(asset_ids)) if asset_ids else "1",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["red", "gold"],
            label_position="front_center",
            label_ratio="medium",
            style_impression=["premium tea packaging"],
            must_preserve=["package silhouette", "front label zone", "brand mark position"],
        ),
        material_guess=MaterialGuess(
            container_material=container_material,
            label_material="matte paper with foil accents",
        ),
        visual_constraints=VisualConstraints(
            recommended_style_direction=[
                "keep the package body unchanged",
                "preserve the front label readability",
                "let the package remain the only saturated visual focus",
            ],
            avoid=[
                "do not invent extra package structures",
                "do not redesign the main label",
            ],
        ),
        selling_points=[],
        visual_style_keywords=visual_keywords,
        recommended_focuses=recommended_focuses,
        source_asset_ids=asset_ids,
        locked_elements=["package silhouette", "front label layout", "brand mark placement"],
        must_preserve_texts=[product_name] if product_name else [],
        text_anchor_status="readable" if product_name else "unreadable",
        text_anchor_source="fallback" if product_name else "none",
        text_anchor_notes=[] if product_name else ["mock analysis could not infer stable package text anchors"],
        editable_elements=["background", "props", "lighting", "camera crop"],
        package_type=package_type,
        asset_completeness_mode="packshot_plus_detail" if has_detail_asset else "packshot_only",
        primary_color="red",
        material=material,
        label_structure=label_structure,
    )
    return analysis.model_copy(
        update={
            "package_template_family": resolve_tea_package_template_family(analysis),
        }
    )
