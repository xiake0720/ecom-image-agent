"""参考图选择器。

文件位置：
- `src/services/assets/reference_selector.py`

职责：
- 从上传素材中挑选产品参考图与背景风格参考图
- 优先保证白底包装图作为主参考，详情图作为补充参考
- 明确把背景风格参考图与产品保真参考图分开
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.engine.domain.asset import Asset, AssetType


@dataclass(frozen=True)
class ReferenceSelection:
    """参考图选择结果。"""

    main_asset: Asset | None
    detail_asset: Asset | None
    product_reference_assets: list[Asset]
    background_style_assets: list[Asset]
    selected_assets: list[Asset]
    selected_asset_ids: list[str]
    selected_main_asset_id: str | None
    selected_detail_asset_id: str | None
    background_style_asset_ids: list[str]
    selection_reason: str


def select_reference_bundle(
    assets: list[Asset],
    *,
    max_images: int = 2,
    max_background_style_images: int = 2,
) -> ReferenceSelection:
    """优先返回白底主图和详情图，并额外保留背景风格参考图。"""

    if not assets or max_images <= 0:
        return ReferenceSelection(
            main_asset=None,
            detail_asset=None,
            product_reference_assets=[],
            background_style_assets=[],
            selected_assets=[],
            selected_asset_ids=[],
            selected_main_asset_id=None,
            selected_detail_asset_id=None,
            background_style_asset_ids=[],
            selection_reason="no_assets",
        )

    background_style_assets = [
        asset for asset in assets if asset.asset_type == AssetType.BACKGROUND_STYLE
    ][: max(0, max_background_style_images)]
    product_candidates = [asset for asset in assets if asset.asset_type != AssetType.BACKGROUND_STYLE]
    white_bg_assets = [
        asset for asset in product_candidates if asset.asset_type in {AssetType.WHITE_BG, AssetType.PRODUCT}
    ]
    detail_assets = [asset for asset in product_candidates if asset.asset_type == AssetType.DETAIL]

    main_asset = white_bg_assets[0] if white_bg_assets else (product_candidates[0] if product_candidates else None)
    detail_asset = detail_assets[0] if detail_assets else None

    product_reference_assets: list[Asset] = []
    if main_asset is not None:
        product_reference_assets.append(main_asset)
    if detail_asset is not None and detail_asset not in product_reference_assets and len(product_reference_assets) < max_images:
        product_reference_assets.append(detail_asset)
    if len(product_reference_assets) < max_images:
        for asset in product_candidates:
            if asset in product_reference_assets:
                continue
            product_reference_assets.append(asset)
            if len(product_reference_assets) >= max_images:
                break

    selected_assets = [*product_reference_assets, *background_style_assets]
    return ReferenceSelection(
        main_asset=main_asset,
        detail_asset=detail_asset if detail_asset in product_reference_assets else None,
        product_reference_assets=product_reference_assets,
        background_style_assets=background_style_assets,
        selected_assets=selected_assets,
        selected_asset_ids=[asset.asset_id for asset in selected_assets],
        selected_main_asset_id=main_asset.asset_id if main_asset is not None else None,
        selected_detail_asset_id=detail_asset.asset_id if detail_asset in product_reference_assets else None,
        background_style_asset_ids=[asset.asset_id for asset in background_style_assets],
        selection_reason="prefer_white_bg_then_detail_keep_background_style_separate",
    )
