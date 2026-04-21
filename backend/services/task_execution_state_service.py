"""Celery 任务执行状态写回服务。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import uuid

from backend.core.logging import format_log_event
from backend.db.enums import TaskEventLevel, TaskEventType, TaskStatus
from backend.db.models.task import TaskEvent
from backend.db.session import get_async_session_factory
from backend.repositories.db.task_db_repository import TaskDbRepository
from backend.repositories.db.task_event_repository import TaskEventRepository


logger = logging.getLogger(__name__)


class TaskExecutionStateService:
    """统一处理 worker 外层状态、错误和 retry 信息。"""

    def __init__(self) -> None:
        self.session_factory = get_async_session_factory()

    async def mark_running(self, *, task_id: str, step: str = "celery_worker") -> str | None:
        """标记任务已被 Celery worker 接收并开始执行。"""

        task_uuid = uuid.UUID(task_id)
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            event_repo = TaskEventRepository(session)
            task_row = await task_repo.get_by_id(task_uuid)
            if task_row is None:
                logger.warning(format_log_event("task_state_update_failed", task_id=task_id, step=step, reason="task_not_found"))
                return None

            task_row.status = TaskStatus.RUNNING.value
            task_row.current_step = step
            task_row.started_at = task_row.started_at or datetime.now(timezone.utc)
            await task_repo.upsert(task_row)
            event_repo.add(
                self._build_event(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_RUNNING.value,
                    level=TaskEventLevel.INFO.value,
                    step=step,
                    message="Celery worker 已开始执行任务",
                    payload={"status": TaskStatus.RUNNING.value},
                )
            )
            await session.commit()
            logger.info(format_log_event("task_state_running", task_id=task_id, user_id=task_row.user_id.hex, step=step))
            return task_row.user_id.hex

    async def mark_retrying(self, *, task_id: str, exc: Exception, retry_count: int) -> None:
        """记录任务即将重试，并把状态放回 queued。"""

        task_uuid = uuid.UUID(task_id)
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            event_repo = TaskEventRepository(session)
            task_row = await task_repo.get_by_id(task_uuid)
            if task_row is None:
                logger.warning(format_log_event("task_state_update_failed", task_id=task_id, state="retrying", reason="task_not_found"))
                return

            task_row.status = TaskStatus.QUEUED.value
            task_row.current_step = "celery_retry"
            task_row.retry_count = retry_count
            task_row.error_message = str(exc)
            await task_repo.upsert(task_row)
            event_repo.add(
                self._build_event(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type="task_retrying",
                    level=TaskEventLevel.WARNING.value,
                    step="celery_retry",
                    message="任务执行失败，等待 Celery 重试",
                    payload={"retry_count": retry_count, "error_message": str(exc)},
                )
            )
            await session.commit()
            logger.info(format_log_event("task_retrying", task_id=task_id, user_id=task_row.user_id.hex, retry_count=retry_count))

    async def mark_failed(self, *, task_id: str, exc: Exception, retry_count: int) -> None:
        """记录 Celery 终态失败，避免异常无声丢失。"""

        task_uuid = uuid.UUID(task_id)
        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            event_repo = TaskEventRepository(session)
            task_row = await task_repo.get_by_id(task_uuid)
            if task_row is None:
                logger.warning(format_log_event("task_state_update_failed", task_id=task_id, state="failed", reason="task_not_found"))
                return

            task_row.status = TaskStatus.FAILED.value
            task_row.current_step = task_row.current_step or "celery_worker"
            task_row.error_message = str(exc)
            task_row.retry_count = retry_count
            task_row.finished_at = datetime.now(timezone.utc)
            await task_repo.upsert(task_row)
            event_repo.add(
                self._build_event(
                    task_id=task_row.id,
                    user_id=task_row.user_id,
                    event_type=TaskEventType.TASK_FAILED.value,
                    level=TaskEventLevel.ERROR.value,
                    step=task_row.current_step,
                    message="Celery 任务执行失败",
                    payload={"retry_count": retry_count, "error_message": str(exc)},
                )
            )
            await session.commit()
            logger.info(format_log_event("task_failed", task_id=task_id, user_id=task_row.user_id.hex, retry_count=retry_count))

    def mark_running_sync(self, *, task_id: str, step: str = "celery_worker") -> str | None:
        """同步包装，供 Celery worker 调用。"""

        return asyncio.run(self.mark_running(task_id=task_id, step=step))

    def mark_retrying_sync(self, *, task_id: str, exc: Exception, retry_count: int) -> None:
        """同步包装，供 Celery worker 调用。"""

        asyncio.run(self.mark_retrying(task_id=task_id, exc=exc, retry_count=retry_count))

    def mark_failed_sync(self, *, task_id: str, exc: Exception, retry_count: int) -> None:
        """同步包装，供 Celery worker 调用。"""

        asyncio.run(self.mark_failed(task_id=task_id, exc=exc, retry_count=retry_count))

    def _build_event(
        self,
        *,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        event_type: str,
        level: str,
        step: str,
        message: str,
        payload: dict[str, object],
    ) -> TaskEvent:
        """构造任务事件对象，调用方负责提交事务。"""

        return TaskEvent(
            id=uuid.uuid4(),
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            level=level,
            step=step,
            message=message,
            payload=payload,
        )
