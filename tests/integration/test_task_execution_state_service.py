from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select

from backend.core.config import reset_settings_cache
from backend.db.base import Base
from backend.db.enums import TaskEventType, TaskStatus, TaskType
from backend.db.models.task import Task, TaskEvent
from backend.db.models.user import User
from backend.db.session import dispose_async_engine, get_async_engine, get_async_session_factory
from backend.services.task_execution_state_service import TaskExecutionStateService


@pytest.fixture()
def state_service_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "state-service.sqlite3"
    monkeypatch.setenv("ECOM_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ECOM_AUTH_JWT_SECRET_KEY", "test-jwt-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_TOKEN_HASH_SECRET", "test-token-hash-secret-with-at-least-thirty-two-bytes")
    reset_settings_cache()
    asyncio.run(dispose_async_engine())

    async def _init_db() -> None:
        engine = get_async_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db())
    yield
    asyncio.run(dispose_async_engine())
    reset_settings_cache()


def test_task_execution_state_service_writes_status_and_events(state_service_db: None) -> None:
    task_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async def _seed() -> None:
        session_factory = get_async_session_factory()
        async with session_factory() as session:
            session.add(
                User(
                    id=user_id,
                    email="worker-state@example.com",
                    password_hash="hash",
                    nickname="worker-state",
                )
            )
            session.add(
                Task(
                    id=task_id,
                    user_id=user_id,
                    task_type=TaskType.MAIN_IMAGE.value,
                    status=TaskStatus.QUEUED.value,
                    title="worker state task",
                )
            )
            await session.commit()

    async def _read() -> tuple[Task, list[TaskEvent]]:
        session_factory = get_async_session_factory()
        async with session_factory() as session:
            task_row = await session.get(Task, task_id)
            assert task_row is not None
            events = list(
                (
                    await session.execute(
                        select(TaskEvent)
                        .where(TaskEvent.task_id == task_id)
                        .order_by(TaskEvent.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            return task_row, events

    asyncio.run(_seed())
    service = TaskExecutionStateService()

    asyncio.run(service.mark_running(task_id=str(task_id), step="celery_test"))
    task_row, events = asyncio.run(_read())
    assert task_row.status == TaskStatus.RUNNING.value
    assert task_row.current_step == "celery_test"
    assert task_row.started_at is not None
    assert [event.event_type for event in events] == [TaskEventType.TASK_RUNNING.value]

    asyncio.run(service.mark_retrying(task_id=str(task_id), exc=RuntimeError("provider timeout"), retry_count=1))
    task_row, events = asyncio.run(_read())
    assert task_row.status == TaskStatus.QUEUED.value
    assert task_row.current_step == "celery_retry"
    assert task_row.retry_count == 1
    assert task_row.error_message == "provider timeout"
    assert [event.event_type for event in events] == [TaskEventType.TASK_RUNNING.value, "task_retrying"]

    asyncio.run(service.mark_failed(task_id=str(task_id), exc=RuntimeError("provider timeout"), retry_count=1))
    task_row, events = asyncio.run(_read())
    assert task_row.status == TaskStatus.FAILED.value
    assert task_row.retry_count == 1
    assert task_row.finished_at is not None
    assert [event.event_type for event in events] == [
        TaskEventType.TASK_RUNNING.value,
        "task_retrying",
        TaskEventType.TASK_FAILED.value,
    ]
