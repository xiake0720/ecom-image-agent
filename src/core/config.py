from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ecom-image-agent"
    env: str = "dev"
    enable_mock_providers: bool = True
    enable_ocr_qc: bool = False
    default_font_path: Path = Path("assets/fonts/NotoSansSC-Regular.otf")
    outputs_dir: Path = Path("outputs")
    tasks_dir: Path = Path("outputs/tasks")
    previews_dir: Path = Path("outputs/previews")
    exports_dir: Path = Path("outputs/exports")
    assets_dir: Path = Path("assets")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ECOM_IMAGE_AGENT_",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        for path in (self.outputs_dir, self.tasks_dir, self.previews_dir, self.exports_dir, self.assets_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
