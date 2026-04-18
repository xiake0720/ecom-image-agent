"""数据库模型公共 mixin。"""

from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.types import UUID_TYPE


class UUIDPrimaryKeyMixin:
    """为模型提供 UUID 主键。"""

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)


class CreatedAtMixin:
    """为模型提供 created_at 字段。"""

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


class TimestampMixin(CreatedAtMixin):
    """为模型提供 created_at 和 updated_at 字段。"""

    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class SoftDeleteMixin:
    """为模型提供软删除时间字段。"""

    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
