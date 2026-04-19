from __future__ import annotations

import asyncio
import base64
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.config import reset_settings_cache
from backend.db.base import Base
from backend.db.session import dispose_async_engine, get_async_engine
from backend.engine.core import config as engine_config


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wIAAgMBAp9K1T0AAAAASUVORK5CYII="
)


@pytest.fixture()
def celery_client(tmp_path, monkeypatch):
    db_path = tmp_path / "celery-test.sqlite3"
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
        "backend.workers.celery_app",
        "backend.workers.tasks.main_image_tasks",
        "backend.workers.tasks.detail_page_tasks",
        "backend.services.main_image_service",
        "backend.services.detail_page_job_service",
        "backend.api.image",
        "backend.api.detail_jobs",
        "backend.api.v1",
        "backend.main",
    ]
    loaded_modules = {}
    for name in module_names:
        module = importlib.import_module(name)
        loaded_modules[name] = importlib.reload(module)

    main_calls: list[str] = []
    detail_calls: list[tuple[str, bool]] = []

    main_image_tasks = loaded_modules["backend.workers.tasks.main_image_tasks"]
    detail_page_tasks = loaded_modules["backend.workers.tasks.detail_page_tasks"]
    image_api = loaded_modules["backend.api.image"]
    monkeypatch.setattr(main_image_tasks.run_main_image_task, "delay", lambda task_id: main_calls.append(task_id))
    monkeypatch.setattr(detail_page_tasks.run_detail_page_task, "delay", lambda task_id, plan_only=False: detail_calls.append((task_id, plan_only)))
    monkeypatch.setattr(image_api.main_image_task_queue, "enqueue", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should use celery")))

    backend_main = loaded_modules["backend.main"]
    with TestClient(backend_main.app) as client:
        yield client, main_calls, detail_calls

    asyncio.run(dispose_async_engine())
    reset_settings_cache()
    engine_config.get_settings.cache_clear()


def test_main_image_api_enqueues_celery_when_enabled(celery_client: tuple[TestClient, list[str], list[tuple[str, bool]]]) -> None:
    client, main_calls, _detail_calls = celery_client
    token = _register_and_get_token(client, "celery-main@example.com")

    response = client.post(
        "/api/image/generate-main",
        headers={"Authorization": f"Bearer {token}"},
        data={"product_name": "Celery Main", "shot_count": "1"},
        files={"white_bg": ("white.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200
    task_id = response.json()["data"]["task_id"]
    assert main_calls == [task_id]


def test_detail_plan_api_enqueues_celery_when_enabled(celery_client: tuple[TestClient, list[str], list[tuple[str, bool]]]) -> None:
    client, _main_calls, detail_calls = celery_client
    token = _register_and_get_token(client, "celery-detail@example.com")

    response = client.post(
        "/api/detail/jobs/plan",
        headers={"Authorization": f"Bearer {token}"},
        data={"product_name": "Celery Detail", "target_slice_count": "8"},
        files={"packaging_files": ("packaging.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200
    task_id = response.json()["data"]["task_id"]
    assert detail_calls == [(task_id, True)]


def _register_and_get_token(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "nickname": email.split("@")[0]},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]
