"""Verify the final v1 schema on a real PostgreSQL database.

The target database must be dedicated to this verification when
`--reset-schema` is used because the script drops and recreates `public`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine


def _require_postgres_url(database_url: str) -> None:
    if not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("database_url must start with postgresql+asyncpg://")


async def reset_public_schema(database_url: str) -> None:
    engine = create_async_engine(database_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


async def run_minimal_crud(database_url: str) -> None:
    engine = create_async_engine(database_url)
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    result_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    edit_task_id = uuid.uuid4()
    edit_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    idem_id = uuid.uuid4()

    async with engine.begin() as connection:
        version_num = int((await connection.execute(text("SHOW server_version_num"))).scalar_one())
        if version_num < 160000:
            raise RuntimeError(f"PostgreSQL 16+ is required, got server_version_num={version_num}")

        await connection.execute(
            text(
                """
                INSERT INTO users (id, email, password_hash, status, email_verified)
                VALUES (:id, :email, :password_hash, 'active', true)
                """
            ),
            {"id": user_id, "email": f"schema-{user_id.hex}@example.com", "password_hash": "hash"},
        )
        await connection.execute(
            text(
                """
                INSERT INTO idempotency_keys
                    (id, user_id, request_key, request_hash, endpoint, expires_at)
                VALUES
                    (:id, :user_id, 'phase2-key', 'hash', '/api/test', now() + interval '1 hour')
                """
            ),
            {"id": idem_id, "user_id": user_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO audit_logs
                    (id, user_id, action, object_type, object_id, request_id, payload)
                VALUES
                    (:id, :user_id, 'schema.verify', 'task', :object_id, 'req-schema', '{"ok": true}'::jsonb)
                """
            ),
            {"id": audit_id, "user_id": user_id, "object_id": task_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO tasks
                    (id, user_id, task_type, status, title, progress_percent, retry_count, queued_at,
                     input_summary, params, runtime_snapshot, result_summary)
                VALUES
                    (:id, :user_id, 'main_image', 'queued', 'schema task', 0, 0, now(),
                     '{"kind": "test"}'::jsonb, '{"shots": 1}'::jsonb,
                     '{"status": "queued"}'::jsonb, '{"result_count": 0}'::jsonb)
                """
            ),
            {"id": task_id, "user_id": user_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO task_results
                    (id, task_id, user_id, result_type, shot_no, status, cos_key,
                     mime_type, size_bytes, sha256, width, height, render_meta)
                VALUES
                    (:id, :task_id, :user_id, 'main_image', 1, 'succeeded',
                     'final/result.png', 'image/png', 68, :sha256, 1, 1,
                     '{"source": "schema_test"}'::jsonb)
                """
            ),
            {"id": result_id, "task_id": task_id, "user_id": user_id, "sha256": "a" * 64},
        )
        await connection.execute(
            text(
                """
                INSERT INTO task_assets
                    (id, task_id, user_id, role, source_type, file_name, cos_key,
                     mime_type, size_bytes, sha256, width, height, scan_status, metadata)
                VALUES
                    (:id, :task_id, :user_id, 'white_bg', 'upload', 'input.png',
                     'inputs/input.png', 'image/png', 68, :sha256, 1, 1, 'pending',
                     '{"upload_status": "uploaded"}'::jsonb)
                """
            ),
            {"id": asset_id, "task_id": task_id, "user_id": user_id, "sha256": "b" * 64},
        )
        await connection.execute(
            text(
                """
                INSERT INTO tasks
                    (id, user_id, task_type, status, title, progress_percent, retry_count,
                     queued_at, source_task_id, parent_task_id)
                VALUES
                    (:id, :user_id, 'image_edit', 'queued', 'edit task', 0, 0,
                     now(), :source_task_id, :parent_task_id)
                """
            ),
            {
                "id": edit_task_id,
                "user_id": user_id,
                "source_task_id": task_id,
                "parent_task_id": task_id,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO image_edits
                    (id, source_result_id, edit_task_id, user_id, selection_type,
                     selection, instruction, mode, status, metadata)
                VALUES
                    (:id, :source_result_id, :edit_task_id, :user_id, 'rectangle',
                     '{"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}'::jsonb,
                     'make it brighter', 'full_image_constrained_regeneration',
                     'queued', '{"source": "schema_test"}'::jsonb)
                """
            ),
            {
                "id": edit_id,
                "source_result_id": result_id,
                "edit_task_id": edit_task_id,
                "user_id": user_id,
            },
        )

        count = (await connection.execute(text("SELECT count(*) FROM image_edits"))).scalar_one()
        if int(count) != 1:
            raise RuntimeError("image_edits CRUD verification failed")

        savepoint = await connection.begin_nested()
        try:
            await connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, password_hash, status)
                    VALUES (:id, :email, 'hash', 'pending_verification')
                    """
                ),
                {"id": uuid.uuid4(), "email": f"bad-{user_id.hex}@example.com"},
            )
        except IntegrityError:
            await savepoint.rollback()
        else:
            await savepoint.commit()
            raise RuntimeError("users.status check did not reject pending_verification")

    await engine.dispose()


def alembic_config(database_url: str) -> Config:
    os.environ["ECOM_DATABASE_URL"] = database_url
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def run_verification(*, database_url: str, reset_schema: bool = False, downgrade_check: bool = True) -> None:
    _require_postgres_url(database_url)
    if reset_schema:
        asyncio.run(reset_public_schema(database_url))

    config = alembic_config(database_url)
    command.upgrade(config, "head")
    asyncio.run(run_minimal_crud(database_url))
    if downgrade_check:
        command.downgrade(config, "-1")
        command.upgrade(config, "head")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Alembic head on PostgreSQL 16.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("ECOM_TEST_POSTGRES_URL") or os.getenv("ECOM_DATABASE_URL"),
        help="Dedicated PostgreSQL test URL, e.g. postgresql+asyncpg://user:pass@host:5432/db.",
    )
    parser.add_argument(
        "--reset-schema",
        action="store_true",
        help="Drop and recreate public schema before running migrations. Use only on a dedicated test database.",
    )
    parser.add_argument("--skip-downgrade", action="store_true", help="Skip downgrade -1 / upgrade head reversibility check.")
    args = parser.parse_args()

    if not args.database_url:
        parser.error("--database-url or ECOM_TEST_POSTGRES_URL is required")

    run_verification(
        database_url=args.database_url,
        reset_schema=args.reset_schema,
        downgrade_check=not args.skip_downgrade,
    )
    print("PostgreSQL schema verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
