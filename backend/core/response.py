"""统一响应结构封装。"""

from __future__ import annotations

from typing import Any


def success_response(data: Any, request_id: str, message: str = "ok") -> dict[str, Any]:
    """返回成功响应。

    输入：业务数据与 request_id。
    输出：统一结构的 JSON 字典。
    """

    return {"code": 0, "message": message, "data": data, "requestId": request_id}


def error_response(code: int, message: str, request_id: str) -> dict[str, Any]:
    """返回错误响应。"""

    return {"code": code, "message": message, "data": None, "requestId": request_id}
