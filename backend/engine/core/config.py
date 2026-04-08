"""项目运行配置。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class ResolvedModelSelection:
    """解析后的模型选择结果。"""

    capability: str
    provider_key: str
    model_id: str
    label: str
    source: str


@dataclass(frozen=True)
class ResolvedProviderRoute:
    """解析后的 provider 路由结果。"""

    capability: str
    alias: str
    mode: str
    label: str
    source: str


class Settings(BaseSettings):
    """项目运行时配置。"""

    app_name: str = "ecom-image-agent"
    env: str = "dev"
    enable_mock_providers: bool = True
    enable_node_cache: bool = True
    enable_file_log: bool = True
    log_level: str = "INFO"
    provider_timeout_seconds: int = 600

    default_platform: str = "tmall"
    default_shot_count: int = 8
    default_image_aspect_ratio: str = "1:1"
    default_image_size: str = "2K"
    enable_overlay_fallback: bool = True

    text_provider_mode: str = "real"
    image_provider_mode: str = "real"
    text_provider: str = "runapi_openai"
    image_provider: str = "banana2"

    runapi_api_key: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_RUNAPI_API_KEY")
    runapi_text_api_key: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY")
    runapi_text_base_url: str = Field(default="https://runapi.co/v1", validation_alias="ECOM_IMAGE_AGENT_RUNAPI_TEXT_BASE_URL")
    runapi_text_model: str = Field(default="gpt-5-nano", validation_alias="ECOM_IMAGE_AGENT_RUNAPI_TEXT_MODEL")
    runapi_image_base_url: str = Field(default="https://runapi.co", validation_alias="ECOM_IMAGE_AGENT_RUNAPI_IMAGE_BASE_URL")
    runapi_image_model: str = Field(
        default="gemini-3.1-flash-image-preview",
        validation_alias="ECOM_IMAGE_AGENT_RUNAPI_IMAGE_MODEL",
    )
    google_api_key: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_GOOGLE_API_KEY")
    google_image_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        validation_alias="ECOM_IMAGE_AGENT_GOOGLE_IMAGE_BASE_URL",
    )
    banana2_model: str = Field(
        default="gemini-3.1-flash-image-preview",
        validation_alias="ECOM_IMAGE_AGENT_BANANA2_MODEL",
    )

    default_font_path: Path = Path("assets/fonts/NotoSansSC-Regular.otf")
    outputs_dir: Path = Path("outputs")
    tasks_dir: Path = Path("outputs/tasks")
    cache_dir: Path = Path("outputs/cache")
    exports_dir: Path = Path("outputs/exports")
    assets_dir: Path = Path("assets")

    model_config = SettingsConfigDict(env_prefix="ECOM_IMAGE_AGENT_", extra="ignore")

    @classmethod
    def env_name_for(cls, field_name: str) -> str:
        """返回字段对应的环境变量名。"""

        field = cls.model_fields.get(field_name)
        if field is not None and isinstance(field.validation_alias, str):
            return field.validation_alias
        return f"ECOM_IMAGE_AGENT_{field_name.upper()}"

    def with_streamlit_secrets(self) -> "Settings":
        """用 Streamlit secrets 补足缺省配置。"""

        secrets = _read_streamlit_secrets()
        if not secrets:
            return self

        overrides: dict[str, Any] = {}
        for field_name in type(self).model_fields:
            current_value = getattr(self, field_name)
            field = type(self).model_fields[field_name]
            default_value = field.default
            if current_value not in (None, "") and current_value != default_value:
                continue
            secret_name = self.env_name_for(field_name)
            secret_value = secrets.get(secret_name)
            if secret_value in (None, ""):
                continue
            overrides[secret_name] = secret_value

        if not overrides:
            return self

        merged = self.model_dump(mode="python", by_alias=True)
        merged.update(overrides)
        return self.__class__.model_validate(merged)

    def ensure_directories(self) -> None:
        """确保本地运行所需目录存在。"""

        for path in (self.outputs_dir, self.tasks_dir, self.cache_dir, self.exports_dir, self.assets_dir):
            path.mkdir(parents=True, exist_ok=True)

    def build_debug_summary(self) -> dict[str, str]:
        """返回精简后的运行配置摘要。"""

        return {
            "text_provider": self.resolve_text_provider_route().alias,
            "text_model": self.resolve_text_model_selection().model_id,
            "image_provider": self.resolve_image_provider_route().alias,
            "image_model": self.resolve_image_model_selection().model_id,
            "platform": self.default_platform,
            "shot_count": str(self.default_shot_count),
            "aspect_ratio": self.default_image_aspect_ratio,
            "image_size": self.default_image_size,
            "overlay_fallback": "true" if self.enable_overlay_fallback else "false",
        }

    def resolve_text_provider_route(self) -> ResolvedProviderRoute:
        """解析文本 provider 路由。"""

        mode = self._normalize_mode(self.text_provider_mode)
        alias = "mock" if mode != "real" else self._normalize_provider_alias(
            self.text_provider,
            capability="planning",
            allowed={"runapi_openai"},
        )
        return ResolvedProviderRoute(
            capability="planning",
            alias=alias,
            mode=mode,
            label="Mock Local" if alias == "mock" else alias,
            source=self.env_name_for("text_provider") if alias != "mock" else self.env_name_for("text_provider_mode"),
        )

    def resolve_image_provider_route(self) -> ResolvedProviderRoute:
        """解析图片 provider 路由。"""

        mode = self._normalize_mode(self.image_provider_mode)
        alias = "mock" if mode != "real" else self._normalize_provider_alias(
            self.image_provider,
            capability="image",
            allowed={"banana2", "runapi_gemini31"},
        )
        return ResolvedProviderRoute(
            capability="image",
            alias=alias,
            mode=mode,
            label="Mock Local" if alias == "mock" else alias,
            source=self.env_name_for("image_provider") if alias != "mock" else self.env_name_for("image_provider_mode"),
        )

    def resolve_text_model_selection(self) -> ResolvedModelSelection:
        """解析文本模型。"""

        route = self.resolve_text_provider_route()
        if route.alias == "mock":
            return ResolvedModelSelection("planning", "mock", "mock-local", "Mock Local", route.source)
        model_id = self.runapi_text_model
        return ResolvedModelSelection("planning", route.alias, model_id, self._label_for_model(model_id), "fixed_v2_model")

    def resolve_image_model_selection(self) -> ResolvedModelSelection:
        """解析图片模型。"""

        route = self.resolve_image_provider_route()
        if route.alias == "mock":
            return ResolvedModelSelection("image", "mock", "mock-local", "Mock Local", route.source)
        if route.alias == "banana2":
            model_id = self.banana2_model
        else:
            model_id = self.runapi_image_model
        return ResolvedModelSelection("image", route.alias, model_id, self._label_for_model(model_id), "fixed_v2_model")

    def resolve_output_dimensions(self, *, aspect_ratio: str | None = None, image_size: str | None = None) -> tuple[int, int]:
        """把比例和分辨率映射成像素尺寸。"""

        ratio = str(aspect_ratio or self.default_image_aspect_ratio).strip()
        size = str(image_size or self.default_image_size).strip().upper()
        if size != "2K":
            raise RuntimeError(f"Unsupported image_size: {size}")
        size_map = {
            "1:1": (2048, 2048),
            "3:4": (1536, 2048),
            "4:3": (2048, 1536),
            "16:9": (2048, 1152),
            "9:16": (1152, 2048),
            "1:3": (1080, 3240),
        }
        if ratio not in size_map:
            raise RuntimeError(f"Unsupported aspect_ratio: {ratio}")
        return size_map[ratio]

    def resolve_project_font_candidates(self) -> tuple[Path, ...]:
        """返回项目内优先尝试的中文字体候选。"""

        font_dir = self.assets_dir / "fonts"
        candidates = [
            self.default_font_path,
            font_dir / "NotoSansSC-Regular.otf",
            font_dir / "NotoSansSC-Medium.otf",
            font_dir / "SourceHanSansSC-Regular.otf",
            font_dir / "AlibabaPuHuiTi-3-55-Regular.ttf",
        ]
        return tuple(dict.fromkeys(candidates))

    def resolve_system_chinese_font_candidates(self) -> tuple[Path, ...]:
        """返回系统中文字体候选。"""

        if os.name == "nt":
            fonts_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            return (
                fonts_dir / "msyh.ttc",
                fonts_dir / "msyhbd.ttc",
                fonts_dir / "simhei.ttf",
                fonts_dir / "simsun.ttc",
            )
        if sys.platform == "darwin":
            return (
                Path("/System/Library/Fonts/PingFang.ttc"),
                Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
            )
        return (
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        )

    def _normalize_mode(self, value: str) -> str:
        mode = str(value or "mock").strip().lower()
        if mode not in {"mock", "real"}:
            raise RuntimeError(f"Unsupported provider mode: {mode}")
        return mode

    def _normalize_provider_alias(self, value: str, *, capability: str, allowed: set[str]) -> str:
        """规范化 provider alias，避免无效值静默生效。"""

        normalized = str(value or "").strip().lower()
        if not normalized:
            return "runapi_openai" if capability == "planning" else "banana2"
        if normalized not in allowed:
            return "runapi_openai" if capability == "planning" else "banana2"
        return normalized

    def _label_for_model(self, model_id: str) -> str:
        normalized = str(model_id or "").strip().lower()
        if "gpt-5-nano" in normalized:
            return "GPT-5-Nano"
        if "gemini-3.1-flash-image-preview" in normalized:
            return "Google Official / Gemini 3.1 Flash Image Preview"
        return model_id


def _read_streamlit_secrets() -> dict[str, Any]:
    """读取 Streamlit secrets。"""

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

    load_dotenv(override=False)
    settings = Settings().with_streamlit_secrets()
    settings.ensure_directories()
    return settings


def reload_settings() -> Settings:
    """清理配置缓存并重新加载。"""

    get_settings.cache_clear()
    return get_settings()
