"""素材 contract。

文件位置：
- `src/domain/asset.py`

职责：
- 定义上传素材的最小结构
- 区分产品参考图与背景风格参考图
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    """素材类型枚举。"""

    PRODUCT = "product"
    WHITE_BG = "white_bg"
    DETAIL = "detail"
    BACKGROUND_STYLE = "background_style"
    OTHER = "other"


class Asset(BaseModel):
    """任务内单个素材的最小描述。"""

    asset_id: str
    filename: str
    local_path: str
    mime_type: str = "image/png"
    asset_type: AssetType = AssetType.OTHER
    width: int | None = None
    height: int | None = None
    tags: list[str] = Field(default_factory=list)
