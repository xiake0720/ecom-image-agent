"""模板相关路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.response import success_response
from backend.schemas.task import DetailPageGenerateRequest
from backend.services.detail_page_service import DetailPageService
from backend.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])
template_service = TemplateService()
detail_service = DetailPageService()


@router.get("/main-images")
def list_main_templates(request: Request) -> dict[str, object]:
    """查询主图模板列表。"""

    return success_response(template_service.list_main_templates(), request.state.request_id)


@router.get("/detail-pages")
def list_detail_templates(request: Request) -> dict[str, object]:
    """查询详情页模板列表。"""

    return success_response(template_service.list_detail_templates(), request.state.request_id)


@router.post("/detail-pages/preview")
def preview_detail_template(payload: DetailPageGenerateRequest, request: Request) -> dict[str, object]:
    """根据当前输入生成详情页预览数据。"""

    result = detail_service.generate(payload)
    return success_response(result.model_dump(mode="json"), request.state.request_id)
