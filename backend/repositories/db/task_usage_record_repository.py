"""任务资源消耗 Repository。"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select

from backend.db.models.task import TaskUsageRecord
from backend.repositories.db.base import SqlAlchemyRepository


class TaskUsageRecordRepository(SqlAlchemyRepository):
    """处理 task_usage_records 表读写。"""

    async def get_by_id(self, usage_record_id: uuid.UUID) -> TaskUsageRecord | None:
        stmt: Select[tuple[TaskUsageRecord]] = select(TaskUsageRecord).where(TaskUsageRecord.id == usage_record_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_task(self, task_id: uuid.UUID) -> list[TaskUsageRecord]:
        stmt: Select[tuple[TaskUsageRecord]] = select(TaskUsageRecord).where(TaskUsageRecord.task_id == task_id).order_by(TaskUsageRecord.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, usage_record: TaskUsageRecord) -> TaskUsageRecord:
        self.session.add(usage_record)
        return usage_record

    async def upsert(self, usage_record: TaskUsageRecord) -> TaskUsageRecord:
        return await self.session.merge(usage_record)
