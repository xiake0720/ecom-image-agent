"""主图生成路由。"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile

from backend.core.response import success_response
from backend.schemas.task import MainImageGeneratePayload
from backend.services.main_image_service import MainImageService

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
) -> dict[str, object]:
    """接收主图生成任务并同步执行。"""

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
    summary = await service.generate(payload=payload, white_bg=white_bg, detail_files=detail_files, bg_files=bg_files)
    return success_response(summary.model_dump(mode="json"), request.state.request_id, message="主图任务完成")
