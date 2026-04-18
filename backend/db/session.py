"""异步数据库 Session 管理。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings


_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    """延迟创建全局异步 Engine。"""

    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        engine_kwargs: dict[str, object] = {
            "echo": settings.database_echo,
            "pool_pre_ping": True,
        }
        if settings.resolve_database_url().startswith("sqlite"):
            engine_kwargs.pop("pool_pre_ping", None)
        _async_engine = create_async_engine(settings.resolve_database_url(), **engine_kwargs)
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """返回异步 Session 工厂。"""

    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(get_async_engine(), expire_on_commit=False)
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：返回异步 Session。"""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session


async def dispose_async_engine() -> None:
    """释放全局 Engine 连接池。"""

    global _async_engine, _async_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
    _async_engine = None
    _async_session_factory = None
