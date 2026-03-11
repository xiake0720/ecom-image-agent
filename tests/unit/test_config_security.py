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
