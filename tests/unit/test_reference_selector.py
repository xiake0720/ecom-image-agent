from __future__ import annotations

from src.domain.asset import Asset, AssetType
from src.services.assets.reference_selector import select_reference_bundle


def test_reference_selector_prefers_white_bg_then_detail() -> None:
    assets = [
        Asset(asset_id="asset-01", filename="hero.png", local_path="hero.png", asset_type=AssetType.WHITE_BG),
        Asset(asset_id="asset-02", filename="detail.png", local_path="detail.png", asset_type=AssetType.DETAIL),
        Asset(asset_id="asset-03", filename="other.png", local_path="other.png", asset_type=AssetType.OTHER),
    ]

    selection = select_reference_bundle(assets, max_images=2)

    assert selection.selected_asset_ids == ["asset-01", "asset-02"]
    assert selection.selected_main_asset_id == "asset-01"
    assert selection.selected_detail_asset_id == "asset-02"
    assert selection.selection_reason == "prefer_white_bg_then_detail"
