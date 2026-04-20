"""close v1 schema drift

Revision ID: 20260420_04
Revises: 20260418_03
Create Date: 2026-04-20 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_04"
down_revision = "20260418_03"
branch_labels = None
depends_on = None


GIN_INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    ("ix_audit_logs_payload_gin", "audit_logs", ["payload"]),
    ("ix_tasks_input_summary_gin", "tasks", ["input_summary"]),
    ("ix_tasks_params_gin", "tasks", ["params"]),
    ("ix_tasks_runtime_snapshot_gin", "tasks", ["runtime_snapshot"]),
    ("ix_tasks_result_summary_gin", "tasks", ["result_summary"]),
    ("ix_task_assets_metadata_gin", "task_assets", ["metadata"]),
    ("ix_task_results_prompt_plan_gin", "task_results", ["prompt_plan"]),
    ("ix_task_results_prompt_final_gin", "task_results", ["prompt_final"]),
    ("ix_task_results_render_meta_gin", "task_results", ["render_meta"]),
    ("ix_task_events_payload_gin", "task_events", ["payload"]),
    ("ix_task_usage_records_metadata_gin", "task_usage_records", ["metadata"]),
    ("ix_image_edits_selection_gin", "image_edits", ["selection"]),
    ("ix_image_edits_metadata_gin", "image_edits", ["metadata"]),
)


CHECK_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("tasks", "progress_percent_range", "progress_percent >= 0 AND progress_percent <= 100"),
    ("tasks", "retry_count_nonnegative", "retry_count >= 0"),
    ("task_assets", "role_nonempty", "length(role) > 0"),
    ("task_assets", "source_type_nonempty", "length(source_type) > 0"),
    ("task_assets", "size_bytes_nonnegative", "size_bytes >= 0"),
    ("task_assets", "width_nonnegative", "width IS NULL OR width >= 0"),
    ("task_assets", "height_nonnegative", "height IS NULL OR height >= 0"),
    ("task_assets", "duration_ms_nonnegative", "duration_ms IS NULL OR duration_ms >= 0"),
    ("task_assets", "sort_order_nonnegative", "sort_order >= 0"),
    ("task_results", "page_no_positive", "page_no IS NULL OR page_no > 0"),
    ("task_results", "shot_no_positive", "shot_no IS NULL OR shot_no > 0"),
    ("task_results", "version_no_positive", "version_no > 0"),
    ("task_results", "size_bytes_nonnegative", "size_bytes >= 0"),
    ("task_results", "width_nonnegative", "width IS NULL OR width >= 0"),
    ("task_results", "height_nonnegative", "height IS NULL OR height >= 0"),
    ("task_results", "qc_score_range", "qc_score IS NULL OR (qc_score >= 0 AND qc_score <= 100)"),
    ("task_usage_records", "request_units_nonnegative", "request_units IS NULL OR request_units >= 0"),
    ("task_usage_records", "prompt_tokens_nonnegative", "prompt_tokens IS NULL OR prompt_tokens >= 0"),
    ("task_usage_records", "completion_tokens_nonnegative", "completion_tokens IS NULL OR completion_tokens >= 0"),
    ("task_usage_records", "image_count_nonnegative", "image_count IS NULL OR image_count >= 0"),
    ("task_usage_records", "latency_ms_nonnegative", "latency_ms IS NULL OR latency_ms >= 0"),
    ("task_usage_records", "cost_amount_nonnegative", "cost_amount IS NULL OR cost_amount >= 0"),
)


def upgrade() -> None:
    op.add_column("tasks", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE tasks
        SET queued_at = created_at
        WHERE queued_at IS NULL
          AND status IN ('queued', 'running', 'succeeded', 'failed', 'partial_failed', 'cancelled')
        """
    )
    op.create_index("ix_tasks_user_id_queued_at", "tasks", ["user_id", "queued_at"], unique=False)

    for table_name, constraint_name, condition in CHECK_CONSTRAINTS:
        op.create_check_constraint(constraint_name, table_name, condition)

    for index_name, table_name, columns in GIN_INDEXES:
        op.create_index(index_name, table_name, columns, unique=False, postgresql_using="gin")


def downgrade() -> None:
    for index_name, table_name, _columns in reversed(GIN_INDEXES):
        op.drop_index(index_name, table_name=table_name)

    for table_name, constraint_name, _condition in reversed(CHECK_CONSTRAINTS):
        op.drop_constraint(constraint_name, table_name, type_="check")

    op.drop_index("ix_tasks_user_id_queued_at", table_name="tasks")
    op.drop_column("tasks", "queued_at")
