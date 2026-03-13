from __future__ import annotations

from src.domain.asset import Asset, AssetType


def select_reference_assets(assets: list[Asset], *, max_images: int) -> list[Asset]:
    """保守选择参考图：优先 1 张主图，可选再带 1 张 detail。"""
    if max_images <= 0 or not assets:
        return []

    selected: list[Asset] = []
    main_asset = _select_main_asset(assets)
    if main_asset is not None:
        selected.append(main_asset)

    if max_images <= 1:
        return selected

    detail_asset = _select_detail_asset(assets, main_asset.asset_id if main_asset else None)
    if detail_asset is not None:
        selected.append(detail_asset)
    return selected[:max_images]


def _select_main_asset(assets: list[Asset]) -> Asset | None:
    for asset in assets:
        if asset.asset_type == AssetType.PRODUCT:
            return asset
    for asset in assets:
        if asset.asset_type != AssetType.WHITE_BG:
            return asset
    return assets[0] if assets else None


def _select_detail_asset(assets: list[Asset], main_asset_id: str | None) -> Asset | None:
    for asset in assets:
        if asset.asset_id == main_asset_id:
            continue
        if asset.asset_type == AssetType.DETAIL:
            return asset
    return None
