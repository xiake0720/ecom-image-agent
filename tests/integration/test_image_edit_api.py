from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.core.config import reset_settings_cache
from backend.db.base import Base
from backend.db.enums import TaskResultStatus, TaskStatus, TaskType
from backend.db.models.task import Task, TaskResult
from backend.db.session import dispose_async_engine, get_async_engine, get_async_session_factory
from backend.engine.core import config as engine_config
from backend.repositories.db.user_repository import UserRepository
from backend.schemas.image_edit import ImageEditCreateRequest


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wIAAgMBAp9K1T0AAAAASUVORK5CYII="
)


@pytest.fixture()
def image_edit_client(tmp_path, monkeypatch):
    db_path = tmp_path / "image-edit-test.sqlite3"
    outputs_dir = tmp_path / "outputs"
    tasks_dir = outputs_dir / "tasks"
    storage_dir = tmp_path / "storage"

    monkeypatch.setenv("ECOM_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ECOM_AUTH_JWT_SECRET_KEY", "test-jwt-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_TOKEN_HASH_SECRET", "test-token-hash-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_REFRESH_COOKIE_SECURE", "false")
    monkeypatch.setenv("ECOM_CORS_ORIGINS", '["http://testserver"]')
    monkeypatch.setenv("ECOM_STORAGE_ROOT", str(storage_dir))
    monkeypatch.setenv("ECOM_OUTPUTS_ROOT", str(tasks_dir))
    monkeypatch.setenv("ECOM_CELERY_ENABLED", "true")
    monkeypatch.setenv("ECOM_CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("ECOM_CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_ENABLE_MOCK_PROVIDERS", "true")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_TASKS_DIR", str(tasks_dir))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_CACHE_DIR", str(outputs_dir / "cache"))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_EXPORTS_DIR", str(outputs_dir / "exports"))

    reset_settings_cache()
    engine_config.get_settings.cache_clear()
    asyncio.run(dispose_async_engine())

    async def _init_db() -> None:
        engine = get_async_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db())

    module_names = [
        "backend.services.image_edit_service",
        "backend.workers.tasks.image_edit_tasks",
        "backend.api.v1.image_edits",
        "backend.api.v1.tasks",
        "backend.api.v1",
        "backend.main",
    ]
    loaded_modules = {}
    for name in module_names:
        module = importlib.import_module(name)
        loaded_modules[name] = importlib.reload(module)

    image_edit_calls: list[str] = []
    image_edit_tasks = loaded_modules["backend.workers.tasks.image_edit_tasks"]
    monkeypatch.setattr(image_edit_tasks.run_image_edit_task, "delay", lambda task_id: image_edit_calls.append(task_id))

    backend_main = loaded_modules["backend.main"]
    with TestClient(backend_main.app) as client:
        yield client, image_edit_calls, tasks_dir

    asyncio.run(dispose_async_engine())
    reset_settings_cache()
    engine_config.get_settings.cache_clear()


def test_result_edit_api_is_user_scoped_and_enqueues_celery(image_edit_client: tuple[TestClient, list[str], Path]) -> None:
    client, image_edit_calls, tasks_dir = image_edit_client
    token_a = _register_and_get_token(client, "edit-a@example.com")
    token_b = _register_and_get_token(client, "edit-b@example.com")
    source_result_id = asyncio.run(_create_source_result("edit-a@example.com", tasks_dir))

    response = client.post(
        f"/api/v1/results/{source_result_id}/edits",
        headers={"Authorization": f"Bearer {token_a}"},
        json=_edit_payload(),
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["source_result_id"] == source_result_id.hex
    assert body["status"] == "queued"
    assert body["mode"] == "full_image_constrained_regeneration"
    assert image_edit_calls == [body["edit_task_id"]]

    history_response = client.get(
        f"/api/v1/results/{source_result_id}/edits",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert history_response.status_code == 200
    assert len(history_response.json()["data"]["items"]) == 1

    other_user_history = client.get(
        f"/api/v1/results/{source_result_id}/edits",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_user_history.status_code == 404

    task_list = client.get(
        "/api/v1/tasks?task_type=image_edit",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert task_list.status_code == 200
    assert task_list.json()["data"]["total"] == 1


def test_image_edit_execution_writes_derived_result(image_edit_client: tuple[TestClient, list[str], Path]) -> None:
    client, _image_edit_calls, tasks_dir = image_edit_client
    token = _register_and_get_token(client, "edit-run@example.com")
    source_result_id = asyncio.run(_create_source_result("edit-run@example.com", tasks_dir))
    user = asyncio.run(_get_user("edit-run@example.com"))

    from backend.services.image_edit_service import ImageEditService

    service = ImageEditService()
    created = asyncio.run(
        service.create_edit(
            current_user=user,
            result_id=source_result_id.hex,
            payload=ImageEditCreateRequest.model_validate(_edit_payload()),
            dispatch=False,
        )
    )
    service.run_edit_task_sync(created.edit_task_id)

    history_response = client.get(
        f"/api/v1/results/{source_result_id}/edits",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history_response.status_code == 200
    edit = history_response.json()["data"]["items"][0]
    assert edit["status"] == "succeeded"
    assert edit["edited_result"]["parent_result_id"] == source_result_id.hex
    assert edit["edited_result"]["result_type"] == "image_edit"
    assert edit["edited_result"]["version_no"] == 2
    assert edit["edited_result"]["render_meta"]["mode"] == "full_image_constrained_regeneration"

    result_path = tasks_dir / created.edit_task_id / "final" / "edited_result.png"
    assert result_path.exists()

    task_results = client.get(
        f"/api/v1/tasks/{created.edit_task_id}/results",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert task_results.status_code == 200
    assert len(task_results.json()["data"]["items"]) == 1


def _register_and_get_token(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "nickname": email.split("@")[0]},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _edit_payload() -> dict[str, object]:
    return {
        "selection_type": "rectangle",
        "selection": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.4, "unit": "ratio"},
        "instruction": "保留主体，仅优化选中区域的文字和光影",
    }


async def _create_source_result(email: str, tasks_dir: Path) -> uuid.UUID:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        user = await UserRepository(session).get_by_email(email)
        assert user is not None
        task_id = uuid.uuid4()
        result_id = uuid.uuid4()
        task_dir = tasks_dir / task_id.hex
        final_dir = task_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        source_path = final_dir / "source.png"
        source_path.write_bytes(PNG_BYTES)
        session.add(
            Task(
                id=task_id,
                user_id=user.id,
                task_type=TaskType.MAIN_IMAGE.value,
                status=TaskStatus.SUCCEEDED.value,
                title="Editable Source",
                platform="tmall",
                progress_percent=100,
                result_summary={"result_count": 1, "primary_result_id": result_id.hex},
            )
        )
        session.add(
            TaskResult(
                id=result_id,
                task_id=task_id,
                user_id=user.id,
                result_type=TaskType.MAIN_IMAGE.value,
                version_no=1,
                status=TaskResultStatus.SUCCEEDED.value,
                cos_key="final/source.png",
                mime_type="image/png",
                size_bytes=source_path.stat().st_size,
                sha256=hashlib.sha256(PNG_BYTES).hexdigest(),
                width=1,
                height=1,
                render_meta={"source": "local_file", "local_relative_path": "final/source.png"},
                is_primary=True,
            )
        )
        await session.commit()
        return result_id


async def _get_user(email: str):
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        user = await UserRepository(session).get_by_email(email)
        assert user is not None
        return user
