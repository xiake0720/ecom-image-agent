"""任务主表 Repository。"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select

from backend.db.models.task import Task
from backend.repositories.db.base import SqlAlchemyRepository


class TaskDbRepository(SqlAlchemyRepository):
    """处理 tasks 表读写。"""

    async def get_by_id(self, task_id: uuid.UUID) -> Task | None:
        stmt: Select[tuple[Task]] = select(Task).where(Task.id == task_id, Task.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, task_id: uuid.UUID, *, user_id: uuid.UUID) -> Task | None:
        stmt: Select[tuple[Task]] = select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[Task]:
        stmt: Select[tuple[Task]] = select(Task).where(Task.user_id == user_id, Task.deleted_at.is_(None))
        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
        if status:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(
        self,
        user_id: uuid.UUID,
        *,
        task_type: str | None = None,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Task).where(Task.user_id == user_id, Task.deleted_at.is_(None))
        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
        if status:
            stmt = stmt.where(Task.status == status)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    def add(self, task: Task) -> Task:
        self.session.add(task)
        return task

    async def upsert(self, task: Task) -> Task:
        return await self.session.merge(task)
