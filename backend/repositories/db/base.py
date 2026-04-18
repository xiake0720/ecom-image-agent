"""数据库 Repository 基类。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyRepository:
    """封装共享的 AsyncSession 引用。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
