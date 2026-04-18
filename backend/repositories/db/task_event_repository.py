"""任务事件 Repository。"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select

from backend.db.models.task import TaskEvent
from backend.repositories.db.base import SqlAlchemyRepository


class TaskEventRepository(SqlAlchemyRepository):
    """处理 task_events 表读写。"""

    async def get_by_id(self, event_id: uuid.UUID) -> TaskEvent | None:
        stmt: Select[tuple[TaskEvent]] = select(TaskEvent).where(TaskEvent.id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_task(self, task_id: uuid.UUID) -> list[TaskEvent]:
        stmt: Select[tuple[TaskEvent]] = select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_task_for_user(self, task_id: uuid.UUID, *, user_id: uuid.UUID) -> list[TaskEvent]:
        stmt: Select[tuple[TaskEvent]] = (
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id, TaskEvent.user_id == user_id)
            .order_by(TaskEvent.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, task_event: TaskEvent) -> TaskEvent:
        self.session.add(task_event)
        return task_event

    async def upsert(self, task_event: TaskEvent) -> TaskEvent:
        return await self.session.merge(task_event)
