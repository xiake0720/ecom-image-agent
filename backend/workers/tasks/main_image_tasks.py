"""Main image Celery tasks."""

from __future__ import annotations

import logging

from backend.core.config import get_settings
from backend.core.logging import format_log_event
from backend.services.main_image_service import MainImageService
from backend.services.task_execution_state_service import TaskExecutionStateService
from backend.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ecom.main_image.run")
def run_main_image_task(self, task_id: str) -> str:
    """Restore and execute one main-image workflow by task id."""

    settings = get_settings()
    state_service = TaskExecutionStateService()
    celery_task_id = getattr(self.request, "id", "")
    celery_task_name = getattr(self, "name", "ecom.main_image.run")
    retry_count = getattr(self.request, "retries", 0)
    user_id: str | None = None
    logger.info(
        format_log_event(
            "task_received",
            celery_task_name=celery_task_name,
            celery_task_id=celery_task_id,
            task_id=task_id,
            retry_count=retry_count,
        )
    )
    try:
        user_id = state_service.mark_running_sync(task_id=task_id, step="celery_main_image")
        logger.info(
            format_log_event(
                "task_started",
                celery_task_name=celery_task_name,
                celery_task_id=celery_task_id,
                task_id=task_id,
                user_id=user_id,
                retry_count=retry_count,
            )
        )
        service = MainImageService()
        prepared = service.load_prepared_task(task_id)
        service.run_prepared_task(prepared, raise_on_error=True)
        logger.info(
            format_log_event(
                "task_succeeded",
                celery_task_name=celery_task_name,
                celery_task_id=celery_task_id,
                task_id=task_id,
                user_id=user_id,
                retry_count=retry_count,
            )
        )
        return task_id
    except Exception as exc:
        logger.exception(
            format_log_event(
                "task_failed",
                celery_task_name=celery_task_name,
                celery_task_id=celery_task_id,
                task_id=task_id,
                user_id=user_id,
                retry_count=retry_count,
            )
        )
        if self.request.retries < settings.celery_max_retries:
            next_retry_count = self.request.retries + 1
            state_service.mark_retrying_sync(task_id=task_id, exc=exc, retry_count=next_retry_count)
            logger.warning(
                format_log_event(
                    "task_retrying",
                    celery_task_name=celery_task_name,
                    celery_task_id=celery_task_id,
                    task_id=task_id,
                    user_id=user_id,
                    retry_count=next_retry_count,
                )
            )
            raise self.retry(
                exc=exc,
                countdown=settings.celery_retry_countdown_seconds,
                max_retries=settings.celery_max_retries,
            )
        state_service.mark_failed_sync(task_id=task_id, exc=exc, retry_count=self.request.retries)
        raise
