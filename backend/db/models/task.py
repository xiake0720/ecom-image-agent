"""任务域数据库模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.db.enums import (
    ImageEditMode,
    ImageEditSelectionType,
    ImageEditStatus,
    TaskAssetScanStatus,
    TaskEventLevel,
    TaskQcStatus,
    TaskResultStatus,
    TaskStatus,
    TaskType,
)
from backend.db.models.mixins import CreatedAtMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from backend.db.types import JSONB_TYPE, UUID_TYPE


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """任务主表。"""

    __tablename__ = "tasks"
    __table_args__ = (
        sa.CheckConstraint(
            "task_type IN ('main_image', 'detail_page', 'image_edit')",
            name="tasks_task_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'partial_failed', 'cancelled')",
            name="tasks_status",
        ),
        sa.Index("ix_tasks_user_id_created_at", "user_id", "created_at"),
        sa.Index("ix_tasks_user_id_status", "user_id", "status"),
        sa.Index("ix_tasks_user_id_task_type", "user_id", "task_type"),
        sa.Index("ix_tasks_biz_id", "biz_id"),
        sa.Index("ix_tasks_source_task_id", "source_task_id"),
        sa.Index("ix_tasks_parent_task_id", "parent_task_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    task_type: Mapped[str] = mapped_column(sa.String(length=32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(length=32), nullable=False, default=TaskStatus.PENDING.value, server_default=TaskStatus.PENDING.value)
    title: Mapped[str | None] = mapped_column(sa.String(length=255), nullable=True)
    platform: Mapped[str | None] = mapped_column(sa.String(length=50), nullable=True)
    biz_id: Mapped[str | None] = mapped_column(sa.String(length=100), nullable=True)
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    current_step: Mapped[str | None] = mapped_column(sa.String(length=100), nullable=True)
    progress_percent: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False, default=0, server_default="0")
    input_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    params: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    runtime_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    result_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    error_code: Mapped[str | None] = mapped_column(sa.String(length=100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    retry_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class TaskResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """任务产出结果。"""

    __tablename__ = "task_results"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="task_results_status",
        ),
        sa.CheckConstraint(
            "qc_status IS NULL OR qc_status IN ('pending', 'passed', 'review_required', 'failed')",
            name="task_results_qc_status",
        ),
        sa.Index("ix_task_results_task_id_created_at", "task_id", "created_at"),
        sa.Index("ix_task_results_user_id_created_at", "user_id", "created_at"),
        sa.Index("ix_task_results_task_id_result_type", "task_id", "result_type"),
        sa.Index("ix_task_results_parent_result_id", "parent_result_id"),
        sa.Index("ix_task_results_task_id_page_no_shot_no", "task_id", "page_no", "shot_no"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    result_type: Mapped[str] = mapped_column(sa.String(length=50), nullable=False)
    page_no: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    shot_no: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    version_no: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=1, server_default="1")
    parent_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, sa.ForeignKey("task_results.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(length=32), nullable=False, default=TaskResultStatus.SUCCEEDED.value, server_default=TaskResultStatus.SUCCEEDED.value)
    cos_key: Mapped[str] = mapped_column(sa.String(length=500), nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.String(length=100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(length=64), nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    height: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    prompt_plan: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    prompt_final: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    render_meta: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)
    qc_status: Mapped[str | None] = mapped_column(sa.String(length=32), nullable=True)
    qc_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2), nullable=True)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True, server_default=sa.true())


class TaskAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """任务输入或中间素材。"""

    __tablename__ = "task_assets"
    __table_args__ = (
        sa.CheckConstraint(
            "scan_status IN ('pending', 'clean', 'blocked')",
            name="task_assets_scan_status",
        ),
        sa.Index("ix_task_assets_task_id_sort_order", "task_id", "sort_order"),
        sa.Index("ix_task_assets_user_id_created_at", "user_id", "created_at"),
        sa.Index("ix_task_assets_task_id_role", "task_id", "role"),
        sa.Index("ix_task_assets_source_task_result_id", "source_task_result_id"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(length=50), nullable=False)
    source_type: Mapped[str] = mapped_column(sa.String(length=50), nullable=False)
    source_task_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, sa.ForeignKey("task_results.id", ondelete="SET NULL"), nullable=True)
    file_name: Mapped[str | None] = mapped_column(sa.String(length=255), nullable=True)
    cos_key: Mapped[str] = mapped_column(sa.String(length=500), nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.String(length=100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(length=64), nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    height: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    scan_status: Mapped[str] = mapped_column(sa.String(length=32), nullable=False, default=TaskAssetScanStatus.PENDING.value, server_default=TaskAssetScanStatus.PENDING.value)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB_TYPE, nullable=True)
    sort_order: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")


class TaskEvent(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """任务事件流水。"""

    __tablename__ = "task_events"
    __table_args__ = (
        sa.CheckConstraint(
            "level IN ('info', 'warning', 'error')",
            name="task_events_level",
        ),
        sa.Index("ix_task_events_task_id_created_at", "task_id", "created_at"),
        sa.Index("ix_task_events_user_id_created_at", "user_id", "created_at"),
        sa.Index("ix_task_events_task_id_event_type", "task_id", "event_type"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(length=50), nullable=False)
    level: Mapped[str] = mapped_column(sa.String(length=20), nullable=False, default=TaskEventLevel.INFO.value, server_default=TaskEventLevel.INFO.value)
    step: Mapped[str | None] = mapped_column(sa.String(length=100), nullable=True)
    message: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB_TYPE, nullable=True)


class TaskUsageRecord(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """任务资源使用记录。"""

    __tablename__ = "task_usage_records"
    __table_args__ = (
        sa.Index("ix_task_usage_records_task_id_created_at", "task_id", "created_at"),
        sa.Index("ix_task_usage_records_user_id_created_at", "user_id", "created_at"),
        sa.Index("ix_task_usage_records_provider_type_provider_name", "provider_type", "provider_name"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    provider_type: Mapped[str] = mapped_column(sa.String(length=50), nullable=False)
    provider_name: Mapped[str] = mapped_column(sa.String(length=100), nullable=False)
    model_name: Mapped[str | None] = mapped_column(sa.String(length=100), nullable=True)
    action_name: Mapped[str] = mapped_column(sa.String(length=100), nullable=False)
    request_units: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    image_count: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    cost_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 4), nullable=True)
    cost_currency: Mapped[str] = mapped_column(sa.String(length=10), nullable=False, default="CNY", server_default="CNY")
    success: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True, server_default=sa.true())
    error_code: Mapped[str | None] = mapped_column(sa.String(length=100), nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB_TYPE, nullable=True)


class ImageEdit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single-result edit request and execution record."""

    __tablename__ = "image_edits"
    __table_args__ = (
        sa.CheckConstraint(
            "selection_type IN ('rectangle', 'mask')",
            name="image_edits_selection_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="image_edits_status",
        ),
        sa.CheckConstraint(
            "mode IN ('native_inpainting', 'full_image_constrained_regeneration')",
            name="image_edits_mode",
        ),
        sa.Index("ix_image_edits_source_result_id_created_at", "source_result_id", "created_at"),
        sa.Index("ix_image_edits_user_id_created_at", "user_id", "created_at"),
        sa.Index("ix_image_edits_edit_task_id", "edit_task_id"),
        sa.Index("ix_image_edits_edited_result_id", "edited_result_id"),
    )

    source_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("task_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    edit_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    edited_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("task_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    selection_type: Mapped[str] = mapped_column(
        sa.String(length=32),
        nullable=False,
        default=ImageEditSelectionType.RECTANGLE.value,
        server_default=ImageEditSelectionType.RECTANGLE.value,
    )
    selection: Mapped[dict[str, object]] = mapped_column(JSONB_TYPE, nullable=False)
    instruction: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    mode: Mapped[str] = mapped_column(
        sa.String(length=64),
        nullable=False,
        default=ImageEditMode.FULL_IMAGE_CONSTRAINED_REGENERATION.value,
        server_default=ImageEditMode.FULL_IMAGE_CONSTRAINED_REGENERATION.value,
    )
    status: Mapped[str] = mapped_column(
        sa.String(length=32),
        nullable=False,
        default=ImageEditStatus.QUEUED.value,
        server_default=ImageEditStatus.QUEUED.value,
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB_TYPE, nullable=True)
