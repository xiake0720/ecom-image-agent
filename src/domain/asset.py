from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    PRODUCT = "product"
    WHITE_BG = "white_bg"
    DETAIL = "detail"
    OTHER = "other"


class Asset(BaseModel):
    asset_id: str
    filename: str
    local_path: str
    mime_type: str = "image/png"
    asset_type: AssetType = AssetType.OTHER
    width: int | None = None
    height: int | None = None
    tags: list[str] = Field(default_factory=list)

