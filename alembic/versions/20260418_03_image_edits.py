"""add image edit records

Revision ID: 20260418_03
Revises: 20260418_02
Create Date: 2026-04-19 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_03"
down_revision = "20260418_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_edits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edit_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edited_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("selection_type", sa.String(length=32), nullable=False, server_default="rectangle"),
        sa.Column("selection", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False, server_default="full_image_constrained_regeneration"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("selection_type IN ('rectangle', 'mask')", name="image_edits_selection_type"),
        sa.CheckConstraint("status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'cancelled')", name="image_edits_status"),
        sa.CheckConstraint(
            "mode IN ('native_inpainting', 'full_image_constrained_regeneration')",
            name="image_edits_mode",
        ),
        sa.ForeignKeyConstraint(
            ["source_result_id"],
            ["task_results.id"],
            name=op.f("fk_image_edits_source_result_id_task_results"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["edit_task_id"],
            ["tasks.id"],
            name=op.f("fk_image_edits_edit_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_image_edits_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["edited_result_id"],
            ["task_results.id"],
            name=op.f("fk_image_edits_edited_result_id_task_results"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_edits")),
    )
    op.create_index("ix_image_edits_source_result_id_created_at", "image_edits", ["source_result_id", "created_at"], unique=False)
    op.create_index("ix_image_edits_user_id_created_at", "image_edits", ["user_id", "created_at"], unique=False)
    op.create_index("ix_image_edits_edit_task_id", "image_edits", ["edit_task_id"], unique=False)
    op.create_index("ix_image_edits_edited_result_id", "image_edits", ["edited_result_id"], unique=False)
    op.execute(
        """
        CREATE TRIGGER trg_image_edits_updated_at
        BEFORE UPDATE ON image_edits
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at_timestamp();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_image_edits_updated_at ON image_edits;")
    op.drop_index("ix_image_edits_edited_result_id", table_name="image_edits")
    op.drop_index("ix_image_edits_edit_task_id", table_name="image_edits")
    op.drop_index("ix_image_edits_user_id_created_at", table_name="image_edits")
    op.drop_index("ix_image_edits_source_result_id_created_at", table_name="image_edits")
    op.drop_table("image_edits")
