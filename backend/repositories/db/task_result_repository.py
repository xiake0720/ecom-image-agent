"""任务结果 Repository。"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select

from backend.db.models.task import TaskResult
from backend.repositories.db.base import SqlAlchemyRepository


class TaskResultRepository(SqlAlchemyRepository):
    """处理 task_results 表读写。"""

    async def get_by_id(self, result_id: uuid.UUID) -> TaskResult | None:
        stmt: Select[tuple[TaskResult]] = select(TaskResult).where(TaskResult.id == result_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, result_id: uuid.UUID, *, user_id: uuid.UUID) -> TaskResult | None:
        stmt: Select[tuple[TaskResult]] = select(TaskResult).where(
            TaskResult.id == result_id,
            TaskResult.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_task(self, task_id: uuid.UUID) -> list[TaskResult]:
        stmt: Select[tuple[TaskResult]] = select(TaskResult).where(TaskResult.task_id == task_id).order_by(TaskResult.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_task_for_user(self, task_id: uuid.UUID, *, user_id: uuid.UUID) -> list[TaskResult]:
        stmt: Select[tuple[TaskResult]] = (
            select(TaskResult)
            .where(TaskResult.task_id == task_id, TaskResult.user_id == user_id)
            .order_by(TaskResult.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_task_and_cos_key(self, task_id: uuid.UUID, *, cos_key: str) -> TaskResult | None:
        stmt: Select[tuple[TaskResult]] = select(TaskResult).where(
            TaskResult.task_id == task_id,
            TaskResult.cos_key == cos_key,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def next_version_no_for_source(self, source_result_id: uuid.UUID) -> int:
        """Return the next version number for edits derived from a source result."""

        stmt = select(func.max(TaskResult.version_no)).where(
            or_(TaskResult.id == source_result_id, TaskResult.parent_result_id == source_result_id)
        )
        result = await self.session.execute(stmt)
        current_max = result.scalar_one_or_none()
        return int(current_max or 1) + 1

    def add(self, task_result: TaskResult) -> TaskResult:
        self.session.add(task_result)
        return task_result

    async def upsert(self, task_result: TaskResult) -> TaskResult:
        return await self.session.merge(task_result)
