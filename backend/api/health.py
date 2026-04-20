"""Health, liveness, and readiness endpoints."""

from __future__ import annotations

import logging
from time import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.core.config import get_settings
from backend.core.response import success_response
from backend.db.session import get_async_session_factory


router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)
STARTED_AT = time()


@router.get("")
async def health(request: Request) -> dict[str, object]:
    """Return a cheap process health response."""

    return success_response({"status": "ok", "uptime_seconds": int(time() - STARTED_AT)}, request.state.request_id)


@router.get("/live")
async def liveness(request: Request) -> dict[str, object]:
    """Kubernetes-style liveness endpoint."""

    return success_response({"status": "alive", "uptime_seconds": int(time() - STARTED_AT)}, request.state.request_id)


@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    """Kubernetes-style readiness endpoint with dependency checks."""

    settings = get_settings()
    checks: dict[str, str] = {}
    ready = True

    try:
        session_factory = get_async_session_factory()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        ready = False
        checks["database"] = "error"
        logger.exception("readiness database check failed: %s", exc)

    if settings.celery_enabled and settings.readiness_check_redis:
        try:
            from redis.asyncio import Redis

            redis_client = Redis.from_url(settings.resolve_celery_broker_url())
            try:
                await redis_client.ping()
            finally:
                await redis_client.aclose()
            checks["redis"] = "ok"
        except Exception as exc:
            ready = False
            checks["redis"] = "error"
            logger.exception("readiness redis check failed: %s", exc)
    else:
        checks["redis"] = "skipped"

    payload = success_response(
        {"status": "ready" if ready else "not_ready", "checks": checks},
        request.state.request_id,
    )
    return JSONResponse(status_code=200 if ready else 503, content=payload)
