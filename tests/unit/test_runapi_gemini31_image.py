from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.core.config import Settings
from src.domain.asset import Asset, AssetType
from src.domain.prompt_plan_v2 import PromptShot
from src.providers.image.runapi_gemini31_image import (
    RUNAPI_GEMINI31_MODEL_ID,
    RunApiGemini31ImageProvider,
)


def _build_demo_image(path: Path, *, image_format: str) -> None:
    """生成最小可读测试图片，供 inlineData 请求体拼装使用。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color=(240, 240, 240)).save(path, format=image_format)


def test_runapi_gemini31_provider_builds_generate_content_payload_with_refs(tmp_path: Path) -> None:
    """验证 Gemini 3.1 provider 会按 v2 约定拼装 text、inlineData 和 imageConfig。"""
    main_image = tmp_path / "product.png"
    detail_image = tmp_path / "detail.jpg"
    _build_demo_image(main_image, image_format="PNG")
    _build_demo_image(detail_image, image_format="JPEG")

    settings = Settings(
        image_provider_mode="real",
        image_provider="runapi_gemini31",
        runapi_api_key="runapi-test-key",
        image_model=None,
        image_model_id=None,
    )
    provider = RunApiGemini31ImageProvider(settings)
    shot = PromptShot(
        shot_id="shot-01",
        shot_role="hero",
        render_prompt="高级茶叶主图，产品主体清晰，整体风格统一。",
        title_copy="东方茶礼",
        subtitle_copy="甄选春茶醇香回甘",
        layout_hint="顶部留白，右下弱化文案区",
        aspect_ratio="1:1",
        image_size="2K",
    )
    prompt_text = provider._compose_v2_prompt_text(shot)
    payload = provider._build_request_payload(
        prompt_text=prompt_text,
        reference_assets=[
            Asset(
                asset_id="asset-01",
                filename="product.png",
                local_path=str(main_image),
                asset_type=AssetType.PRODUCT,
                mime_type="image/png",
            ),
            Asset(
                asset_id="asset-02",
                filename="detail.jpg",
                local_path=str(detail_image),
                asset_type=AssetType.DETAIL,
                mime_type="image/jpeg",
            ),
        ],
        aspect_ratio=shot.aspect_ratio,
        image_size=shot.image_size,
    )
    context = provider.resolve_generation_context(
        reference_assets=[
            Asset(asset_id="asset-01", filename="product.png", local_path=str(main_image)),
            Asset(asset_id="asset-02", filename="detail.jpg", local_path=str(detail_image)),
        ]
    )

    assert provider.model_id == RUNAPI_GEMINI31_MODEL_ID
    assert context.generation_mode == "t2i"
    assert context.reference_asset_ids == ["asset-01", "asset-02"]
    assert payload["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert payload["generationConfig"]["imageConfig"] == {
        "aspectRatio": "1:1",
        "imageSize": "2K",
    }

    parts = payload["contents"][0]["parts"]
    assert len(parts) == 3
    assert "东方茶礼" in parts[0]["text"]
    assert "甄选春茶醇香回甘" in parts[0]["text"]
    assert "顶部留白" in parts[0]["text"]
    assert parts[1]["inlineData"]["mimeType"] == "image/png"
    assert parts[2]["inlineData"]["mimeType"] == "image/jpeg"
    assert isinstance(parts[1]["inlineData"]["data"], str)
    assert isinstance(parts[2]["inlineData"]["data"], str)
