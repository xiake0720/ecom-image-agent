"""用户模型。"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.db.enums import UserStatus
from backend.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from backend.db.types import INET_TYPE


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """平台用户。"""

    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("email"),
        sa.CheckConstraint(
            f"status IN ('{UserStatus.ACTIVE.value}', '{UserStatus.DISABLED.value}', '{UserStatus.SUSPENDED.value}')",
            name="users_status",
        ),
        sa.Index("ix_users_status_created_at", "status", "created_at"),
    )

    email: Mapped[str] = mapped_column(sa.String(length=255), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.String(length=255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(sa.String(length=100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(sa.String(length=500), nullable=True)
    status: Mapped[str] = mapped_column(
        sa.String(length=32),
        nullable=False,
        default=UserStatus.ACTIVE.value,
        server_default=UserStatus.ACTIVE.value,
    )
    email_verified: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default=sa.false())
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(INET_TYPE, nullable=True)
