"""认证流程使用的持久化模型。"""

from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.db.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from backend.db.types import INET_TYPE, JSONB_TYPE, UUID_TYPE


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Refresh token 持久化记录。"""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        sa.UniqueConstraint("token_hash"),
        sa.Index("ix_refresh_tokens_user_id_revoked_at", "user_id", "revoked_at"),
        sa.Index("ix_refresh_tokens_user_id_expires_at", "user_id", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.String(length=255), nullable=False)
    device_id: Mapped[str | None] = mapped_column(sa.String(length=128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(sa.String(length=500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET_TYPE, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    replaced_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )


class IdempotencyKey(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """幂等键缓存记录。"""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "request_key"),
        sa.Index("ix_idempotency_keys_expires_at", "expires_at"),
        sa.Index("ix_idempotency_keys_user_id_endpoint", "user_id", "endpoint"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_key: Mapped[str] = mapped_column(sa.String(length=128), nullable=False)
    request_hash: Mapped[str] = mapped_column(sa.String(length=128), nullable=False)
    endpoint: Mapped[str] = mapped_column(sa.String(length=255), nullable=False)
    response_status: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
