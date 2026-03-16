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
import logging
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
    enable_node_cache: bool = True
    budget_mode: str = "production"
    prompt_build_mode: str | None = None
    render_mode: str | None = None
    preview_shot_count: int = 2
    preview_output_size: str = "1024x1024"
    analyze_max_reference_images: int = 2
    render_max_reference_images: int = 2
    text_provider: str | None = None
    vision_provider: str | None = None
    image_provider: str | None = None
    text_provider_mode: str = "real"
    vision_provider_mode: str = "real"
    image_provider_mode: str = "real"
    text_model_provider: str = "qwen"
    vision_model_provider: str = "qwen"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    dashscope_api_key: str | None = Field(default=None, validation_alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias="DASHSCOPE_BASE_URL",
    )
    zhipu_api_key: str | None = Field(default=None, validation_alias="ZHIPU_API_KEY")
    zhipu_base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4/",
        validation_alias="ZHIPU_BASE_URL",
    )
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", validation_alias="OLLAMA_BASE_URL")
    text_model: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_TEXT_MODEL")
    text_model_id: str | None = None
    vision_model: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_VISION_MODEL")
    vision_model_id: str | None = None
    image_model: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_IMAGE_MODEL")
    image_model_id: str | None = None
    image_edit_provider: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_IMAGE_EDIT_PROVIDER")
    image_edit_model: str | None = Field(default=None, validation_alias="ECOM_IMAGE_AGENT_IMAGE_EDIT_MODEL")
    image_edit_enabled: bool = Field(default=True, validation_alias="ECOM_IMAGE_AGENT_IMAGE_EDIT_ENABLED")
    image_edit_prefer_multi_image: bool = Field(
        default=True,
        validation_alias="ECOM_IMAGE_AGENT_IMAGE_EDIT_PREFER_MULTI_IMAGE",
    )
    image_edit_max_reference_images: int | None = Field(
        default=None,
        validation_alias="ECOM_IMAGE_AGENT_IMAGE_EDIT_MAX_REFERENCE_IMAGES",
    )
    image_allow_mock_fallback: bool = Field(
        default=False,
        validation_alias="ECOM_IMAGE_AGENT_IMAGE_ALLOW_MOCK_FALLBACK",
    )
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
    text_render_preset: str = "premium_minimal"
    text_render_adaptive_style_enabled: bool = True
    text_render_min_title_font_size: int = 40
    text_render_min_subtitle_font_size: int = 24
    text_render_min_bullets_font_size: int = 22
    text_render_min_cta_font_size: int = 22
    outputs_dir: Path = Path("outputs")
    tasks_dir: Path = Path("outputs/tasks")
    cache_dir: Path = Path("outputs/cache")
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
        field = cls.model_fields.get(field_name)
        if field is not None and isinstance(field.validation_alias, str):
            return field.validation_alias
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
        for path in (self.outputs_dir, self.tasks_dir, self.cache_dir, self.previews_dir, self.exports_dir, self.assets_dir):
            path.mkdir(parents=True, exist_ok=True)

    def build_debug_summary(self) -> dict[str, str]:
        """返回适合 UI 调试区展示的关键运行配置摘要。"""
        text_route = self.resolve_text_provider_route()
        vision_route = self.resolve_vision_provider_route()
        image_route = self.resolve_image_provider_route()
        image_edit_route = self.resolve_image_edit_provider_route()
        text_selection = self.resolve_text_model_selection()
        vision_selection = self.resolve_vision_model_selection()
        image_selection = self.resolve_image_model_selection()
        image_edit_selection = self.resolve_image_edit_model_selection()
        return {
            "budget_mode": self.resolve_budget_mode(),
            "text_provider_mode": self.text_provider_mode,
            "vision_provider_mode": self.vision_provider_mode,
            "image_provider_mode": self.image_provider_mode,
            "effective_text_provider_mode": text_route.mode,
            "effective_vision_provider_mode": vision_route.mode,
            "effective_image_provider_mode": image_route.mode,
            "text_provider_alias": text_route.alias,
            "vision_provider_alias": vision_route.alias,
            "image_provider_alias": image_route.alias,
            "image_edit_provider_alias": image_edit_route.alias,
            "text_provider_source": text_route.source,
            "vision_provider_source": vision_route.source,
            "image_provider_source": image_route.source,
            "image_edit_provider_source": image_edit_route.source,
            "text_model_provider": text_selection.provider_key,
            "text_model_id": text_selection.model_id,
            "vision_model_provider": vision_selection.provider_key,
            "vision_model_id": vision_selection.model_id,
            "image_model_provider": image_selection.provider_key,
            "image_model_id": image_selection.model_id,
            "image_edit_model_provider": image_edit_selection.provider_key,
            "image_edit_model_id": image_edit_selection.model_id,
            "text_model_label": text_selection.label,
            "vision_model_label": vision_selection.label,
            "image_model_label": image_selection.label,
            "image_edit_model_label": image_edit_selection.label,
            "text_model_source": text_selection.source,
            "vision_model_source": vision_selection.source,
            "image_model_source": image_selection.source,
            "image_edit_model_source": image_edit_selection.source,
            "log_level": self.log_level,
            "prompt_build_mode": self.resolve_prompt_build_mode(),
            "render_mode": self.resolve_render_mode(),
            "preview_shot_count": str(self.preview_shot_count),
            "preview_output_size": self.preview_output_size,
            "analyze_max_reference_images": str(self.analyze_max_reference_images),
            "render_max_reference_images": str(self.render_max_reference_images),
            "image_edit_enabled": "true" if self.image_edit_enabled else "false",
            "image_edit_prefer_multi_image": "true" if self.image_edit_prefer_multi_image else "false",
            "image_edit_max_reference_images": str(self.resolve_image_edit_max_reference_images()),
            "enable_node_cache": "true" if self.enable_node_cache else "false",
            "enable_file_log": "true" if self.enable_file_log else "false",
            "default_font_path": str(self.default_font_path),
            "text_render_preset": self.resolve_text_render_preset(),
            "text_render_adaptive_style_enabled": "true" if self.text_render_adaptive_style_enabled else "false",
            "text_render_min_title_font_size": str(self.text_render_min_title_font_size),
            "text_render_min_subtitle_font_size": str(self.text_render_min_subtitle_font_size),
            "text_render_min_bullets_font_size": str(self.text_render_min_bullets_font_size),
            "text_render_min_cta_font_size": str(self.text_render_min_cta_font_size),
            "proxy_enabled": "true" if self.is_proxy_enabled() else "false",
            "dashscope_api_key_loaded": "true" if bool(self.dashscope_api_key) else "false",
            "dashscope_base_url": self.dashscope_base_url,
            "image_allow_mock_fallback": "true" if self.image_allow_mock_fallback else "false",
            "runapi_image_model": self.runapi_image_model,
            "outputs_dir": str(self.outputs_dir),
            "tasks_dir": str(self.tasks_dir),
            "cache_dir": str(self.cache_dir),
        }

    def resolve_text_model_selection(self) -> ResolvedModelSelection:
        """解析当前结构化规划能力实际使用的模型。"""
        route = self.resolve_text_provider_route()
        legacy_model_provider = (self.text_model_provider or "qwen").strip().lower()
        provider_key = route.alias if route.alias != "mock" else legacy_model_provider
        if self.text_model:
            return ResolvedModelSelection(
                capability="planning",
                provider_key=provider_key or "custom",
                model_id=self.text_model,
                label=self._label_for_model(provider_key, self.text_model),
                source="ECOM_IMAGE_AGENT_TEXT_MODEL",
            )
        if self.text_model_id:
            return ResolvedModelSelection(
                capability="planning",
                provider_key=provider_key or "custom",
                model_id=self.text_model_id,
                label=self._label_for_model(provider_key, self.text_model_id),
                source="ECOM_IMAGE_AGENT_TEXT_MODEL_ID",
            )
        if provider_key == "nvidia" and self.nvidia_text_model:
            return ResolvedModelSelection(
                capability="planning",
                provider_key=provider_key or "legacy",
                model_id=self.nvidia_text_model,
                label=self._label_for_model(provider_key, self.nvidia_text_model),
                source="ECOM_IMAGE_AGENT_NVIDIA_TEXT_MODEL",
            )
        if provider_key == "nvidia" and legacy_model_provider == "qwen":
            return ResolvedModelSelection(
                capability="planning",
                provider_key="nvidia",
                model_id=self.qwen_model_id,
                label="Qwen3.5",
                source=route.source,
            )
        if provider_key == "nvidia" and legacy_model_provider == "glm5":
            return ResolvedModelSelection(
                capability="planning",
                provider_key="nvidia",
                model_id=self.glm5_model_id,
                label="GLM-5",
                source=route.source,
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
        if provider_key == "ollama":
            model_id = self.text_model_id or "qwen2.5:7b-instruct"
            return ResolvedModelSelection(
                capability="planning",
                provider_key="ollama",
                model_id=model_id,
                label="Ollama",
                source=route.source,
            )
        if provider_key == "dashscope":
            model_id = self.text_model or self.text_model_id or "qwen-plus"
            return ResolvedModelSelection(
                capability="planning",
                provider_key="dashscope",
                model_id=model_id,
                label=self._label_for_model(provider_key, model_id),
                source=route.source,
            )
        if provider_key in {"zhipu", "zhipu_glm47_flash"}:
            model_id = self.text_model or self.text_model_id or "glm-4.7-flash"
            return ResolvedModelSelection(
                capability="planning",
                provider_key="zhipu",
                model_id=model_id,
                label="GLM-4.7-Flash",
                source=route.source,
            )
        if provider_key == "zhipu_glm47":
            model_id = self.text_model or self.text_model_id or "glm-4.7"
            return ResolvedModelSelection(
                capability="planning",
                provider_key="zhipu",
                model_id=model_id,
                label="GLM-4.7",
                source=route.source,
            )
        raise RuntimeError(
            "不支持的文本模型开关："
            f"{provider_key}。当前仅支持 nvidia / ollama / dashscope / zhipu，"
            "如需自定义模型，请显式设置 ECOM_IMAGE_AGENT_TEXT_MODEL_ID。"
        )

    def resolve_vision_model_selection(self) -> ResolvedModelSelection:
        """解析当前视觉分析能力实际使用的模型。"""
        route = self.resolve_vision_provider_route()
        legacy_model_provider = (self.vision_model_provider or "qwen").strip().lower()
        provider_key = route.alias if route.alias != "mock" else legacy_model_provider
        if self.vision_model:
            return ResolvedModelSelection(
                capability="vision",
                provider_key=provider_key or "custom",
                model_id=self.vision_model,
                label=self._label_for_model(provider_key, self.vision_model),
                source="ECOM_IMAGE_AGENT_VISION_MODEL",
            )
        if self.vision_model_id:
            return ResolvedModelSelection(
                capability="vision",
                provider_key=provider_key or "custom",
                model_id=self.vision_model_id,
                label=self._label_for_model(provider_key, self.vision_model_id),
                source="ECOM_IMAGE_AGENT_VISION_MODEL_ID",
            )
        if provider_key == "nvidia" and self.nvidia_vision_model:
            return ResolvedModelSelection(
                capability="vision",
                provider_key=provider_key or "legacy",
                model_id=self.nvidia_vision_model,
                label=self._label_for_model(provider_key, self.nvidia_vision_model),
                source="ECOM_IMAGE_AGENT_NVIDIA_VISION_MODEL",
            )
        if provider_key == "nvidia" and legacy_model_provider == "qwen":
            return ResolvedModelSelection(
                capability="vision",
                provider_key="nvidia",
                model_id=self.qwen_model_id,
                label="Qwen3.5",
                source=route.source,
            )
        if provider_key == "qwen":
            return ResolvedModelSelection(
                capability="vision",
                provider_key="qwen",
                model_id=self.qwen_model_id,
                label="Qwen3.5",
                source="ECOM_IMAGE_AGENT_VISION_MODEL_PROVIDER",
            )
        if provider_key == "dashscope":
            model_id = self.vision_model or self.vision_model_id or "qwen3-vl-flash"
            return ResolvedModelSelection(
                capability="vision",
                provider_key="dashscope",
                model_id=model_id,
                label=self._label_for_model(provider_key, model_id),
                source=route.source,
            )
        if provider_key == "zhipu":
            model_id = self.vision_model or self.vision_model_id or "glm-4.6v-flash"
            return ResolvedModelSelection(
                capability="vision",
                provider_key="zhipu",
                model_id=model_id,
                label="Zhipu Flash Vision",
                source=route.source,
            )
        raise RuntimeError(
            "不支持的视觉模型开关："
            f"{provider_key}。当前默认视觉链路仅支持 nvidia / dashscope / zhipu，"
            "如需自定义视觉模型，请显式设置 ECOM_IMAGE_AGENT_VISION_MODEL_ID。"
        )

    def resolve_image_model_selection(self) -> ResolvedModelSelection:
        """解析当前图片能力实际使用的模型。"""
        route = self.resolve_image_provider_route()
        provider_key = route.alias
        if provider_key == "runapi":
            return ResolvedModelSelection(
                capability="image",
                provider_key="runapi",
                model_id=self.runapi_image_model,
                label="RunAPI",
                source=route.source,
            )
        if provider_key == "dashscope":
            model_id = self.image_model or self.image_model_id or "wanx2.1-t2i-turbo"
            return ResolvedModelSelection(
                capability="image",
                provider_key="dashscope",
                model_id=model_id,
                label=self._label_for_model(provider_key, model_id),
                source=route.source,
            )
        if provider_key == "zhipu":
            return ResolvedModelSelection(
                capability="image",
                provider_key="zhipu",
                model_id="cogview-auto",
                label="Zhipu Image",
                source=route.source,
            )
        return ResolvedModelSelection(
            capability="image",
            provider_key="mock",
            model_id="mock-local",
            label="Mock Local",
            source=route.source,
        )

    def resolve_image_edit_provider_route(self) -> ResolvedProviderRoute:
        """Resolve the effective image edit/reference provider route."""
        base_route = self.resolve_image_provider_route()
        if base_route.mode != "real":
            return ResolvedProviderRoute(
                capability="image_edit",
                alias="mock",
                mode="mock",
                label="Mock Local",
                source=base_route.source,
            )
        if self.image_edit_provider:
            alias = str(self.image_edit_provider).strip().lower()
            source = self.env_name_for("image_edit_provider")
        else:
            alias = base_route.alias
            source = base_route.source
        return ResolvedProviderRoute(
            capability="image_edit",
            alias=alias,
            mode="real",
            label=alias.upper(),
            source=source,
        )

    def resolve_image_edit_model_selection(self) -> ResolvedModelSelection:
        """Resolve the effective image edit/reference model selection."""
        route = self.resolve_image_edit_provider_route()
        if route.mode != "real" or route.alias == "mock":
            return ResolvedModelSelection(
                capability="image_edit",
                provider_key="mock",
                model_id="mock-local",
                label="Mock Local",
                source=route.source,
            )
        if route.alias == "dashscope":
            model_id = self.image_edit_model or "wan2.6-image"
            source = "ECOM_IMAGE_AGENT_IMAGE_EDIT_MODEL" if self.image_edit_model else route.source
            return ResolvedModelSelection(
                capability="image_edit",
                provider_key="dashscope",
                model_id=model_id,
                label=self._label_for_model(route.alias, model_id),
                source=source,
            )
        if route.alias == "runapi":
            model_id = self.image_edit_model or self.runapi_image_model
            source = "ECOM_IMAGE_AGENT_IMAGE_EDIT_MODEL" if self.image_edit_model else "ECOM_IMAGE_AGENT_RUNAPI_IMAGE_MODEL"
            return ResolvedModelSelection(
                capability="image_edit",
                provider_key="runapi",
                model_id=model_id,
                label="RunAPI",
                source=source,
            )
        model_id = self.image_edit_model or self.resolve_image_model_selection().model_id
        source = "ECOM_IMAGE_AGENT_IMAGE_EDIT_MODEL" if self.image_edit_model else route.source
        return ResolvedModelSelection(
            capability="image_edit",
            provider_key=route.alias,
            model_id=model_id,
            label=self._label_for_model(route.alias, model_id),
            source=source,
        )

    def resolve_image_edit_max_reference_images(self) -> int:
        """Resolve the maximum number of reference images allowed for image edit."""
        explicit_value = self.image_edit_max_reference_images
        if explicit_value is not None:
            return max(1, int(explicit_value))
        return max(1, int(self.render_max_reference_images))

    def resolve_budget_mode(self) -> str:
        """返回标准化后的预算模式。"""
        normalized = str(self.budget_mode or "production").strip().lower()
        allowed = {"local", "cheap", "balanced", "production"}
        if normalized not in allowed:
            raise RuntimeError(
                "不支持的预算模式："
                f"{normalized}。当前仅支持 local / cheap / balanced / production。"
            )
        return normalized

    def resolve_prompt_build_mode(self) -> str:
        explicit_value = self.prompt_build_mode
        allowed = {"per_shot", "batch"}
        if explicit_value:
            normalized = str(explicit_value).strip().lower()
            if normalized not in allowed:
                raise RuntimeError(
                    "不支持的 prompt build mode："
                    f"{normalized}。当前仅支持 per_shot / batch。"
                )
            return normalized
        budget_mode = self.resolve_budget_mode()
        if budget_mode in {"local", "cheap"}:
            return "batch"
        return "per_shot"

    def resolve_render_mode(self) -> str:
        explicit_value = self.render_mode
        allowed = {"preview", "final", "full_auto"}
        if explicit_value:
            normalized = str(explicit_value).strip().lower()
            if normalized not in allowed:
                raise RuntimeError(
                    "不支持的 render mode："
                    f"{normalized}。当前仅支持 preview / final / full_auto。"
                )
            return normalized
        return "full_auto"

    def resolve_text_render_preset(self) -> str:
        explicit_value = str(self.text_render_preset or "premium_minimal").strip().lower()
        allowed = {"premium_minimal", "commercial_balanced"}
        if explicit_value not in allowed:
            raise RuntimeError(
                f"Unsupported text render preset: {explicit_value}. Current supported presets: premium_minimal / commercial_balanced."
            )
        return explicit_value

    def resolve_text_render_min_font_size(self, block_kind: str) -> int:
        """返回指定文字块允许缩小到的最小字号。"""
        min_size_map = {
            "title": self.text_render_min_title_font_size,
            "subtitle": self.text_render_min_subtitle_font_size,
            "bullets": self.text_render_min_bullets_font_size,
            "cta": self.text_render_min_cta_font_size,
        }
        return int(min_size_map.get(block_kind, self.text_render_min_bullets_font_size))

    def resolve_project_font_candidates(self, requested_font_path: Path | None = None) -> tuple[Path, ...]:
        """返回项目内优先尝试的中文字体候选列表。"""
        requested = requested_font_path or self.default_font_path
        font_dir = self.assets_dir / "fonts"
        candidates: list[Path] = []
        known_names = [
            requested.name,
            "NotoSansSC-Regular.otf",
            "NotoSansSC-Medium.otf",
            "NotoSansSC-Bold.otf",
            "SourceHanSansSC-Regular.otf",
            "SourceHanSansCN-Regular.otf",
            "SourceHanSansSC-Medium.otf",
            "AlibabaPuHuiTi-3-55-Regular.ttf",
            "AlibabaPuHuiTi-3-75-SemiBold.ttf",
        ]
        for name in known_names:
            if not name:
                continue
            path = requested if requested.name == name else font_dir / name
            if path not in candidates:
                candidates.append(path)
        if requested not in candidates:
            candidates.insert(0, requested)
        return tuple(candidates)

    def resolve_system_chinese_font_candidates(self) -> tuple[Path, ...]:
        """按平台返回更适合中文渲染的系统字体候选。

        Windows 是当前仓库优先兼容目标，因此优先尝试微软雅黑、等线、黑体、宋体。
        """
        if os.name == "nt":
            fonts_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            names = [
                "msyh.ttc",
                "msyhbd.ttc",
                "msyhl.ttc",
                "Deng.ttf",
                "Dengb.ttf",
                "simhei.ttf",
                "simsun.ttc",
                "simsunb.ttf",
                "simfang.ttf",
                "simkai.ttf",
            ]
            return tuple(fonts_dir / name for name in names)
        if sys.platform == "darwin":
            return (
                Path("/System/Library/Fonts/PingFang.ttc"),
                Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
                Path("/Library/Fonts/Arial Unicode.ttf"),
                Path("/System/Library/Fonts/STHeiti Medium.ttc"),
            )
        return (
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            Path("/usr/share/fonts/truetype/arphic/ukai.ttc"),
            Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
            Path("/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf"),
        )

    def resolve_text_provider_route(self) -> ResolvedProviderRoute:
        """解析当前文本 provider 路由。"""
        mode = self._resolve_effective_provider_mode("text")
        alias, source = self._resolve_effective_provider_alias("text")
        if mode != "real":
            alias = "mock"
        return ResolvedProviderRoute(
            capability="planning",
            alias=alias,
            mode=mode,
            label=alias.upper() if alias != "mock" else "Mock Local",
            source=source,
        )

    def resolve_vision_provider_route(self) -> ResolvedProviderRoute:
        """解析当前视觉 provider 路由。"""
        mode = self._resolve_effective_provider_mode("vision")
        alias, source = self._resolve_effective_provider_alias("vision")
        if mode != "real":
            alias = "mock"
        return ResolvedProviderRoute(
            capability="vision",
            alias=alias,
            mode=mode,
            label=alias.upper() if alias != "mock" else "Mock Local",
            source=source,
        )

    def resolve_image_provider_route(self) -> ResolvedProviderRoute:
        """解析当前图片 provider 路由。"""
        mode = self._resolve_effective_provider_mode("image")
        alias, source = self._resolve_effective_provider_alias("image")
        if mode != "real" or alias == "mock":
            alias = "mock"
            mode = "mock"
        return ResolvedProviderRoute(
            capability="image",
            alias=alias,
            mode=mode,
            label=alias.upper() if alias != "mock" else "Mock Local",
            source=source,
        )

    def _label_for_model(self, provider_key: str, model_id: str) -> str:
        """根据 provider 开关和模型 ID 生成可读标签。"""
        normalized = (provider_key or "").strip().lower()
        lowered = model_id.lower()
        if "glm5" in lowered:
            return "GLM-5"
        if "wan2.6-image" in lowered:
            return "Wan 2.6 Image"
        if "wanx2.1-imageedit" in lowered:
            return "Wanx 2.1 Image Edit"
        if "wanx2.1-t2i-turbo" in lowered:
            return "Wanx 2.1 Turbo"
        if "qwen3-vl-flash" in lowered:
            return "Qwen3 VL Flash"
        if "qwen-plus" in lowered:
            return "Qwen Plus"
        if "glm-4.7-flash" in lowered:
            return "GLM-4.7-Flash"
        if "glm-4.7" in lowered:
            return "GLM-4.7"
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

    def _resolve_effective_provider_mode(self, capability: str) -> str:
        """解析预算模式作用后的有效 provider mode。"""
        field_name = f"{capability}_provider_mode"
        raw_mode = str(getattr(self, field_name) or "mock").strip().lower()
        if raw_mode not in {"mock", "real"}:
            raise RuntimeError(f"不支持的 {capability} provider mode: {raw_mode}")
        if field_name in self.model_fields_set or not self._should_apply_budget_defaults():
            return raw_mode
        return self._budget_defaults()[field_name]

    def _resolve_effective_provider_alias(self, capability: str) -> tuple[str, str]:
        """解析预算模式作用后的有效 provider alias。"""
        field_name = f"{capability}_provider"
        explicit_value = getattr(self, field_name)
        if explicit_value:
            return str(explicit_value).strip().lower(), self.env_name_for(field_name)
        if self._should_apply_budget_defaults():
            return self._budget_defaults()[field_name], self.env_name_for("budget_mode")
        default_alias_map = {
            "text": "dashscope",
            "vision": "dashscope",
            "image": "dashscope",
        }
        return default_alias_map[capability], "legacy-default"

    def _should_apply_budget_defaults(self) -> bool:
        """判断当前是否启用预算模式默认路由。"""
        return self.resolve_budget_mode() in {"local", "cheap", "balanced"} or "budget_mode" in self.model_fields_set

    def _budget_defaults(self) -> dict[str, str]:
        """返回预算模式对应的 provider 默认路由。"""
        budget_mode = self.resolve_budget_mode()
        presets = {
            "local": {
                "text_provider_mode": "real",
                "vision_provider_mode": "real",
                "image_provider_mode": "real",
                "prompt_build_mode": "batch",
                "text_provider": "dashscope",
                "vision_provider": "dashscope",
                "image_provider": "dashscope",
            },
            "cheap": {
                "text_provider_mode": "real",
                "vision_provider_mode": "real",
                "image_provider_mode": "real",
                "prompt_build_mode": "batch",
                "text_provider": "dashscope",
                "vision_provider": "dashscope",
                "image_provider": "dashscope",
            },
            "balanced": {
                "text_provider_mode": "real",
                "vision_provider_mode": "real",
                "image_provider_mode": "real",
                "prompt_build_mode": "per_shot",
                "text_provider": "dashscope",
                "vision_provider": "dashscope",
                "image_provider": "dashscope",
            },
            "production": {
                "text_provider_mode": "real",
                "vision_provider_mode": "real",
                "image_provider_mode": "real",
                "prompt_build_mode": "per_shot",
                "text_provider": "dashscope",
                "vision_provider": "dashscope",
                "image_provider": "dashscope",
            },
        }
        return presets[budget_mode]


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
    # Settings 带缓存；修改环境变量或 `.env` 后必须重启 Streamlit 进程，不能假定当前进程会自动感知。
    load_dotenv(override=False)
    settings = Settings().with_streamlit_secrets()
    settings.ensure_directories()
    logger.info(
        "配置已加载并写入缓存；如修改环境变量或 .env，请重启 Streamlit 进程后再验证 provider/model 切换。"
    )
    return settings


def reload_settings() -> Settings:
    """清理配置缓存并重新加载设置。"""
    get_settings.cache_clear()
    return get_settings()
