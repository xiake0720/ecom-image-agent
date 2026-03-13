from __future__ import annotations

import os

from PIL import Image
import pytest
from pydantic import BaseModel, Field

from src.core.config import Settings
from src.domain.asset import Asset
from src.providers.vision.dashscope_vision import DashScopeVisionProvider


class VisionIdentityPayload(BaseModel):
    dominant_colors: list[str] = Field(default_factory=list)
    must_preserve: list[str] = Field(default_factory=list)


class VisionSmokePayload(BaseModel):
    category: str
    product_form: str
    visual_identity: VisionIdentityPayload


pytestmark = pytest.mark.skipif(
    not os.getenv("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY is not configured for DashScope smoke testing.",
)


def test_dashscope_vision_provider_smoke(tmp_path) -> None:
    image_path = tmp_path / "vision_smoke.png"
    Image.new("RGB", (512, 512), color=(245, 238, 220)).save(image_path)
    settings = Settings(
        vision_provider_mode="real",
        vision_provider="dashscope",
        vision_model="qwen3-vl-flash",
    ).with_streamlit_secrets()
    provider = DashScopeVisionProvider(settings)
    asset = Asset(asset_id="asset-01", filename=image_path.name, local_path=str(image_path), mime_type="image/png")

    result = provider.generate_structured_from_assets(
        (
            "Analyze the uploaded product image and return JSON. "
            "Use category='tea' and product_form='can' if the image is too simple to infer. "
            "visual_identity.must_preserve should contain 1-2 short phrases."
        ),
        VisionSmokePayload,
        assets=[asset],
        system_prompt="You are a DashScope vision smoke test endpoint. Return valid JSON only.",
    )

    assert provider.last_response_status_code == 200
    assert provider.last_response_metadata["provider_name"] == "dashscope"
    assert provider.last_response_metadata["model_id"] == "qwen3-vl-flash"
    assert provider.last_response_metadata["capability"] == "vision"
    assert result.category
    assert result.product_form
