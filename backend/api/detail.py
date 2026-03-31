"""详情页生成路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.response import success_response
from backend.schemas.task import DetailPageGenerateRequest
from backend.services.detail_page_service import DetailPageService

router = APIRouter(prefix="/detail", tags=["detail"])
service = DetailPageService()


@router.post("/generate")
def generate_detail_page(payload: DetailPageGenerateRequest, request: Request) -> dict[str, object]:
    """生成详情页模块化 JSON。"""

    result = service.generate(payload)
    return success_response(result.model_dump(mode="json"), request.state.request_id, message="详情页生成完成")
