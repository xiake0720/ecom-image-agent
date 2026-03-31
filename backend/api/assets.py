"""静态产物访问路由。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.core.config import get_settings
from backend.core.exceptions import AppException

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{file_name}")
def get_asset(file_name: str) -> FileResponse:
    """按文件名访问 storage 下产物。

    为了安全仅允许读取 storage 根目录下文件名匹配的文件。
    """

    root = get_settings().storage_root
    target = root / file_name
    if not target.exists() or not target.is_file():
        raise AppException("文件不存在", code=4045)
    return FileResponse(target)
