"""Request middleware for context, safety headers, and basic telemetry."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from logging import getLogger
from urllib.parse import parse_qsl, urlencode

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from backend.core.config import Settings, get_settings
from backend.core.logging import format_log_event
from backend.core.metrics import metrics_registry
from backend.core.response import error_response


access_logger = getLogger("backend.access")


async def request_context_middleware(request: Request, call_next: Callable) -> Response:
    """Attach request context and keep production safeguards in one place."""

    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    settings = get_settings()
    content_length = _content_length(request)
    client_ip = _client_ip(request)

    if settings.log_http_access:
        _log_access(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            route_path=_route_path(request),
            client_ip=client_ip,
            query_string=_safe_query_string(request),
            content_length=content_length,
        )

    if _body_too_large(request, settings):
        if settings.log_http_access:
            _log_access(
                "request_body_too_large",
                level="warning",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                route_path=_route_path(request),
                client_ip=client_ip,
                query_string=_safe_query_string(request),
                content_length=content_length,
                max_request_body_size_bytes=settings.max_request_body_size_bytes,
            )
        response = JSONResponse(
            status_code=413,
            content=error_response(4130, "Request body too large", request_id),
        )
    else:
        try:
            response = await call_next(request)
        except Exception:
            elapsed_seconds = time.perf_counter() - started
            if settings.log_http_access:
                _log_access(
                    "request_failed",
                    level="exception",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    route_path=_route_path(request),
                    elapsed_ms=int(elapsed_seconds * 1000),
                    client_ip=client_ip,
                    query_string=_safe_query_string(request),
                    content_length=content_length,
                )
            raise

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
    if settings.log_http_access:
        _log_access(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            route_path=_route_path(request),
            status_code=response.status_code,
            elapsed_ms=int(elapsed_seconds * 1000),
            client_ip=client_ip,
            query_string=_safe_query_string(request),
            content_length=content_length,
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


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return ""


def _content_length(request: Request) -> int | None:
    raw_content_length = request.headers.get("content-length")
    if not raw_content_length:
        return None
    try:
        return int(raw_content_length)
    except ValueError:
        return None


def _safe_query_string(request: Request) -> str:
    raw_query = request.url.query
    if not raw_query:
        return ""
    pairs = parse_qsl(raw_query, keep_blank_values=True)
    return urlencode(
        [(key, "<redacted>" if _is_sensitive_key(key) else value) for key, value in pairs],
        doseq=True,
    )


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    sensitive_markers = ("password", "token", "refresh_token", "authorization", "secret", "api_key", "apikey")
    return any(marker in normalized for marker in sensitive_markers)


def _log_access(event: str, level: str = "info", **fields: object) -> None:
    log_fields = {"event": event, **fields}
    message = format_log_event(event, **fields)
    if level == "warning":
        access_logger.warning(message, extra=log_fields)
    elif level == "exception":
        access_logger.exception(message, extra=log_fields)
    else:
        access_logger.info(message, extra=log_fields)
