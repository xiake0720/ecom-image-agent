"""Request middleware for context, safety headers, and basic telemetry."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from backend.core.config import Settings, get_settings
from backend.core.metrics import metrics_registry
from backend.core.response import error_response


async def request_context_middleware(request: Request, call_next: Callable) -> Response:
    """Attach request context and keep production safeguards in one place."""

    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    request.state.request_id = request_id
    started = time.perf_counter()
    settings = get_settings()

    if _body_too_large(request, settings):
        response = JSONResponse(
            status_code=413,
            content=error_response(4130, "Request body too large", request_id),
        )
    else:
        response = await call_next(request)

    elapsed_seconds = time.perf_counter() - started
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Elapsed-MS"] = str(int(elapsed_seconds * 1000))
    _apply_security_headers(response, settings)
    if settings.metrics_enabled:
        metrics_registry.record_http_request(
            method=request.method,
            path=_route_path(request),
            status_code=response.status_code,
            duration_seconds=elapsed_seconds,
        )
    return response


def _body_too_large(request: Request, settings: Settings) -> bool:
    if settings.max_request_body_size_bytes <= 0:
        return False
    raw_content_length = request.headers.get("content-length")
    if not raw_content_length:
        return False
    try:
        content_length = int(raw_content_length)
    except ValueError:
        return False
    return content_length > settings.max_request_body_size_bytes


def _apply_security_headers(response: Response, settings: Settings) -> None:
    if not settings.security_headers_enabled:
        return
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.security_hsts_enabled:
        response.headers.setdefault(
            "Strict-Transport-Security",
            f"max-age={settings.security_hsts_max_age_seconds}; includeSubDomains",
        )


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return str(getattr(route, "path", request.url.path))
