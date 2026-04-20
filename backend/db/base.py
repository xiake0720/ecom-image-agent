"""SQLAlchemy Declarative Base。"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有数据库模型的基类。"""

    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


from backend.db.models import AuditLog, IdempotencyKey, ImageEdit, RefreshToken, Task, TaskAsset, TaskEvent, TaskResult, TaskUsageRecord, User  # noqa: E402,F401
