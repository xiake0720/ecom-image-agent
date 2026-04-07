"""FastAPI 后端配置模块。

该模块集中管理后端配置，避免路径和参数散落硬编码。
输入：环境变量与默认值。
输出：可被服务层和路由层复用的 Settings 单例。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置。

    设计意图：
    - 将运行目录、模板目录、CORS 等运行参数统一收敛；
    - 为后续多环境部署保留扩展位。
    """

    model_config = SettingsConfigDict(env_prefix="ECOM_", env_file=".env", extra="ignore")

    app_name: str = "ecom-image-agent-api"
    debug: bool = False
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    storage_root: Path = Path("storage")
    outputs_root: Path = Path("outputs/tasks")
    template_root: Path = Path("backend/templates")


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


def _resolve_project_path(path: Path) -> Path:
    """把相对路径统一解析到仓库根目录，避免依赖当前工作目录。"""

    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
