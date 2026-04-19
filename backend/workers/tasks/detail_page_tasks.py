"""详情图 Celery 任务。"""

from __future__ import annotations

import logging

from backend.core.config import get_settings
from backend.services.detail_page_job_service import DetailPageJobService
from backend.services.task_execution_state_service import TaskExecutionStateService
from backend.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ecom.detail_page.run")
def run_detail_page_task(self, task_id: str, plan_only: bool = False) -> str:
    """按 task_id 从任务目录恢复并执行详情图 workflow。"""

    settings = get_settings()
    state_service = TaskExecutionStateService()
    try:
        state_service.mark_running_sync(task_id=task_id, step="celery_detail_page")
        service = DetailPageJobService()
        prepared = service.load_prepared(task_id=task_id, plan_only=plan_only)
        service.run_prepared(prepared, raise_on_error=True)
        return task_id
    except Exception as exc:
        logger.exception("Celery 详情图任务失败 task_id=%s", task_id)
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
