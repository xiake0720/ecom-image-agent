"""FastAPI 应用入口。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import assets, detail, detail_jobs, health, image, tasks, templates
from backend.api.v1 import router as v1_router
from backend.core.config import get_settings
from backend.core.exceptions import AppException
from backend.core.logging import setup_logging
from backend.core.middleware import request_context_middleware
from backend.core.response import error_response

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
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


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """统一处理业务异常，返回受控错误信息。"""

    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(status_code=exc.status_code, content=error_response(exc.code, str(exc), request_id))


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """统一处理参数校验错误。"""

    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(status_code=422, content=error_response(4220, f"参数校验失败: {exc.errors()}", request_id))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理，避免向前端泄漏原始栈信息。"""

    logger.exception("未处理异常: %s", exc)
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(status_code=500, content=error_response(5000, "服务内部错误，请稍后重试", request_id))
