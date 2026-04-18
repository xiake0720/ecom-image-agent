"""Refresh token Repository。"""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Select, select, update

from backend.db.models.auth import RefreshToken
from backend.repositories.db.base import SqlAlchemyRepository


class RefreshTokenRepository(SqlAlchemyRepository):
    """处理 refresh_tokens 表读写。"""

    async def get_by_id(self, token_id: uuid.UUID) -> RefreshToken | None:
        stmt: Select[tuple[RefreshToken]] = select(RefreshToken).where(RefreshToken.id == token_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        stmt: Select[tuple[RefreshToken]] = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        return token

    async def revoke(self, token: RefreshToken, *, revoked_at: datetime) -> None:
        token.revoked_at = revoked_at
        await self.session.flush()

    async def rotate(self, current: RefreshToken, *, replacement: RefreshToken, revoked_at: datetime) -> None:
        current.revoked_at = revoked_at
        await self.session.flush()
        current.replaced_by_token_id = replacement.id
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID, *, revoked_at: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
