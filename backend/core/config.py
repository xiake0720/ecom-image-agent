"""FastAPI 后端配置模块。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """统一管理 FastAPI 应用配置。"""

    model_config = SettingsConfigDict(env_prefix="ECOM_", env_file=".env", extra="ignore")

    app_name: str = "ecom-image-agent-api"
    debug: bool = False
    api_prefix: str = "/api"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    storage_root: Path = Path("storage")
    outputs_root: Path = Path("outputs/tasks")
    template_root: Path = Path("backend/templates")

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ecom_image_agent"
    database_echo: bool = False

    auth_jwt_secret_key: str = "change-me-in-env"
    auth_jwt_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 60
    auth_refresh_token_expire_days: int = 30
    auth_refresh_cookie_name: str = "ecom_refresh_token"
    auth_refresh_cookie_secure: bool = False
    auth_refresh_cookie_samesite: str = "lax"
    auth_refresh_cookie_domain: str | None = None
    auth_refresh_cookie_path: str = "/api/v1/auth"
    auth_token_hash_secret: str = "change-me-too"
    compat_task_user_email: str = "compat-task-user@local.invalid"
    compat_task_user_nickname: str = "系统兼容任务账户"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        """兼容 JSON 数组和逗号分隔字符串。"""

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return ["*"]
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("auth_refresh_cookie_samesite")
    @classmethod
    def _normalize_samesite(cls, value: str) -> str:
        """限制 SameSite 取值，避免运行时写入非法 cookie。"""

        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("auth_refresh_cookie_samesite must be one of lax/strict/none")
        return normalized

    def resolve_database_url(self) -> str:
        """返回异步数据库 URL。"""

        return self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回缓存后的配置对象，并确保基础目录可用。"""

    settings = Settings()
    settings.storage_root = _resolve_project_path(settings.storage_root)
    settings.outputs_root = _resolve_project_path(settings.outputs_root)
    settings.template_root = _resolve_project_path(settings.template_root)
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.outputs_root.mkdir(parents=True, exist_ok=True)
    return settings


def reset_settings_cache() -> None:
    """为测试和脚本提供配置缓存重置入口。"""

    get_settings.cache_clear()


def _resolve_project_path(path: Path) -> Path:
    """把相对路径统一解析到仓库根目录。"""

    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
