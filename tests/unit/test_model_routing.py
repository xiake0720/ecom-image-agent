"""模型选择与能力路由测试。"""

from __future__ import annotations

from src.core.config import Settings
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider
from src.providers.router import build_capability_bindings


def test_default_model_selection_uses_qwen3_5() -> None:
    """默认主链路应解析为 Qwen3.5。"""
    settings = Settings(
        text_provider_mode="mock",
        vision_provider_mode="mock",
        image_provider_mode="mock",
        text_model_provider="qwen",
        vision_model_provider="qwen",
        text_model_id=None,
        vision_model_id=None,
        nvidia_text_model=None,
        nvidia_vision_model=None,
    )

    text_selection = settings.resolve_text_model_selection()
    vision_selection = settings.resolve_vision_model_selection()

    assert text_selection.provider_key == "qwen"
    assert text_selection.model_id == "qwen/qwen3.5-122b-a10b"
    assert text_selection.label == "Qwen3.5"
    assert vision_selection.provider_key == "qwen"
    assert vision_selection.model_id == "qwen/qwen3.5-122b-a10b"


def test_text_model_can_switch_to_glm5() -> None:
    """文本主链路必须保留 GLM-5 开关。"""
    settings = Settings(
        text_model_provider="glm5",
        text_model_id=None,
        nvidia_text_model=None,
    )

    text_selection = settings.resolve_text_model_selection()

    assert text_selection.provider_key == "glm5"
    assert text_selection.model_id == "z-ai/glm5"
    assert text_selection.label == "GLM-5"


def test_capability_router_keeps_mock_and_real_boundaries() -> None:
    """能力路由层应集中处理 mock / real 选择。"""
    mock_bindings = build_capability_bindings(
        Settings(
            text_provider_mode="mock",
            vision_provider_mode="mock",
            image_provider_mode="mock",
            text_model_provider="qwen",
            vision_model_provider="qwen",
            text_model_id=None,
            vision_model_id=None,
            nvidia_text_model=None,
            nvidia_vision_model=None,
        )
    )
    assert isinstance(mock_bindings.planning_provider, GeminiTextProvider)
    assert mock_bindings.vision_analysis_provider is None
    assert isinstance(mock_bindings.image_generation_provider, GeminiImageProvider)

    real_bindings = build_capability_bindings(
        Settings(
            text_provider_mode="real",
            vision_provider_mode="real",
            image_provider_mode="real",
            text_model_provider="qwen",
            vision_model_provider="qwen",
            text_model_id=None,
            vision_model_id=None,
            nvidia_text_model=None,
            nvidia_vision_model=None,
            nvidia_api_key="demo-key",
            nvidia_vision_api_key="demo-key",
            runapi_api_key="demo-key",
        )
    )
    assert isinstance(real_bindings.planning_provider, NVIDIATextProvider)
    assert isinstance(real_bindings.image_generation_provider, RunApiGeminiImageProvider)
    assert real_bindings.vision_provider_name == "NVIDIAVisionProductAnalysisProvider"
