"""API v1 routes for result image edits."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.api.dependencies import get_current_user
from backend.core.response import success_response
from backend.db.models.user import User
from backend.schemas.image_edit import ImageEditCreateRequest
from backend.services.image_edit_service import ImageEditService


router = APIRouter(prefix="/results", tags=["image-edits-v1"])
service = ImageEditService()


@router.post("/{result_id}/edits")
async def create_result_edit(
    result_id: str,
    payload: ImageEditCreateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """Create an edit task for a result image."""

    data = await service.create_edit(current_user=current_user, result_id=result_id, payload=payload)
    return success_response(data.model_dump(mode="json"), request.state.request_id, message="图片编辑任务已提交")


@router.get("/{result_id}/edits")
async def list_result_edits(
    result_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """List edit history for a result image."""

    data = await service.list_edits(current_user=current_user, result_id=result_id)
    return success_response(data.model_dump(mode="json"), request.state.request_id)
