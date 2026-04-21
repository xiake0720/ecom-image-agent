"""Celery application configuration entrypoint."""

from __future__ import annotations

import logging

from celery import Celery

from backend.core.config import get_settings
from backend.core.logging import format_log_event, setup_logging


setup_logging()
logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    """Create the Celery app from FastAPI settings."""

    settings = get_settings()
    app = Celery(
        "ecom_image_agent",
        broker=settings.resolve_celery_broker_url(),
        backend=settings.resolve_celery_result_backend(),
        include=[
            "backend.workers.tasks.main_image_tasks",
            "backend.workers.tasks.detail_page_tasks",
            "backend.workers.tasks.image_edit_tasks",
        ],
    )
    app.conf.update(
        task_serializer=settings.celery_task_serializer,
        accept_content=settings.celery_accept_content,
        result_serializer=settings.celery_result_serializer,
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=True,
        task_track_started=True,
        task_time_limit=settings.celery_task_time_limit_seconds,
        task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        broker_connection_retry_on_startup=True,
        timezone="UTC",
    )
    logger.info(
        format_log_event(
            "celery_app_configured",
            celery_enabled=settings.celery_enabled,
            task_always_eager=settings.celery_task_always_eager,
            broker_configured=bool(settings.resolve_celery_broker_url()),
            result_backend_configured=bool(settings.resolve_celery_result_backend()),
        )
    )
    return app


celery_app = create_celery_app()
