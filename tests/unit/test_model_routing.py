"""模型选择与能力路由测试。"""

from __future__ import annotations

from src.core.config import Settings
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.image.runapi_gemini_image import RunApiGeminiImageProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.nvidia_text import NVIDIATextProvider
from src.providers.llm.ollama_text import OllamaTextProvider
from src.providers.router import build_capability_bindings
from src.workflows.graph import build_workflow, reload_runtime


def _clear_provider_envs(monkeypatch) -> None:
    for name in [
        "ECOM_IMAGE_AGENT_BUDGET_MODE",
        "ECOM_IMAGE_AGENT_TEXT_PROVIDER",
        "ECOM_IMAGE_AGENT_VISION_PROVIDER",
        "ECOM_IMAGE_AGENT_IMAGE_PROVIDER",
        "ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE",
        "ECOM_IMAGE_AGENT_VISION_PROVIDER_MODE",
        "ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE",
        "ECOM_IMAGE_AGENT_NVIDIA_TEXT_MODEL",
        "ECOM_IMAGE_AGENT_NVIDIA_VISION_MODEL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_default_model_selection_uses_qwen3_5(monkeypatch) -> None:
    """默认主链路应解析为 Qwen3.5。"""
    _clear_provider_envs(monkeypatch)
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


def test_text_model_can_switch_to_glm5(monkeypatch) -> None:
    """文本主链路必须保留 GLM-5 开关。"""
    _clear_provider_envs(monkeypatch)
    settings = Settings(
        budget_mode="production",
        text_model_provider="glm5",
        text_model_id=None,
        nvidia_text_model=None,
    )

    text_selection = settings.resolve_text_model_selection()

    assert text_selection.provider_key == "nvidia"
    assert text_selection.model_id == "z-ai/glm5"
    assert text_selection.label == "GLM-5"


def test_capability_router_keeps_mock_and_real_boundaries(monkeypatch) -> None:
    """能力路由层应集中处理 mock / real 选择。"""
    _clear_provider_envs(monkeypatch)
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


def test_budget_mode_local_prefers_ollama_and_mock_routes(monkeypatch) -> None:
    """local 预算模式应优先路由到 ollama + mock + mock。"""
    _clear_provider_envs(monkeypatch)
    settings = Settings(budget_mode="local")

    text_route = settings.resolve_text_provider_route()
    vision_route = settings.resolve_vision_provider_route()
    image_route = settings.resolve_image_provider_route()
    bindings = build_capability_bindings(settings)

    assert text_route.alias == "ollama"
    assert text_route.mode == "real"
    assert vision_route.alias == "mock"
    assert vision_route.mode == "mock"
    assert image_route.alias == "mock"
    assert image_route.mode == "mock"
    assert isinstance(bindings.planning_provider, OllamaTextProvider)
    assert isinstance(bindings.image_generation_provider, GeminiImageProvider)


def test_explicit_provider_override_wins_over_budget_mode(monkeypatch) -> None:
    """显式 provider 配置应覆盖预算模式默认值。"""
    _clear_provider_envs(monkeypatch)
    settings = Settings(
        budget_mode="cheap",
        text_provider="nvidia",
        image_provider="mock",
    )

    assert settings.resolve_text_provider_route().alias == "nvidia"
    assert settings.resolve_image_provider_route().alias == "mock"


def test_explicit_production_budget_keeps_current_main_chain(monkeypatch) -> None:
    """显式 production 预算模式应回到当前主链路默认别名。"""
    _clear_provider_envs(monkeypatch)
    settings = Settings(budget_mode="production")

    assert settings.resolve_text_provider_route().alias == "nvidia"
    assert settings.resolve_text_provider_route().mode == "real"
    assert settings.resolve_vision_provider_route().alias == "nvidia"
    assert settings.resolve_image_provider_route().alias == "runapi"


def test_reload_runtime_clears_workflow_cache(monkeypatch) -> None:
    """重新加载运行时应清空 workflow 缓存。"""
    _clear_provider_envs(monkeypatch)
    build_workflow.cache_clear()
    build_workflow()
    assert build_workflow.cache_info().currsize == 1

    reload_runtime()

    assert build_workflow.cache_info().currsize == 0
