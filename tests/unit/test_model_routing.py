from __future__ import annotations

from src.core.config import Settings
from src.providers.image.dashscope_image import DashScopeImageProvider
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.llm.dashscope_text import DashScopeTextProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.ollama_text import OllamaTextProvider
from src.providers.llm.zhipu_text import ZhipuTextProvider
from src.providers.router import build_capability_bindings
from src.providers.vision.dashscope_vision import DashScopeVisionProvider
from src.providers.vision.zhipu_vision import ZhipuVisionProvider
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
        "ECOM_IMAGE_AGENT_TEXT_MODEL",
        "ECOM_IMAGE_AGENT_TEXT_MODEL_ID",
        "ECOM_IMAGE_AGENT_VISION_MODEL",
        "ECOM_IMAGE_AGENT_VISION_MODEL_ID",
        "ECOM_IMAGE_AGENT_IMAGE_MODEL",
        "ECOM_IMAGE_AGENT_IMAGE_MODEL_ID",
        "ECOM_IMAGE_AGENT_IMAGE_ALLOW_MOCK_FALLBACK",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_default_model_selection_uses_dashscope_defaults(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    settings = Settings()

    text_selection = settings.resolve_text_model_selection()
    vision_selection = settings.resolve_vision_model_selection()
    image_selection = settings.resolve_image_model_selection()

    assert text_selection.provider_key == "dashscope"
    assert text_selection.model_id == "qwen-plus"
    assert vision_selection.provider_key == "dashscope"
    assert vision_selection.model_id == "qwen3-vl-flash"
    assert image_selection.provider_key == "dashscope"
    assert image_selection.model_id == "wanx2.1-t2i-turbo"


def test_capability_router_defaults_to_dashscope(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    bindings = build_capability_bindings(Settings())

    assert isinstance(bindings.planning_provider, DashScopeTextProvider)
    assert isinstance(bindings.vision_analysis_provider, DashScopeVisionProvider)
    assert isinstance(bindings.image_generation_provider, DashScopeImageProvider)
    assert bindings.planning_route.alias == "dashscope"
    assert bindings.vision_route.alias == "dashscope"
    assert bindings.image_route.alias == "dashscope"


def test_mock_mode_still_requires_explicit_switch(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    bindings = build_capability_bindings(
        Settings(
            text_provider_mode="mock",
            vision_provider_mode="mock",
            image_provider_mode="mock",
        )
    )

    assert isinstance(bindings.planning_provider, GeminiTextProvider)
    assert bindings.vision_analysis_provider is None
    assert isinstance(bindings.image_generation_provider, GeminiImageProvider)


def test_budget_modes_all_resolve_to_dashscope(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)

    for budget_mode in ("local", "cheap", "balanced", "production"):
        settings = Settings(budget_mode=budget_mode)
        assert settings.resolve_text_provider_route().alias == "dashscope"
        assert settings.resolve_vision_provider_route().alias == "dashscope"
        assert settings.resolve_image_provider_route().alias == "dashscope"
        assert settings.resolve_text_provider_route().mode == "real"
        assert settings.resolve_vision_provider_route().mode == "real"
        assert settings.resolve_image_provider_route().mode == "real"


def test_explicit_ollama_override_still_supported(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    settings = Settings(text_provider="ollama")

    assert settings.resolve_text_provider_route().alias == "ollama"
    assert isinstance(build_capability_bindings(settings).planning_provider, OllamaTextProvider)


def test_explicit_provider_override_wins_over_budget_mode(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    settings = Settings(
        budget_mode="production",
        text_provider="zhipu",
        vision_provider="zhipu",
        image_provider_mode="mock",
    )

    assert settings.resolve_text_provider_route().alias == "zhipu"
    assert settings.resolve_vision_provider_route().alias == "zhipu"
    assert settings.resolve_image_provider_route().alias == "mock"


def test_legacy_providers_remain_constructible(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)

    text_settings = Settings(text_provider="zhipu", text_model="glm-4.7-flash")
    vision_settings = Settings(vision_provider="zhipu", vision_model="glm-4.6v-flash")

    assert isinstance(build_capability_bindings(text_settings).planning_provider, ZhipuTextProvider)
    assert isinstance(build_capability_bindings(vision_settings).vision_analysis_provider, ZhipuVisionProvider)


def test_reload_runtime_clears_workflow_cache(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    build_workflow.cache_clear()
    build_workflow()
    assert build_workflow.cache_info().currsize == 1

    reload_runtime()

    assert build_workflow.cache_info().currsize == 0
