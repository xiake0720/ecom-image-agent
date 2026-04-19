"""主图 Celery 任务。"""

from __future__ import annotations

import logging

from backend.core.config import get_settings
from backend.services.main_image_service import MainImageService
from backend.services.task_execution_state_service import TaskExecutionStateService
from backend.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ecom.main_image.run")
def run_main_image_task(self, task_id: str) -> str:
    """按 task_id 从任务目录恢复并执行主图 workflow。"""

    settings = get_settings()
    state_service = TaskExecutionStateService()
    try:
        state_service.mark_running_sync(task_id=task_id, step="celery_main_image")
        service = MainImageService()
        prepared = service.load_prepared_task(task_id)
        service.run_prepared_task(prepared, raise_on_error=True)
        return task_id
    except Exception as exc:
        logger.exception("Celery 主图任务失败 task_id=%s", task_id)
        if self.request.retries < settings.celery_max_retries:
            retry_count = self.request.retries + 1
            state_service.mark_retrying_sync(task_id=task_id, exc=exc, retry_count=retry_count)
            raise self.retry(
                exc=exc,
                countdown=settings.celery_retry_countdown_seconds,
                max_retries=settings.celery_max_retries,
            )
        state_service.mark_failed_sync(task_id=task_id, exc=exc, retry_count=self.request.retries)
        raise
