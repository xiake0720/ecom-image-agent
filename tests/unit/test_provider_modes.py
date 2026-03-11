"""provider 模式边界测试。

这些测试只验证 mock / real 模式下的显式报错行为，
不负责真实外部服务联调。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import Settings
from src.domain.asset import Asset
from src.domain.image_prompt_plan import ImagePrompt, ImagePromptPlan
from src.domain.product_analysis import ProductAnalysis
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider


def test_nvidia_provider_requires_api_key_in_real_mode() -> None:
    """真实文本模式下缺失 key 时必须显式报错。"""
    settings = Settings(text_provider_mode="real", nvidia_api_key=None)
    provider = NVIDIATextProvider(settings)

    with pytest.raises(RuntimeError, match="ECOM_IMAGE_AGENT_NVIDIA_API_KEY"):
        provider.generate_structured("test", ProductAnalysis)


def test_runapi_provider_requires_api_key_in_real_mode(tmp_path: Path) -> None:
    """真实图片模式下缺失 key 时必须显式报错。"""
    settings = Settings(image_provider_mode="real", runapi_api_key=None)
    provider = RunApiGeminiImageProvider(settings)
    plan = ImagePromptPlan(prompts=[ImagePrompt(shot_id="shot-01", prompt="tea", output_size="1440x1440")])
    assets = [Asset(asset_id="asset-01", filename="demo.png", local_path=str(tmp_path / "demo.png"))]

    with pytest.raises(RuntimeError, match="ECOM_IMAGE_AGENT_RUNAPI_API_KEY"):
        provider.generate_images(plan, output_dir=tmp_path, reference_assets=assets)
