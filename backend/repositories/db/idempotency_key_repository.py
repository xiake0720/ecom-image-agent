"""幂等键 Repository。"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select

from backend.db.models.auth import IdempotencyKey
from backend.repositories.db.base import SqlAlchemyRepository


class IdempotencyKeyRepository(SqlAlchemyRepository):
    """处理 idempotency_keys 表读写。"""

    async def get_by_user_and_key(self, user_id: uuid.UUID, request_key: str) -> IdempotencyKey | None:
        stmt: Select[tuple[IdempotencyKey]] = select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.request_key == request_key,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, idempotency_key: IdempotencyKey) -> IdempotencyKey:
        self.session.add(idempotency_key)
        return idempotency_key
