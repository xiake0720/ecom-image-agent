from __future__ import annotations

from src.core import config as config_module


def test_settings_defaults_match_v2_production_baseline(monkeypatch) -> None:
    monkeypatch.delenv("ECOM_IMAGE_AGENT_RUNAPI_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("ECOM_IMAGE_AGENT_RUNAPI_TEXT_MODEL", raising=False)
    settings = config_module.Settings()

    assert settings.default_platform == "tmall"
    assert settings.default_shot_count == 8
    assert settings.default_image_aspect_ratio == "1:1"
    assert settings.default_image_size == "2K"
    assert settings.runapi_text_model == "gpt-5-nano"
    assert settings.runapi_image_model == "gemini-3.1-flash-image-preview"
    assert settings.enable_overlay_fallback is True


def test_streamlit_secrets_fill_missing_runapi_values(monkeypatch) -> None:
    monkeypatch.delenv("ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY", raising=False)
    monkeypatch.delenv("ECOM_IMAGE_AGENT_RUNAPI_API_KEY", raising=False)
    monkeypatch.setattr(
        config_module,
        "_read_streamlit_secrets",
        lambda: {
            "ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY": "text-secret",
            "ECOM_IMAGE_AGENT_RUNAPI_API_KEY": "shared-secret",
        },
    )

    settings = config_module.Settings().with_streamlit_secrets()

    assert settings.runapi_text_api_key == "text-secret"
    assert settings.runapi_api_key == "shared-secret"


def test_environment_value_overrides_streamlit_secret(monkeypatch) -> None:
    monkeypatch.setenv("ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY", "env-text-secret")
    monkeypatch.setattr(
        config_module,
        "_read_streamlit_secrets",
        lambda: {"ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY": "secret-from-streamlit"},
    )

    settings = config_module.Settings().with_streamlit_secrets()

    assert settings.runapi_text_api_key == "env-text-secret"


def test_legacy_provider_aliases_are_ignored_in_v2(monkeypatch) -> None:
    monkeypatch.setenv("ECOM_IMAGE_AGENT_TEXT_PROVIDER", "dashscope")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_IMAGE_PROVIDER", "dashscope")

    settings = config_module.Settings()

    assert settings.resolve_text_provider_route().alias == "runapi_openai"
    assert settings.resolve_image_provider_route().alias == "runapi_gemini31"
