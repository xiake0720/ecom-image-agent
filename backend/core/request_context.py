"""请求上下文抽象。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    """跨 route/service 传递的最小请求上下文。"""

    request_id: str
    ip_address: str | None
    user_agent: str | None
    device_id: str | None
