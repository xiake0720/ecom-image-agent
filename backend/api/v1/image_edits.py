"""API v1 routes for result image edits."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.api.dependencies import get_current_user, get_request_context
from backend.core.rate_limit import rate_limit
from backend.core.request_context import RequestContext
from backend.core.response import success_response
from backend.db.enums import AuditAction
from backend.db.models.user import User
from backend.schemas.image_edit import ImageEditCreateRequest
from backend.services.audit_service import write_audit_log
from backend.services.image_edit_service import ImageEditService


router = APIRouter(prefix="/results", tags=["image-edits-v1"])
service = ImageEditService()


@router.post("/{result_id}/edits")
async def create_result_edit(
    result_id: str,
    payload: ImageEditCreateRequest,
    request: Request,
    _rate_limited: Annotated[None, Depends(rate_limit("task_create"))],
    current_user: Annotated[User, Depends(get_current_user)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    """Create an edit task for a result image."""

    data = await service.create_edit(current_user=current_user, result_id=result_id, payload=payload)
    await write_audit_log(
        action=AuditAction.IMAGE_EDIT_CREATE.value,
        current_user=current_user,
        context=context,
        object_type="image_edit",
        object_id=data.edit_id,
        payload={
            "source_result_id": data.source_result_id,
            "edit_task_id": data.edit_task_id,
            "mode": data.mode,
        },
    )
    return success_response(data.model_dump(mode="json"), request.state.request_id, message="Image edit task submitted")


@router.get("/{result_id}/edits")
async def list_result_edits(
    result_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    """List edit history for a result image."""

    data = await service.list_edits(current_user=current_user, result_id=result_id)
    return success_response(data.model_dump(mode="json"), request.state.request_id)
