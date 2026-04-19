"""Repository for image edit records."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select

from backend.db.models.task import ImageEdit
from backend.repositories.db.base import SqlAlchemyRepository


class ImageEditRepository(SqlAlchemyRepository):
    """Read and write `image_edits` rows."""

    async def get_by_id(self, edit_id: uuid.UUID) -> ImageEdit | None:
        stmt: Select[tuple[ImageEdit]] = select(ImageEdit).where(ImageEdit.id == edit_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_task_id(self, edit_task_id: uuid.UUID) -> ImageEdit | None:
        stmt: Select[tuple[ImageEdit]] = select(ImageEdit).where(ImageEdit.edit_task_id == edit_task_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_source_result_for_user(
        self,
        source_result_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
    ) -> list[ImageEdit]:
        stmt: Select[tuple[ImageEdit]] = (
            select(ImageEdit)
            .where(ImageEdit.source_result_id == source_result_id, ImageEdit.user_id == user_id)
            .order_by(ImageEdit.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, image_edit: ImageEdit) -> ImageEdit:
        self.session.add(image_edit)
        return image_edit

    async def upsert(self, image_edit: ImageEdit) -> ImageEdit:
        return await self.session.merge(image_edit)
