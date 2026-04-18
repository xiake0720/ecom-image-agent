"""审计日志模型。"""

from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.db.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from backend.db.types import INET_TYPE, JSONB_TYPE, UUID_TYPE


class AuditLog(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """关键动作审计日志。"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        sa.Index("ix_audit_logs_user_id_created_at", "user_id", "created_at"),
        sa.Index("ix_audit_logs_action_created_at", "action", "created_at"),
        sa.Index("ix_audit_logs_request_id", "request_id"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(length=100), nullable=False)
    object_type: Mapped[str | None] = mapped_column(sa.String(length=50), nullable=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, nullable=True)
    request_id: Mapped[str | None] = mapped_column(sa.String(length=64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET_TYPE, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(sa.String(length=500), nullable=True)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
