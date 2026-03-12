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

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class ResolvedModelSelection:
    """解析后的模型选择结果。"""

    capability: str
    provider_key: str
    model_id: str
    label: str
    source: str


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
    vision_provider_mode: str = "mock"
    image_provider_mode: str = "mock"
    text_model_provider: str = "qwen"
    vision_model_provider: str = "qwen"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    text_model_id: str | None = None
    vision_model_id: str | None = None
    qwen_model_id: str = "qwen/qwen3.5-122b-a10b"
    glm5_model_id: str = "z-ai/glm5"
    nvidia_text_model: str | None = None
    nvidia_vision_api_key: str | None = None
    nvidia_vision_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_vision_model: str | None = None
    runapi_api_key: str | None = None
    runapi_image_base_url: str = "https://runapi.co"
    runapi_image_model: str = "gemini-2.5-flash-image"
    provider_timeout_seconds: int = 120
    log_level: str = "INFO"
    enable_file_log: bool = True
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

    def build_debug_summary(self) -> dict[str, str]:
        """返回适合 UI 调试区展示的关键运行配置摘要。"""
        text_selection = self.resolve_text_model_selection()
        vision_selection = self.resolve_vision_model_selection()
        return {
            "text_provider_mode": self.text_provider_mode,
            "vision_provider_mode": self.vision_provider_mode,
            "image_provider_mode": self.image_provider_mode,
            "text_model_provider": text_selection.provider_key,
            "vision_model_provider": vision_selection.provider_key,
            "text_model_label": text_selection.label,
            "vision_model_label": vision_selection.label,
            "text_model_source": text_selection.source,
            "vision_model_source": vision_selection.source,
            "log_level": self.log_level,
            "enable_file_log": "true" if self.enable_file_log else "false",
            "proxy_enabled": "true" if self.is_proxy_enabled() else "false",
            "nvidia_text_model": text_selection.model_id,
            "nvidia_vision_model": vision_selection.model_id,
            "runapi_image_model": self.runapi_image_model,
            "outputs_dir": str(self.outputs_dir),
            "tasks_dir": str(self.tasks_dir),
        }

    def resolve_text_model_selection(self) -> ResolvedModelSelection:
        """解析当前结构化规划能力实际使用的模型。"""
        provider_key = (self.text_model_provider or "qwen").strip().lower()
        if self.text_model_id:
            return ResolvedModelSelection(
                capability="planning",
                provider_key=provider_key or "custom",
                model_id=self.text_model_id,
                label=self._label_for_model(provider_key, self.text_model_id),
                source="ECOM_IMAGE_AGENT_TEXT_MODEL_ID",
            )
        if self.nvidia_text_model:
            return ResolvedModelSelection(
                capability="planning",
                provider_key=provider_key or "legacy",
                model_id=self.nvidia_text_model,
                label=self._label_for_model(provider_key, self.nvidia_text_model),
                source="ECOM_IMAGE_AGENT_NVIDIA_TEXT_MODEL",
            )
        if provider_key == "qwen":
            return ResolvedModelSelection(
                capability="planning",
                provider_key="qwen",
                model_id=self.qwen_model_id,
                label="Qwen3.5",
                source="ECOM_IMAGE_AGENT_TEXT_MODEL_PROVIDER",
            )
        if provider_key == "glm5":
            return ResolvedModelSelection(
                capability="planning",
                provider_key="glm5",
                model_id=self.glm5_model_id,
                label="GLM-5",
                source="ECOM_IMAGE_AGENT_TEXT_MODEL_PROVIDER",
            )
        raise RuntimeError(
            "不支持的文本模型开关："
            f"{provider_key}。当前仅支持 qwen 或 glm5，"
            "如需自定义模型，请显式设置 ECOM_IMAGE_AGENT_TEXT_MODEL_ID。"
        )

    def resolve_vision_model_selection(self) -> ResolvedModelSelection:
        """解析当前视觉分析能力实际使用的模型。"""
        provider_key = (self.vision_model_provider or "qwen").strip().lower()
        if self.vision_model_id:
            return ResolvedModelSelection(
                capability="vision",
                provider_key=provider_key or "custom",
                model_id=self.vision_model_id,
                label=self._label_for_model(provider_key, self.vision_model_id),
                source="ECOM_IMAGE_AGENT_VISION_MODEL_ID",
            )
        if self.nvidia_vision_model:
            return ResolvedModelSelection(
                capability="vision",
                provider_key=provider_key or "legacy",
                model_id=self.nvidia_vision_model,
                label=self._label_for_model(provider_key, self.nvidia_vision_model),
                source="ECOM_IMAGE_AGENT_NVIDIA_VISION_MODEL",
            )
        if provider_key == "qwen":
            return ResolvedModelSelection(
                capability="vision",
                provider_key="qwen",
                model_id=self.qwen_model_id,
                label="Qwen3.5",
                source="ECOM_IMAGE_AGENT_VISION_MODEL_PROVIDER",
            )
        raise RuntimeError(
            "不支持的视觉模型开关："
            f"{provider_key}。当前默认视觉链路仅支持 qwen，"
            "如需自定义视觉模型，请显式设置 ECOM_IMAGE_AGENT_VISION_MODEL_ID。"
        )

    def _label_for_model(self, provider_key: str, model_id: str) -> str:
        """根据 provider 开关和模型 ID 生成可读标签。"""
        normalized = (provider_key or "").strip().lower()
        lowered = model_id.lower()
        if "glm5" in lowered:
            return "GLM-5"
        if "qwen" in lowered:
            return "Qwen3.5"
        if normalized == "glm5":
            return "GLM-5"
        if normalized == "qwen":
            return "Qwen3.5"
        return model_id

    def is_proxy_enabled(self) -> bool:
        """返回当前进程是否设置了常见环境变量代理。"""
        proxy_names = (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        )
        return any(os.getenv(name) for name in proxy_names)


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
