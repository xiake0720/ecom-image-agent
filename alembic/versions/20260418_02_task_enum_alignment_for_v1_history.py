"""align task enums for v1 task history

Revision ID: 20260418_02
Revises: 20260418_01
Create Date: 2026-04-18 20:30:00
"""

from __future__ import annotations

from alembic import op


revision = "20260418_02"
down_revision = "20260418_01"
branch_labels = None
depends_on = None


OLD_TASK_TYPE_CONSTRAINT = "task_type IN ('main_image', 'detail_page_v2', 'local_regenerate')"
NEW_TASK_TYPE_CONSTRAINT = "task_type IN ('main_image', 'detail_page', 'image_edit')"
OLD_TASK_STATUS_CONSTRAINT = "status IN ('pending', 'queued', 'running', 'review_required', 'succeeded', 'failed', 'canceled')"
NEW_TASK_STATUS_CONSTRAINT = "status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'partial_failed', 'cancelled')"


def upgrade() -> None:
    op.execute("UPDATE tasks SET task_type = 'detail_page' WHERE task_type = 'detail_page_v2';")
    op.execute("UPDATE tasks SET task_type = 'image_edit' WHERE task_type = 'local_regenerate';")
    op.execute("UPDATE tasks SET status = 'partial_failed' WHERE status = 'review_required';")
    op.execute("UPDATE tasks SET status = 'cancelled' WHERE status = 'canceled';")

    op.drop_constraint("tasks_task_type", "tasks", type_="check")
    op.drop_constraint("tasks_status", "tasks", type_="check")
    op.create_check_constraint("tasks_task_type", "tasks", NEW_TASK_TYPE_CONSTRAINT)
    op.create_check_constraint("tasks_status", "tasks", NEW_TASK_STATUS_CONSTRAINT)


def downgrade() -> None:
    op.execute("UPDATE tasks SET task_type = 'detail_page_v2' WHERE task_type = 'detail_page';")
    op.execute("UPDATE tasks SET task_type = 'local_regenerate' WHERE task_type = 'image_edit';")
    op.execute("UPDATE tasks SET status = 'review_required' WHERE status = 'partial_failed';")
    op.execute("UPDATE tasks SET status = 'canceled' WHERE status = 'cancelled';")

    op.drop_constraint("tasks_task_type", "tasks", type_="check")
    op.drop_constraint("tasks_status", "tasks", type_="check")
    op.create_check_constraint("tasks_task_type", "tasks", OLD_TASK_TYPE_CONSTRAINT)
    op.create_check_constraint("tasks_status", "tasks", OLD_TASK_STATUS_CONSTRAINT)
