from __future__ import annotations

from src.domain.asset import Asset
from src.domain.product_analysis import (
    MaterialGuess,
    PackagingStructure,
    ProductAnalysis,
    VisualConstraints,
    VisualIdentity,
)


def build_mock_product_analysis(assets: list[Asset], product_name: str) -> ProductAnalysis:
    """构造本地 mock 的 SKU 级视觉分析结果。

    这里仍然是占位实现，但输出结构已经对齐为“商品外观分析”而不是通用茶叶卖点。
    """
    asset_ids = [asset.asset_id for asset in assets]
    return ProductAnalysis(
        analysis_scope="sku_level",
        intended_for="all_future_shots",
        category="tea",
        subcategory=product_name or "unknown",
        product_type=product_name or "unknown",
        product_form="packaged_tea",
        packaging_structure=PackagingStructure(
            primary_container="unknown",
            has_outer_box="unknown",
            has_visible_lid="unknown",
            container_count=str(len(asset_ids)) if asset_ids else "unknown",
        ),
        visual_identity=VisualIdentity(
            dominant_colors=["unknown"],
            label_position="unknown",
            label_ratio="low_confidence",
            style_impression=["mock_visual_analysis"],
            must_preserve=["包装主体轮廓", "标签主视觉区域"],
        ),
        material_guess=MaterialGuess(
            container_material="unknown",
            label_material="unknown",
        ),
        visual_constraints=VisualConstraints(
            recommended_style_direction=["突出包装主体", "保留标签区可读性", "延续商品原始色调"],
            avoid=["不要虚构额外包装结构", "不要把行业卖点当作图片分析结果"],
        ),
        selling_points=[],
        visual_style_keywords=["包装主体", "标签区域", "原始主色调"],
        recommended_focuses=["包装主体", "标签布局", "材质反光控制"],
        source_asset_ids=asset_ids,
    )

