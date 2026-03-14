from __future__ import annotations

from pathlib import Path

from src.core.config import Settings
from src.domain.asset import Asset
from src.providers.image.routed_image import RoutedImageProvider
from src.providers.router import build_capability_bindings


def test_dashscope_image_route_uses_image_edit_when_reference_assets_present(tmp_path: Path) -> None:
    settings = Settings(
        image_provider="dashscope",
        image_provider_mode="real",
        dashscope_api_key="test-key",
    )
    bindings = build_capability_bindings(settings)

    assert isinstance(bindings.image_generation_provider, RoutedImageProvider)
    first_asset = tmp_path / "product.png"
    second_asset = tmp_path / "detail.png"
    first_asset.write_bytes(b"product")
    second_asset.write_bytes(b"detail")
    context = bindings.image_generation_provider.resolve_generation_context(
        reference_assets=[
            Asset(asset_id="asset-01", filename="product.png", local_path=str(first_asset)),
            Asset(asset_id="asset-02", filename="detail.png", local_path=str(second_asset)),
        ]
    )

    assert context.generation_mode == "image_edit"
    assert context.reference_asset_ids == ["asset-01", "asset-02"]
    assert context.model_id == settings.resolve_image_edit_model_selection().model_id


def test_dashscope_image_route_uses_t2i_when_reference_assets_are_absent() -> None:
    settings = Settings(
        image_provider="dashscope",
        image_provider_mode="real",
        dashscope_api_key="test-key",
    )
    bindings = build_capability_bindings(settings)

    assert isinstance(bindings.image_generation_provider, RoutedImageProvider)
    context = bindings.image_generation_provider.resolve_generation_context(reference_assets=[])

    assert context.generation_mode == "t2i"
    assert context.reference_asset_ids == []
    assert context.model_id == settings.resolve_image_model_selection().model_id
