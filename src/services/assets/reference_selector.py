from __future__ import annotations

from dataclasses import dataclass

from src.domain.asset import Asset, AssetType


@dataclass(frozen=True)
class ReferenceSelection:
    main_asset: Asset | None
    detail_asset: Asset | None
    selected_assets: list[Asset]
    selected_asset_ids: list[str]
    selected_main_asset_id: str | None
    selected_detail_asset_id: str | None
    selection_reason: str


def select_reference_assets(assets: list[Asset], *, max_images: int) -> list[Asset]:
    return select_reference_bundle(assets, max_images=max_images).selected_assets


def select_reference_bundle(assets: list[Asset], *, max_images: int) -> ReferenceSelection:
    if max_images <= 0 or not assets:
        return ReferenceSelection(
            main_asset=None,
            detail_asset=None,
            selected_assets=[],
            selected_asset_ids=[],
            selected_main_asset_id=None,
            selected_detail_asset_id=None,
            selection_reason="no_assets_or_max_images_zero",
        )

    main_asset, main_reason = _select_main_asset(assets)
    selected_assets: list[Asset] = []
    if main_asset is not None:
        selected_assets.append(main_asset)

    detail_asset = None
    detail_reason = "detail_not_selected"
    if max_images > 1:
        detail_asset, detail_reason = _select_detail_asset(assets, main_asset.asset_id if main_asset else None)
        if detail_asset is not None:
            selected_assets.append(detail_asset)

    if len(selected_assets) < max_images:
        existing_ids = {asset.asset_id for asset in selected_assets}
        for asset in _rank_remaining_assets(assets, existing_ids=existing_ids):
            selected_assets.append(asset)
            existing_ids.add(asset.asset_id)
            if len(selected_assets) >= max_images:
                break

    selected_asset_ids = [asset.asset_id for asset in selected_assets[:max_images]]
    selected_assets = selected_assets[:max_images]
    return ReferenceSelection(
        main_asset=main_asset,
        detail_asset=detail_asset if detail_asset in selected_assets else None,
        selected_assets=selected_assets,
        selected_asset_ids=selected_asset_ids,
        selected_main_asset_id=main_asset.asset_id if main_asset is not None else None,
        selected_detail_asset_id=detail_asset.asset_id if detail_asset is not None and detail_asset in selected_assets else None,
        selection_reason=f"main={main_reason}; detail={detail_reason}; max_images={max_images}",
    )


def _select_main_asset(assets: list[Asset]) -> tuple[Asset | None, str]:
    packshot_candidates = [asset for asset in assets if _looks_like_main_packshot(asset)]
    if packshot_candidates:
        ranked = sorted(packshot_candidates, key=_main_sort_key)
        return ranked[0], "packshot_complete_front_or_three_quarter"

    product_candidates = [asset for asset in assets if asset.asset_type == AssetType.PRODUCT]
    if product_candidates:
        ranked = sorted(product_candidates, key=_main_sort_key)
        return ranked[0], "product_type_priority"

    complete_non_white = [asset for asset in assets if asset.asset_type != AssetType.WHITE_BG and _looks_subject_complete(asset)]
    if complete_non_white:
        ranked = sorted(complete_non_white, key=_main_sort_key)
        return ranked[0], "non_white_bg_subject_complete"

    non_white = [asset for asset in assets if asset.asset_type != AssetType.WHITE_BG]
    if non_white:
        ranked = sorted(non_white, key=_main_sort_key)
        return ranked[0], "non_white_bg_fallback"

    return assets[0] if assets else None, "first_asset_fallback"


def _select_detail_asset(assets: list[Asset], main_asset_id: str | None) -> tuple[Asset | None, str]:
    detail_type_candidates = [
        asset
        for asset in assets
        if asset.asset_id != main_asset_id and asset.asset_type == AssetType.DETAIL
    ]
    if detail_type_candidates:
        ranked = sorted(detail_type_candidates, key=_detail_sort_key)
        return ranked[0], "detail_type_priority"

    detail_like_candidates = [
        asset
        for asset in assets
        if asset.asset_id != main_asset_id and _looks_like_detail_reference(asset)
    ]
    if detail_like_candidates:
        ranked = sorted(detail_like_candidates, key=_detail_sort_key)
        return ranked[0], "detail_keyword_priority"

    return None, "detail_not_found"


def _rank_remaining_assets(assets: list[Asset], *, existing_ids: set[str]) -> list[Asset]:
    candidates = [asset for asset in assets if asset.asset_id not in existing_ids]
    return sorted(candidates, key=_remaining_sort_key)


def _main_sort_key(asset: Asset) -> tuple[int, int, int, int, str]:
    return (
        0 if _looks_like_main_packshot(asset) else 1,
        0 if asset.asset_type == AssetType.PRODUCT else 1,
        0 if asset.asset_type != AssetType.WHITE_BG else 1,
        0 if _looks_subject_complete(asset) else 1,
        asset.asset_id,
    )


def _detail_sort_key(asset: Asset) -> tuple[int, int, str]:
    return (
        0 if asset.asset_type == AssetType.DETAIL else 1,
        0 if _looks_like_detail_reference(asset) else 1,
        asset.asset_id,
    )


def _remaining_sort_key(asset: Asset) -> tuple[int, int, int, str]:
    return (
        0 if asset.asset_type == AssetType.PRODUCT else 1,
        0 if asset.asset_type == AssetType.DETAIL else 1,
        0 if asset.asset_type != AssetType.WHITE_BG else 1,
        asset.asset_id,
    )


def _looks_like_main_packshot(asset: Asset) -> bool:
    text = _asset_text(asset)
    if _looks_like_detail_reference(asset):
        return False
    packshot_keywords = (
        "packshot",
        "hero",
        "main",
        "front",
        "3/4",
        "three-quarter",
        "three_quarter",
        "full",
        "primary",
    )
    if asset.asset_type == AssetType.PRODUCT and _looks_subject_complete(asset):
        return True
    return _contains_any(text, packshot_keywords) and _looks_subject_complete(asset)


def _looks_like_detail_reference(asset: Asset) -> bool:
    text = _asset_text(asset)
    detail_keywords = (
        "detail",
        "label",
        "material",
        "texture",
        "craft",
        "side",
        "structure",
        "close",
        "closeup",
        "macro",
        "logo",
        "lid",
        "cap",
        "edge",
    )
    return asset.asset_type == AssetType.DETAIL or _contains_any(text, detail_keywords)


def _looks_subject_complete(asset: Asset) -> bool:
    text = _asset_text(asset)
    negative_keywords = ("detail", "closeup", "macro", "crop", "label", "texture", "partial")
    if _contains_any(text, negative_keywords):
        return False
    return True


def _asset_text(asset: Asset) -> str:
    tags_text = " ".join(asset.tags or [])
    return f"{asset.filename} {tags_text}".strip().lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)
