"""initial auth and task database schema

Revision ID: 20260418_01
Revises:
Create Date: 2026-04-18 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_01"
down_revision = None
branch_labels = None
depends_on = None


UPDATED_AT_TABLES = ("users", "refresh_tokens", "tasks", "task_results", "task_assets")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled', 'suspended')", name="users_status"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index("ix_users_status_created_at", "users", ["status", "created_at"], unique=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["replaced_by_token_id"], ["refresh_tokens.id"], name=op.f("fk_refresh_tokens_replaced_by_token_id_refresh_tokens"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_user_id_revoked_at", "refresh_tokens", ["user_id", "revoked_at"], unique=False)
    op.create_index("ix_refresh_tokens_user_id_expires_at", "refresh_tokens", ["user_id", "expires_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("object_type", sa.String(length=50), nullable=True),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_audit_logs_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_user_id_created_at", "audit_logs", ["user_id", "created_at"], unique=False)
    op.create_index("ix_audit_logs_action_created_at", "audit_logs", ["action", "created_at"], unique=False)
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"], unique=False)

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_idempotency_keys_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_keys")),
        sa.UniqueConstraint("user_id", "request_key", name=op.f("uq_idempotency_keys_user_id_request_key")),
    )
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"], unique=False)
    op.create_index("ix_idempotency_keys_user_id_endpoint", "idempotency_keys", ["user_id", "endpoint"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("biz_id", sa.String(length=100), nullable=True),
        sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("progress_percent", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("runtime_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("task_type IN ('main_image', 'detail_page_v2', 'local_regenerate')", name="tasks_task_type"),
        sa.CheckConstraint("status IN ('pending', 'queued', 'running', 'review_required', 'succeeded', 'failed', 'canceled')", name="tasks_status"),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"], name=op.f("fk_tasks_parent_task_id_tasks"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_task_id"], ["tasks.id"], name=op.f("fk_tasks_source_task_id_tasks"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_tasks_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index("ix_tasks_user_id_created_at", "tasks", ["user_id", "created_at"], unique=False)
    op.create_index("ix_tasks_user_id_status", "tasks", ["user_id", "status"], unique=False)
    op.create_index("ix_tasks_user_id_task_type", "tasks", ["user_id", "task_type"], unique=False)
    op.create_index("ix_tasks_biz_id", "tasks", ["biz_id"], unique=False)
    op.create_index("ix_tasks_source_task_id", "tasks", ["source_task_id"], unique=False)
    op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"], unique=False)

    op.create_table(
        "task_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_type", sa.String(length=50), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("shot_no", sa.Integer(), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("parent_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="succeeded"),
        sa.Column("cos_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("prompt_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_final", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("render_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("qc_status", sa.String(length=32), nullable=True),
        sa.Column("qc_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('pending', 'succeeded', 'failed')", name="task_results_status"),
        sa.CheckConstraint("qc_status IS NULL OR qc_status IN ('pending', 'passed', 'review_required', 'failed')", name="task_results_qc_status"),
        sa.ForeignKeyConstraint(["parent_result_id"], ["task_results.id"], name=op.f("fk_task_results_parent_result_id_task_results"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_results_task_id_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_task_results_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_results")),
    )
    op.create_index("ix_task_results_task_id_created_at", "task_results", ["task_id", "created_at"], unique=False)
    op.create_index("ix_task_results_user_id_created_at", "task_results", ["user_id", "created_at"], unique=False)
    op.create_index("ix_task_results_task_id_result_type", "task_results", ["task_id", "result_type"], unique=False)
    op.create_index("ix_task_results_parent_result_id", "task_results", ["parent_result_id"], unique=False)
    op.create_index("ix_task_results_task_id_page_no_shot_no", "task_results", ["task_id", "page_no", "shot_no"], unique=False)

    op.create_table(
        "task_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_task_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("cos_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("scan_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("scan_status IN ('pending', 'clean', 'blocked')", name="task_assets_scan_status"),
        sa.ForeignKeyConstraint(["source_task_result_id"], ["task_results.id"], name=op.f("fk_task_assets_source_task_result_id_task_results"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_assets_task_id_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_task_assets_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_assets")),
    )
    op.create_index("ix_task_assets_task_id_sort_order", "task_assets", ["task_id", "sort_order"], unique=False)
    op.create_index("ix_task_assets_user_id_created_at", "task_assets", ["user_id", "created_at"], unique=False)
    op.create_index("ix_task_assets_task_id_role", "task_assets", ["task_id", "role"], unique=False)
    op.create_index("ix_task_assets_source_task_result_id", "task_assets", ["source_task_result_id"], unique=False)

    op.create_table(
        "task_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("step", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("level IN ('info', 'warning', 'error')", name="task_events_level"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_events_task_id_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_task_events_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_events")),
    )
    op.create_index("ix_task_events_task_id_created_at", "task_events", ["task_id", "created_at"], unique=False)
    op.create_index("ix_task_events_user_id_created_at", "task_events", ["user_id", "created_at"], unique=False)
    op.create_index("ix_task_events_task_id_event_type", "task_events", ["task_id", "event_type"], unique=False)

    op.create_table(
        "task_usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("action_name", sa.String(length=100), nullable=False),
        sa.Column("request_units", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_amount", sa.Numeric(12, 4), nullable=True),
        sa.Column("cost_currency", sa.String(length=10), nullable=False, server_default="CNY"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_usage_records_task_id_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_task_usage_records_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_usage_records")),
    )
    op.create_index("ix_task_usage_records_task_id_created_at", "task_usage_records", ["task_id", "created_at"], unique=False)
    op.create_index("ix_task_usage_records_user_id_created_at", "task_usage_records", ["user_id", "created_at"], unique=False)
    op.create_index("ix_task_usage_records_provider_type_provider_name", "task_usage_records", ["provider_type", "provider_name"], unique=False)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table_name in UPDATED_AT_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at_timestamp();
            """
        )


