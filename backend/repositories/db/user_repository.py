"""用户 Repository。"""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Select, select

from backend.db.models.user import User
from backend.repositories.db.base import SqlAlchemyRepository


class UserRepository(SqlAlchemyRepository):
    """处理 users 表读写。"""

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt: Select[tuple[User]] = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt: Select[tuple[User]] = select(User).where(User.email == email, User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, user: User) -> User:
        self.session.add(user)
        return user

    async def touch_last_login(self, user: User, *, login_at: datetime, login_ip: str | None) -> None:
        user.last_login_at = login_at
        user.last_login_ip = login_ip
        await self.session.flush()
