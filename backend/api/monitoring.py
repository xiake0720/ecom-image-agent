"""Operations endpoints that are not part of the public API versioning."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from backend.core.config import get_settings
from backend.core.metrics import metrics_registry


router = APIRouter(tags=["monitoring"])


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    """Expose a minimal Prometheus text endpoint."""

    if not get_settings().metrics_enabled:
        return PlainTextResponse("metrics disabled\n", status_code=404)
    return PlainTextResponse(
        metrics_registry.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
