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
from src.providers.image.dashscope_image import DashScopeImageProvider
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.dashscope_text import DashScopeTextProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider
from src.providers.vision.dashscope_vision import DashScopeVisionProvider
from src.providers.vision.nvidia_product_analysis import NVIDIAVisionProductAnalysisProvider


def _clear_sensitive_envs(monkeypatch) -> None:
    for name in [
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_BASE_URL",
        "ZHIPU_API_KEY",
        "ZHIPU_BASE_URL",
        "ECOM_IMAGE_AGENT_TEXT_MODEL",
        "ECOM_IMAGE_AGENT_VISION_MODEL",
        "ECOM_IMAGE_AGENT_IMAGE_MODEL",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_PROVIDER",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_MODEL",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_ENABLED",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_PREFER_MULTI_IMAGE",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_MAX_REFERENCE_IMAGES",
        "ECOM_IMAGE_AGENT_NVIDIA_API_KEY",
        "ECOM_IMAGE_AGENT_NVIDIA_VISION_API_KEY",
        "ECOM_IMAGE_AGENT_RUNAPI_API_KEY",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_nvidia_provider_requires_api_key_in_real_mode(monkeypatch) -> None:
    """真实文本模式下缺失 key 时必须显式报错。"""
    _clear_sensitive_envs(monkeypatch)
    settings = Settings(text_provider_mode="real", text_provider="nvidia", nvidia_api_key=None)
    provider = NVIDIATextProvider(settings)

    with pytest.raises(RuntimeError, match="ECOM_IMAGE_AGENT_NVIDIA_API_KEY"):
        provider.generate_structured("test", ProductAnalysis)


def test_runapi_provider_requires_api_key_in_real_mode(monkeypatch, tmp_path: Path) -> None:
    """真实图片模式下缺失 key 时必须显式报错。"""
    _clear_sensitive_envs(monkeypatch)
    settings = Settings(image_provider_mode="real", image_provider="runapi", runapi_api_key=None)
    provider = RunApiGeminiImageProvider(settings)
    plan = ImagePromptPlan(prompts=[ImagePrompt(shot_id="shot-01", prompt="tea", output_size="1440x1440")])
    assets = [Asset(asset_id="asset-01", filename="demo.png", local_path=str(tmp_path / "demo.png"))]

    with pytest.raises(RuntimeError, match="ECOM_IMAGE_AGENT_RUNAPI_API_KEY"):
        provider.generate_images(plan, output_dir=tmp_path, reference_assets=assets)


def test_nvidia_vision_provider_requires_api_key_in_real_mode(monkeypatch, tmp_path: Path) -> None:
    """真实视觉模式下缺失 key 时必须显式报错。"""
    _clear_sensitive_envs(monkeypatch)
    image_path = tmp_path / "demo.png"
    image_path.write_bytes(b"demo")
    settings = Settings(
        vision_provider_mode="real",
        vision_provider="nvidia",
        nvidia_api_key=None,
        nvidia_vision_api_key=None,
    )
    provider = NVIDIAVisionProductAnalysisProvider(settings)
    assets = [Asset(asset_id="asset-01", filename="demo.png", local_path=str(image_path))]

    with pytest.raises(RuntimeError, match="ECOM_IMAGE_AGENT_NVIDIA_VISION_API_KEY|ECOM_IMAGE_AGENT_NVIDIA_API_KEY"):
        provider.generate_structured_from_assets("test", ProductAnalysis, assets=assets)


def test_dashscope_text_provider_requires_api_key_in_real_mode(monkeypatch) -> None:
    _clear_sensitive_envs(monkeypatch)
    settings = Settings(text_provider_mode="real", text_provider="dashscope", dashscope_api_key=None)
    provider = DashScopeTextProvider(settings)

    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        provider.generate_structured("Return JSON.", ProductAnalysis)


def test_dashscope_vision_provider_requires_api_key_in_real_mode(monkeypatch, tmp_path: Path) -> None:
    _clear_sensitive_envs(monkeypatch)
    image_path = tmp_path / "demo.png"
    image_path.write_bytes(b"demo")
    settings = Settings(vision_provider_mode="real", vision_provider="dashscope", dashscope_api_key=None)
    provider = DashScopeVisionProvider(settings)
    assets = [Asset(asset_id="asset-01", filename="demo.png", local_path=str(image_path))]

    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        provider.generate_structured_from_assets("Return JSON.", ProductAnalysis, assets=assets)


def test_dashscope_image_provider_requires_api_key_in_real_mode(monkeypatch, tmp_path: Path) -> None:
    _clear_sensitive_envs(monkeypatch)
    settings = Settings(image_provider_mode="real", image_provider="dashscope", dashscope_api_key=None)
    provider = DashScopeImageProvider(settings)
    plan = ImagePromptPlan(prompts=[ImagePrompt(shot_id="shot-01", prompt="tea can", output_size="1024x1024")])

    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        provider.generate_images(plan, output_dir=tmp_path)
