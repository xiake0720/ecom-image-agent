from __future__ import annotations

import asyncio
import base64
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.config import reset_settings_cache
from backend.db.base import Base
from backend.db.enums import TaskType
from backend.db.session import dispose_async_engine, get_async_engine
from backend.engine.core import config as engine_config
from backend.engine.domain.task import Task as LegacyTask
from backend.engine.domain.task import TaskStatus as LegacyTaskStatus
from backend.engine.services.storage.local_storage import LocalStorageService
from backend.repositories.task_repository import TaskRepository
from backend.services.task_db_mirror_service import TaskDbMirrorService


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wIAAgMBAp9K1T0AAAAASUVORK5CYII="
)


@pytest.fixture()
def task_client(tmp_path, monkeypatch):
    db_path = tmp_path / "task-test.sqlite3"
    outputs_dir = tmp_path / "outputs"
    tasks_dir = outputs_dir / "tasks"
    cache_dir = outputs_dir / "cache"
    exports_dir = outputs_dir / "exports"
    storage_dir = tmp_path / "storage"

    monkeypatch.setenv("ECOM_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ECOM_AUTH_JWT_SECRET_KEY", "test-jwt-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_TOKEN_HASH_SECRET", "test-token-hash-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_REFRESH_COOKIE_SECURE", "false")
    monkeypatch.setenv("ECOM_CORS_ORIGINS", '["http://testserver"]')
    monkeypatch.setenv("ECOM_STORAGE_ROOT", str(storage_dir))
    monkeypatch.setenv("ECOM_OUTPUTS_ROOT", str(tasks_dir))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_TEXT_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_IMAGE_PROVIDER_MODE", "mock")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_ENABLE_MOCK_PROVIDERS", "true")
    monkeypatch.setenv("ECOM_IMAGE_AGENT_OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_TASKS_DIR", str(tasks_dir))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("ECOM_IMAGE_AGENT_EXPORTS_DIR", str(exports_dir))

    reset_settings_cache()
    engine_config.get_settings.cache_clear()
    asyncio.run(dispose_async_engine())

    async def _init_db() -> None:
        engine = get_async_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db())

    module_names = [
        "backend.services.task_db_mirror_service",
        "backend.services.main_image_service",
        "backend.services.task_queue_service",
        "backend.services.detail_page_job_service",
        "backend.services.task_query_service",
        "backend.api.image",
        "backend.api.detail_jobs",
        "backend.api.v1.tasks",
        "backend.api.v1",
        "backend.main",
    ]
    loaded_modules = {}
    for name in module_names:
        module = importlib.import_module(name)
        loaded_modules[name] = importlib.reload(module)

    image_api = loaded_modules["backend.api.image"]
    monkeypatch.setattr(image_api.main_image_task_queue, "enqueue", lambda prepared, executor: None)

    backend_main = loaded_modules["backend.main"]
    with TestClient(backend_main.app) as client:
        yield client, tasks_dir

    asyncio.run(dispose_async_engine())
    reset_settings_cache()
    engine_config.get_settings.cache_clear()


def test_v1_tasks_history_is_user_scoped_and_reads_db_mirror(task_client: tuple[TestClient, Path]) -> None:
    client, tasks_dir = task_client

    token_a = _register_and_get_token(client, "user-a@example.com")
    token_b = _register_and_get_token(client, "user-b@example.com")

    create_response = client.post(
        "/api/image/generate-main",
        headers={"Authorization": f"Bearer {token_a}"},
        data={
            "brand_name": "TeaLab",
            "product_name": "Spring Oolong",
            "platform": "tmall",
            "shot_count": "1",
        },
        files={"white_bg": ("white.png", PNG_BYTES, "image/png")},
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["task_id"]

    _mark_task_completed(task_id=task_id, tasks_dir=tasks_dir)

    list_response = client.get(
        "/api/v1/tasks?page=1&page_size=10&task_type=main_image&status=succeeded",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert list_response.status_code == 200
    list_body = list_response.json()["data"]
    assert list_body["total"] == 1
    assert list_body["items"][0]["task_id"] == task_id
    assert list_body["items"][0]["status"] == "succeeded"

    other_user_list = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token_b}"})
    assert other_user_list.status_code == 200
    assert other_user_list.json()["data"]["total"] == 0

    detail_response = client.get(f"/api/v1/tasks/{task_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert detail_response.status_code == 200
    detail_body = detail_response.json()["data"]
    assert detail_body["task_type"] == "main_image"
    assert detail_body["result_summary"]["result_count"] == 1

    runtime_response = client.get(f"/api/v1/tasks/{task_id}/runtime", headers={"Authorization": f"Bearer {token_a}"})
    assert runtime_response.status_code == 200
    runtime_body = runtime_response.json()["data"]
    assert runtime_body["task"]["task_id"] == task_id
    assert runtime_body["task"]["status"] == "succeeded"
    assert runtime_body["runtime"]["result_count_completed"] == 1
    assert any(event["event_type"] == "task_succeeded" for event in runtime_body["events"])

    results_response = client.get(f"/api/v1/tasks/{task_id}/results", headers={"Authorization": f"Bearer {token_a}"})
    assert results_response.status_code == 200
    results_body = results_response.json()["data"]
    assert results_body["task_id"] == task_id
    assert len(results_body["items"]) == 1
    assert results_body["items"][0]["result_type"] == "main_image"
    assert results_body["items"][0]["file_url"].endswith(f"/api/tasks/{task_id}/files/final/result_01.png")

    forbidden_response = client.get(f"/api/v1/tasks/{task_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden_response.status_code == 404
    assert forbidden_response.json()["code"] == 4044


def _register_and_get_token(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "nickname": email.split("@")[0]},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _mark_task_completed(*, task_id: str, tasks_dir: Path) -> None:
    task_dir = tasks_dir / task_id
    final_dir = task_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "result_01.png").write_bytes(PNG_BYTES)

    task_path = task_dir / "task.json"
    task = LegacyTask.model_validate_json(task_path.read_text(encoding="utf-8"))
    completed_task = task.model_copy(
        update={
            "status": LegacyTaskStatus.COMPLETED,
            "current_step": "finalize",
            "current_step_label": "任务已完成",
            "progress_percent": 100,
        }
    )
    LocalStorageService().save_task_manifest(completed_task)
    TaskRepository().save_runtime_task(completed_task)
    asyncio.run(TaskDbMirrorService().sync_runtime_from_local(task_id=task_id, task_type=TaskType.MAIN_IMAGE))
