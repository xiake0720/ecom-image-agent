"""请求链路中间件。"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response


async def request_context_middleware(request: Request, call_next: Callable) -> Response:
    """为每个请求注入 request_id 并记录耗时。

    为什么这样做：
    - 统一 request_id，便于跨日志与接口响应对齐。
    - 最小化侵入，不要求每个路由重复写样板代码。
    """

    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Elapsed-MS"] = str(int((time.perf_counter() - started) * 1000))
    return response
