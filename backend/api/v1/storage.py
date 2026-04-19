"""API v1 文件存储路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.api.dependencies import get_current_user
from backend.core.response import success_response
from backend.db.models.user import User
from backend.schemas.storage import StoragePresignRequest
from backend.services.storage.storage_service import StorageService


router = APIRouter(tags=["storage-v1"])
service = StorageService()


@router.post("/storage/presign")
async def create_presigned_upload(
    payload: StoragePresignRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """为当前用户任务生成图片直传 COS 的预签名 URL。"""

    data = await service.create_presigned_upload(current_user=current_user, payload=payload)
    return success_response(data.model_dump(mode="json"), request.state.request_id)


@router.get("/files/{file_id}/download-url")
async def get_file_download_url(
    file_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """校验文件归属后返回签名下载 URL。"""

    data = await service.create_download_url(current_user=current_user, file_id=file_id)
    return success_response(data.model_dump(mode="json"), request.state.request_id)
