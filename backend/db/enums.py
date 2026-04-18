"""数据库层使用的集中枚举定义。"""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    SUSPENDED = "suspended"


class AuditAction(StrEnum):
    AUTH_REGISTER = "auth.register"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"


class TaskType(StrEnum):
    MAIN_IMAGE = "main_image"
    DETAIL_PAGE = "detail_page"
    IMAGE_EDIT = "image_edit"


class TaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL_FAILED = "partial_failed"
    CANCELLED = "cancelled"


class TaskResultStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskAssetScanStatus(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    BLOCKED = "blocked"


class TaskEventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TaskEventType(StrEnum):
    TASK_CREATED = "task_created"
    TASK_QUEUED = "task_queued"
    TASK_RUNNING = "task_running"
    TASK_SUCCEEDED = "task_succeeded"
    TASK_FAILED = "task_failed"
    TASK_PARTIAL_FAILED = "task_partial_failed"
    TASK_CANCELLED = "task_cancelled"
    TASK_RESULTS_SYNCED = "task_results_synced"


class TaskQcStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
