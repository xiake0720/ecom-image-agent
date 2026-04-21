"""Celery task for image edit execution."""

from __future__ import annotations

import logging

from backend.core.config import get_settings
from backend.core.logging import format_log_event
from backend.services.image_edit_service import ImageEditService
from backend.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ecom.image_edit.run")
def run_image_edit_task(self, edit_task_id: str) -> str:
    """Execute one image edit task by its image_edit task id."""

    settings = get_settings()
    celery_task_id = getattr(self.request, "id", "")
    celery_task_name = getattr(self, "name", "ecom.image_edit.run")
    retry_count = getattr(self.request, "retries", 0)
    logger.info(
        format_log_event(
            "task_received",
            celery_task_name=celery_task_name,
            celery_task_id=celery_task_id,
            task_id=edit_task_id,
            retry_count=retry_count,
        )
    )
    try:
        logger.info(
            format_log_event(
                "task_started",
                celery_task_name=celery_task_name,
                celery_task_id=celery_task_id,
                task_id=edit_task_id,
                retry_count=retry_count,
            )
        )
        ImageEditService().run_edit_task_sync(edit_task_id)
        logger.info(
            format_log_event(
                "task_succeeded",
                celery_task_name=celery_task_name,
                celery_task_id=celery_task_id,
                task_id=edit_task_id,
                retry_count=retry_count,
            )
        )
        return edit_task_id
    except Exception as exc:
        logger.exception(
            format_log_event(
                "task_failed",
                celery_task_name=celery_task_name,
                celery_task_id=celery_task_id,
                task_id=edit_task_id,
                retry_count=retry_count,
            )
        )
        if self.request.retries < settings.celery_max_retries:
            next_retry_count = self.request.retries + 1
            logger.warning(
                format_log_event(
                    "task_retrying",
                    celery_task_name=celery_task_name,
                    celery_task_id=celery_task_id,
                    task_id=edit_task_id,
                    retry_count=next_retry_count,
                )
            )
            raise self.retry(
                exc=exc,
                countdown=settings.celery_retry_countdown_seconds,
                max_retries=settings.celery_max_retries,
            )
        raise