def downgrade() -> None:
    for table_name in UPDATED_AT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name};")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at_timestamp();")

    op.drop_index("ix_task_usage_records_provider_type_provider_name", table_name="task_usage_records")
    op.drop_index("ix_task_usage_records_user_id_created_at", table_name="task_usage_records")
    op.drop_index("ix_task_usage_records_task_id_created_at", table_name="task_usage_records")
    op.drop_table("task_usage_records")

    op.drop_index("ix_task_events_task_id_event_type", table_name="task_events")
    op.drop_index("ix_task_events_user_id_created_at", table_name="task_events")
    op.drop_index("ix_task_events_task_id_created_at", table_name="task_events")
    op.drop_table("task_events")

    op.drop_index("ix_task_assets_source_task_result_id", table_name="task_assets")
    op.drop_index("ix_task_assets_task_id_role", table_name="task_assets")
    op.drop_index("ix_task_assets_user_id_created_at", table_name="task_assets")
    op.drop_index("ix_task_assets_task_id_sort_order", table_name="task_assets")
    op.drop_table("task_assets")

    op.drop_index("ix_task_results_task_id_page_no_shot_no", table_name="task_results")
    op.drop_index("ix_task_results_parent_result_id", table_name="task_results")
    op.drop_index("ix_task_results_task_id_result_type", table_name="task_results")
    op.drop_index("ix_task_results_user_id_created_at", table_name="task_results")
    op.drop_index("ix_task_results_task_id_created_at", table_name="task_results")
    op.drop_table("task_results")

    op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
    op.drop_index("ix_tasks_source_task_id", table_name="tasks")
    op.drop_index("ix_tasks_biz_id", table_name="tasks")
    op.drop_index("ix_tasks_user_id_task_type", table_name="tasks")
    op.drop_index("ix_tasks_user_id_status", table_name="tasks")
    op.drop_index("ix_tasks_user_id_created_at", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_idempotency_keys_user_id_endpoint", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_expires_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_refresh_tokens_user_id_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id_revoked_at", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_status_created_at", table_name="users")
    op.drop_table("users")
