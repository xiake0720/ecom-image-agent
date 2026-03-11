from __future__ import annotations

from src.domain.asset import Asset
from src.domain.product_analysis import ProductAnalysis


def build_mock_product_analysis(assets: list[Asset], product_name: str) -> ProductAnalysis:
    # TODO: Replace heuristics with provider-backed multimodal analysis.
    return ProductAnalysis(
        category="tea",
        product_type=product_name or "茶叶",
        selling_points=["清香耐泡", "适合日常冲泡", "电商主图展示友好"],
        visual_style_keywords=["清透", "自然", "茶感"],
        recommended_focuses=["包装主体", "茶叶细节", "冲泡氛围"],
        source_asset_ids=[asset.asset_id for asset in assets],
    )

