"""Celery task for image edit execution."""

from __future__ import annotations

import logging

from backend.core.config import get_settings
from backend.services.image_edit_service import ImageEditService
from backend.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ecom.image_edit.run")
def run_image_edit_task(self, edit_task_id: str) -> str:
    """Execute one image edit task by its image_edit task id."""

    settings = get_settings()
    try:
        ImageEditService().run_edit_task_sync(edit_task_id)
        return edit_task_id
    except Exception as exc:
        logger.exception("Celery image edit task failed edit_task_id=%s", edit_task_id)
        if self.request.retries < settings.celery_max_retries:
            raise self.retry(
                exc=exc,
                countdown=settings.celery_retry_countdown_seconds,
                max_retries=settings.celery_max_retries,
            )
        raise
