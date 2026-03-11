"""全局配置模块。

该模块位于 `src/core/`，负责集中管理运行时配置，并统一封装：
- 系统环境变量读取
- Streamlit `st.secrets` 读取
- 本地目录初始化

当前仓库仍然保持 Streamlit 单体应用形态。provider、workflow、UI 和 service
都只能通过这里暴露的配置对象读取环境相关参数，避免在业务代码中散落
`os.getenv()` 或硬编码敏感信息。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目运行时配置。

    关键约束：
    - 敏感配置只允许来自环境变量或 Streamlit secrets。
    - provider 运行模式、模型名、Base URL、timeout 都统一从这里读取。
    - provider 层负责在配置缺失时显式报错；本模块只负责集中加载配置。
    """

    app_name: str = "ecom-image-agent"
    env: str = "dev"
    enable_mock_providers: bool = True
    enable_ocr_qc: bool = False
    text_provider_mode: str = "mock"
    image_provider_mode: str = "mock"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_text_model: str = "z-ai/glm5"
    runapi_api_key: str | None = None
    runapi_image_base_url: str = "https://runapi.co"
    runapi_image_model: str = "gemini-2.5-flash-image"
    provider_timeout_seconds: int = 120
    default_font_path: Path = Path("assets/fonts/NotoSansSC-Regular.otf")
    outputs_dir: Path = Path("outputs")
    tasks_dir: Path = Path("outputs/tasks")
    previews_dir: Path = Path("outputs/previews")
    exports_dir: Path = Path("outputs/exports")
    assets_dir: Path = Path("assets")

    model_config = SettingsConfigDict(
        env_prefix="ECOM_IMAGE_AGENT_",
        extra="ignore",
    )

    @classmethod
    def env_name_for(cls, field_name: str) -> str:
        """返回字段对应的完整环境变量名。"""
        return f"ECOM_IMAGE_AGENT_{field_name.upper()}"

    def with_streamlit_secrets(self) -> "Settings":
        """使用 Streamlit secrets 为缺失配置做兜底。

        优先级保持为：
        1. 系统环境变量（包含本地 `.env` 预加载后的环境变量）
        2. `st.secrets`
        3. 若 provider 需要但仍缺失，则在 provider 层显式报错
        """
        secrets = _read_streamlit_secrets()
        if not secrets:
            return self

        overrides: dict[str, Any] = {}
        for field_name in type(self).model_fields:
            if field_name in self.model_fields_set:
                continue
            secret_name = self.env_name_for(field_name)
            secret_value = secrets.get(secret_name)
            if secret_value in (None, ""):
                continue
            overrides[field_name] = secret_value

        if not overrides:
            return self

        merged = self.model_dump(mode="python")
        merged.update(overrides)
        return self.__class__.model_validate(merged)

    def ensure_directories(self) -> None:
        """确保本地运行所需目录存在。"""
        for path in (self.outputs_dir, self.tasks_dir, self.previews_dir, self.exports_dir, self.assets_dir):
            path.mkdir(parents=True, exist_ok=True)


def _read_streamlit_secrets() -> dict[str, Any]:
    """读取 Streamlit secrets。

    非 Streamlit 运行环境下返回空字典，避免把 `streamlit` 依赖扩散到 provider、
    workflow 或 service 层。
    """
    try:
        import streamlit as st
    except Exception:
        return {}

    try:
        secrets = st.secrets
        if hasattr(secrets, "to_dict"):
            return dict(secrets.to_dict())
        return dict(secrets)
    except Exception:
        return {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回单例化配置对象。"""
    # 本地 `.env` 只作为开发期环境变量预加载，且不会覆盖系统环境变量。
    load_dotenv(override=False)
    settings = Settings().with_streamlit_secrets()
    settings.ensure_directories()
    return settings
