"""主图生成路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi import Depends

from backend.api.dependencies import get_current_user, get_request_context
from backend.core.config import get_settings
from backend.core.rate_limit import rate_limit
from backend.core.request_context import RequestContext
from backend.core.response import success_response
from backend.db.enums import AuditAction, TaskType
from backend.db.models.user import User
from backend.schemas.task import MainImageGeneratePayload
from backend.services.audit_service import write_audit_log
from backend.services.main_image_service import MainImageService
from backend.services.task_queue_service import main_image_task_queue

router = APIRouter(prefix="/image", tags=["image"])
service = MainImageService()


@router.post("/generate-main")
async def generate_main_image(
    request: Request,
    white_bg: UploadFile = File(...),
    detail_files: list[UploadFile] = File(default_factory=list),
    bg_files: list[UploadFile] = File(default_factory=list),
    brand_name: str = Form(default=""),
    product_name: str = Form(default=""),
    category: str = Form(default="tea"),
    platform: str = Form(default="tmall"),
    style_type: str = Form(default="高端极简"),
    style_notes: str = Form(default=""),
    shot_count: int = Form(default=8),
    aspect_ratio: str = Form(default="1:1"),
    image_size: str = Form(default="2K"),
    _rate_limited: Annotated[None, Depends(rate_limit("task_create"))] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    context: Annotated[RequestContext, Depends(get_request_context)] = None,
) -> dict[str, object]:
    """接收主图任务并立即返回 task_id，再由 Celery 或本地 fallback 执行。"""

    payload = MainImageGeneratePayload(
        brand_name=brand_name,
        product_name=product_name,
        category=category,
        platform=platform,
        style_type=style_type,
        style_notes=style_notes,
        shot_count=shot_count,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    prepared = await service.prepare_generation(
        payload=payload,
        white_bg=white_bg,
        detail_files=detail_files,
        bg_files=bg_files,
        current_user=current_user,
    )
    settings = get_settings()
    if settings.celery_enabled:
        from backend.workers.tasks.main_image_tasks import run_main_image_task

        run_main_image_task.delay(prepared.summary.task_id)
    else:
        main_image_task_queue.enqueue(prepared, service.run_prepared_task)
    await write_audit_log(
        action=AuditAction.TASK_CREATE.value,
        current_user=current_user,
        context=context,
        object_type="task",
        object_id=prepared.summary.task_id,
        payload={"task_type": TaskType.MAIN_IMAGE.value, "task_id": prepared.summary.task_id},
    )
    return success_response(prepared.summary.model_dump(mode="json"), request.state.request_id, message="主图任务已提交")
