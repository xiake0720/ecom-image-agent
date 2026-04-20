"""Best-effort audit log writer for security-relevant actions."""

from __future__ import annotations

import logging
import uuid

from backend.core.request_context import RequestContext
from backend.db.models.audit import AuditLog
from backend.db.models.user import User
from backend.db.session import get_async_session_factory
from backend.repositories.db.audit_log_repository import AuditLogRepository


logger = logging.getLogger(__name__)


async def write_audit_log(
    *,
    action: str,
    context: RequestContext,
    current_user: User | None = None,
    user_id: uuid.UUID | None = None,
    object_type: str | None = None,
    object_id: uuid.UUID | str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    """Persist an audit log entry without blocking the primary business flow.

    Login/logout already write audit records inside AuthService transactions.
    Other first-release security events use this helper after their main action
    succeeds.  Audit failures are logged with request_id for follow-up.
    """

    resolved_object_id = _parse_object_id(object_id)
    resolved_user_id = user_id or (current_user.id if current_user is not None else None)
    audit_log = AuditLog(
        id=uuid.uuid4(),
        user_id=resolved_user_id,
        action=action,
        object_type=object_type,
        object_id=resolved_object_id,
        request_id=context.request_id,
        ip_address=context.ip_address,
        user_agent=context.user_agent,
        payload=payload,
    )

    session_factory = get_async_session_factory()
    try:
        async with session_factory() as session:
            AuditLogRepository(session).add(audit_log)
            await session.commit()
    except Exception as exc:
        logger.exception(
            "audit_log_write_failed request_id=%s action=%s object_type=%s object_id=%s error=%s",
            context.request_id,
            action,
            object_type,
            object_id,
            exc,
        )


def _parse_object_id(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
