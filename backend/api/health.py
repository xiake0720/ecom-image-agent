"""健康检查路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.response import success_response

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(request: Request) -> dict[str, object]:
    """返回服务健康状态。"""

    return success_response({"status": "ok"}, request.state.request_id)
