from __future__ import annotations

from src.core.config import Settings
from src.providers.image.gemini_image import GeminiImageProvider
from src.providers.image.routed_image import RoutedImageProvider
<<<<<<< HEAD
from src.providers.image.runapi_gemini31_image import RunApiGemini31ImageProvider
from src.providers.llm.dashscope_text import DashScopeTextProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.ollama_text import OllamaTextProvider
from src.providers.llm.runapi_openai_text import RunApiOpenAITextProvider
=======
from src.providers.llm.dashscope_text import DashScopeTextProvider
from src.providers.llm.gemini_text import GeminiTextProvider
from src.providers.llm.ollama_text import OllamaTextProvider
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
<<<<<<< HEAD
        "ECOM_IMAGE_AGENT_RUNAPI_TEXT_MODEL",
        "ECOM_IMAGE_AGENT_RUNAPI_TEXT_BASE_URL",
        "ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY",
        "ECOM_IMAGE_AGENT_RUNAPI_API_KEY",
=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        "ECOM_IMAGE_AGENT_VISION_MODEL",
        "ECOM_IMAGE_AGENT_VISION_MODEL_ID",
        "ECOM_IMAGE_AGENT_IMAGE_MODEL",
        "ECOM_IMAGE_AGENT_IMAGE_MODEL_ID",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_PROVIDER",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_MODEL",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_ENABLED",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_PREFER_MULTI_IMAGE",
        "ECOM_IMAGE_AGENT_IMAGE_EDIT_MAX_REFERENCE_IMAGES",
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
    assert isinstance(bindings.image_generation_provider, RoutedImageProvider)
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


<<<<<<< HEAD
def test_explicit_runapi_openai_text_provider_is_supported(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    settings = Settings(text_provider="runapi_openai")
    bindings = build_capability_bindings(settings)

    assert settings.resolve_text_provider_route().alias == "runapi_openai"
    assert settings.resolve_text_model_selection().provider_key == "runapi_openai"
    assert settings.resolve_text_model_selection().model_id == "gpt-5-nano"
    assert isinstance(bindings.planning_provider, RunApiOpenAITextProvider)


def test_explicit_runapi_gemini31_image_provider_is_supported(monkeypatch) -> None:
    _clear_provider_envs(monkeypatch)
    settings = Settings(image_provider="runapi_gemini31")
    bindings = build_capability_bindings(settings)

    assert settings.resolve_image_provider_route().alias == "runapi_gemini31"
    assert settings.resolve_image_model_selection().provider_key == "runapi_gemini31"
    assert settings.resolve_image_model_selection().model_id == "gemini-3.1-flash-image-preview"
    assert isinstance(bindings.image_generation_provider, RunApiGemini31ImageProvider)


=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
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
