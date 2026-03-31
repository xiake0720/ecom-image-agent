"""公共 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApiEnvelope(BaseModel):
    """统一响应外层结构，便于前端统一处理。"""

    code: int = 0
    message: str = "ok"
    data: object | None = None
    requestId: str = Field(default="")
