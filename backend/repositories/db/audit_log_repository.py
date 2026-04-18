"""审计日志 Repository。"""

from __future__ import annotations

from backend.db.models.audit import AuditLog
from backend.repositories.db.base import SqlAlchemyRepository


class AuditLogRepository(SqlAlchemyRepository):
    """处理 audit_logs 表写入。"""

    def add(self, audit_log: AuditLog) -> AuditLog:
        self.session.add(audit_log)
        return audit_log
