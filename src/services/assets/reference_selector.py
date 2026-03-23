"""参考图选择器。

文件位置：
- `src/services/assets/reference_selector.py`

职责：
- 从上传素材中挑选主参考图和附加参考图
- 优先保证白底包装图作为主参考，详情图作为补充参考
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.asset import Asset, AssetType


@dataclass(frozen=True)
class ReferenceSelection:
    """参考图选择结果。"""

    main_asset: Asset | None
    detail_asset: Asset | None
    selected_assets: list[Asset]
    selected_asset_ids: list[str]
    selected_main_asset_id: str | None
    selected_detail_asset_id: str | None
    selection_reason: str


def select_reference_bundle(assets: list[Asset], *, max_images: int = 2) -> ReferenceSelection:
    """优先返回白底主图，再补充一张详情图。"""

    if not assets or max_images <= 0:
        return ReferenceSelection(None, None, [], [], None, None, "no_assets")

    white_bg_assets = [asset for asset in assets if asset.asset_type in {AssetType.WHITE_BG, AssetType.PRODUCT}]
    detail_assets = [asset for asset in assets if asset.asset_type == AssetType.DETAIL]
    main_asset = white_bg_assets[0] if white_bg_assets else assets[0]
    detail_asset = detail_assets[0] if detail_assets else None

    selected_assets = [main_asset]
    if detail_asset is not None and detail_asset.asset_id != main_asset.asset_id and len(selected_assets) < max_images:
        selected_assets.append(detail_asset)
    if len(selected_assets) < max_images:
        for asset in assets:
            if asset.asset_id in {item.asset_id for item in selected_assets}:
                continue
            selected_assets.append(asset)
            if len(selected_assets) >= max_images:
                break

    return ReferenceSelection(
        main_asset=main_asset,
        detail_asset=detail_asset if detail_asset in selected_assets else None,
        selected_assets=selected_assets,
        selected_asset_ids=[asset.asset_id for asset in selected_assets],
        selected_main_asset_id=main_asset.asset_id,
        selected_detail_asset_id=detail_asset.asset_id if detail_asset in selected_assets else None,
        selection_reason="prefer_white_bg_then_detail",
    )
