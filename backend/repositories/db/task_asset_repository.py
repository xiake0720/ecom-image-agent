"""任务素材 Repository。"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select

from backend.db.models.task import TaskAsset
from backend.repositories.db.base import SqlAlchemyRepository


class TaskAssetRepository(SqlAlchemyRepository):
    """处理 task_assets 表读写。"""

    async def get_by_id(self, asset_id: uuid.UUID) -> TaskAsset | None:
        stmt: Select[tuple[TaskAsset]] = select(TaskAsset).where(TaskAsset.id == asset_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_task(self, task_id: uuid.UUID) -> list[TaskAsset]:
        stmt: Select[tuple[TaskAsset]] = select(TaskAsset).where(TaskAsset.task_id == task_id).order_by(TaskAsset.sort_order.asc(), TaskAsset.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, asset: TaskAsset) -> TaskAsset:
        self.session.add(asset)
        return asset

    async def upsert(self, asset: TaskAsset) -> TaskAsset:
        return await self.session.merge(asset)
