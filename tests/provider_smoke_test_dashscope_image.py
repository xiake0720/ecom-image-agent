from __future__ import annotations

import os

import pytest

from src.core.config import Settings
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.providers.image.dashscope_image import DashScopeImageProvider


pytestmark = pytest.mark.skipif(
    not os.getenv("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY is not configured for DashScope smoke testing.",
)


def test_dashscope_image_provider_smoke(tmp_path) -> None:
    settings = Settings(
        image_provider_mode="real",
        image_provider="dashscope",
        image_model="wanx2.1-t2i-turbo",
    ).with_streamlit_secrets()
    provider = DashScopeImageProvider(settings)
    plan = ImagePromptPlan(
        prompts=[
            ImagePrompt(
                shot_id="shot-01",
                shot_type="hero",
                prompt="Premium tea can on a clean studio background, soft light, realistic product photography.",
                output_size="1024x1024",
            )
        ]
    )

    result = provider.generate_images(plan, output_dir=tmp_path)

    assert provider.last_response_metadata["provider_name"] == "dashscope"
    assert provider.last_response_metadata["model_id"] == "wanx2.1-t2i-turbo"
    assert provider.last_response_metadata["capability"] == "image"
    assert len(result.images) == 1
    assert os.path.exists(result.images[0].image_path)
