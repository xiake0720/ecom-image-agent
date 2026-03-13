"""配置来源与敏感信息读取边界测试。"""

from __future__ import annotations

from src.core import config as config_module


def test_streamlit_secrets_used_when_env_missing(monkeypatch) -> None:
    """环境变量缺失时，允许从 Streamlit secrets 读取同名配置。"""
    monkeypatch.delenv("ECOM_IMAGE_AGENT_NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr(
        config_module,
        "_read_streamlit_secrets",
        lambda: {"ECOM_IMAGE_AGENT_NVIDIA_API_KEY": "secret-from-streamlit"},
    )

    settings = config_module.Settings().with_streamlit_secrets()

    assert settings.nvidia_api_key == "secret-from-streamlit"


def test_environment_variable_overrides_streamlit_secrets(monkeypatch) -> None:
    """环境变量优先级高于 Streamlit secrets。"""
    monkeypatch.setenv("ECOM_IMAGE_AGENT_NVIDIA_API_KEY", "secret-from-env")
    monkeypatch.setattr(
        config_module,
        "_read_streamlit_secrets",
        lambda: {"ECOM_IMAGE_AGENT_NVIDIA_API_KEY": "secret-from-streamlit"},
    )

    settings = config_module.Settings().with_streamlit_secrets()

    assert settings.nvidia_api_key == "secret-from-env"


def test_non_prefixed_provider_envs_are_supported(monkeypatch) -> None:
    """DashScope / Zhipu / Ollama 配置允许使用非 ECOM 前缀环境变量。"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-secret")
    monkeypatch.setenv("ZHIPU_BASE_URL", "https://example.zhipu.test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11435")

    settings = config_module.Settings().with_streamlit_secrets()

    assert settings.dashscope_api_key == "dashscope-secret"
    assert settings.zhipu_base_url == "https://example.zhipu.test"
    assert settings.ollama_base_url == "http://localhost:11435"


def test_prompt_build_mode_defaults_follow_budget_mode() -> None:
    assert config_module.Settings(budget_mode="local").resolve_prompt_build_mode() == "batch"
    assert config_module.Settings(budget_mode="cheap").resolve_prompt_build_mode() == "batch"
    assert config_module.Settings(budget_mode="balanced").resolve_prompt_build_mode() == "per_shot"
    assert config_module.Settings(budget_mode="production").resolve_prompt_build_mode() == "per_shot"
