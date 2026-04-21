"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import assets, detail, detail_jobs, health, image, monitoring, tasks, templates
from backend.api.v1 import router as v1_router
from backend.core.config import get_settings
from backend.core.exceptions import AppException
from backend.core.logging import format_log_event, setup_logging
from backend.core.middleware import request_context_middleware
from backend.core.response import error_response

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log_startup_configuration()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.middleware("http")(request_context_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(image.router, prefix=settings.api_prefix)
app.include_router(detail.router, prefix=settings.api_prefix)
app.include_router(detail_jobs.router, prefix=settings.api_prefix)
app.include_router(tasks.router, prefix=settings.api_prefix)
app.include_router(templates.router, prefix=settings.api_prefix)
app.include_router(assets.router, prefix=settings.api_prefix)
app.include_router(v1_router, prefix=settings.api_v1_prefix)
app.include_router(monitoring.router)


def log_startup_configuration() -> None:
    """Log non-secret startup configuration for operational diagnostics."""

    logger.info(
        format_log_event(
            "app_started",
            app_name=settings.app_name,
            debug=settings.debug,
            api_prefix=settings.api_prefix,
            api_v1_prefix=settings.api_v1_prefix,
            metrics_enabled=settings.metrics_enabled,
            celery_enabled=settings.celery_enabled,
            cos_enabled=settings.cos_enabled,
        ),
        extra={
            "event": "app_started",
            "app_name": settings.app_name,
            "debug": settings.debug,
            "api_prefix": settings.api_prefix,
            "api_v1_prefix": settings.api_v1_prefix,
            "metrics_enabled": settings.metrics_enabled,
            "celery_enabled": settings.celery_enabled,
            "cos_enabled": settings.cos_enabled,
        },
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """统一处理业务异常，返回受控错误信息。"""

    request_id = getattr(request.state, "request_id", "")
    logger.warning(
        format_log_event(
            "handled_app_exception",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=_safe_query_params(request),
            client_ip=_client_ip(request),
            status_code=exc.status_code,
            code=exc.code,
            message=str(exc),
        ),
        extra={
            "event": "handled_app_exception",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": _safe_query_params(request),
            "client_ip": _client_ip(request),
            "status_code": exc.status_code,
            "code": exc.code,
            "error_message": str(exc),
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, str(exc), request_id),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """统一处理参数校验错误。"""

    request_id = getattr(request.state, "request_id", "")
    safe_errors = _safe_validation_errors(exc)
    logger.warning(
        format_log_event(
            "request_validation_error",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=_safe_query_params(request),
            client_ip=_client_ip(request),
            errors=safe_errors,
        ),
        extra={
            "event": "request_validation_error",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": _safe_query_params(request),
            "client_ip": _client_ip(request),
            "errors": safe_errors,
        },
    )
    return JSONResponse(status_code=422, content=error_response(4220, f"参数校验失败: {exc.errors()}", request_id))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理，避免向前端泄漏原始栈信息。"""

    request_id = getattr(request.state, "request_id", "")
    logger.exception(
        format_log_event(
            "unhandled_exception",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=_safe_query_params(request),
            client_ip=_client_ip(request),
            error=exc,
        ),
        extra={
            "event": "unhandled_exception",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": _safe_query_params(request),
            "client_ip": _client_ip(request),
            "error": str(exc),
        },
    )
    return JSONResponse(status_code=500, content=error_response(5000, "服务内部错误，请稍后重试", request_id))


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return ""


def _safe_query_params(request: Request) -> str:
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


def _safe_validation_errors(exc: RequestValidationError) -> list[object]:
    return [_redact_validation_error(error) for error in exc.errors()]


def _redact_validation_error(error: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    loc = error.get("loc", ())
    sensitive_location = any(_is_sensitive_key(str(part)) for part in loc if part is not None)
    for key, value in error.items():
        if key == "input" and sensitive_location:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = _redact_sensitive_value(value)
    return redacted


def _redact_sensitive_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>" if _is_sensitive_key(str(key)) else _redact_sensitive_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive_value(item) for item in value)
    return value
