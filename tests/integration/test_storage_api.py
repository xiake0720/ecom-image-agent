from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.core.config import reset_settings_cache
from backend.db.base import Base
from backend.db.enums import TaskStatus, TaskType
from backend.db.models.task import Task
from backend.db.session import dispose_async_engine, get_async_engine, get_async_session_factory
from backend.repositories.db.user_repository import UserRepository
from backend.services.storage.storage_service import StorageService


class FakeCosService:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(cos_sign_expire_seconds=120)

    def is_enabled(self) -> bool:
        return True

    def build_task_object_key(self, *, user_id: uuid.UUID, task_id: uuid.UUID, kind: str, file_name: str) -> str:
        return f"users/{user_id.hex}/tasks/{task_id.hex}/{kind}/{file_name}"

    def create_presigned_upload_url(self, *, key: str, mime_type: str, sha256: str) -> tuple[str, dict[str, str]]:
        return f"https://cos.example/upload/{key}", {"Content-Type": mime_type, "x-cos-meta-sha256": sha256}

    def create_presigned_download_url(self, *, key: str) -> str:
        return f"https://cos.example/download/{key}"


@pytest.fixture()
def storage_client(tmp_path, monkeypatch):
    db_path = tmp_path / "storage-test.sqlite3"
    monkeypatch.setenv("ECOM_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ECOM_AUTH_JWT_SECRET_KEY", "test-jwt-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_TOKEN_HASH_SECRET", "test-token-hash-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_REFRESH_COOKIE_SECURE", "false")
    monkeypatch.setenv("ECOM_CORS_ORIGINS", '["http://testserver"]')
    monkeypatch.setenv("ECOM_COS_ENABLED", "true")
    monkeypatch.setenv("ECOM_COS_SECRET_ID", "id")
    monkeypatch.setenv("ECOM_COS_SECRET_KEY", "key")
    monkeypatch.setenv("ECOM_COS_REGION", "ap-guangzhou")
    monkeypatch.setenv("ECOM_COS_BUCKET", "bucket-123")
    monkeypatch.setenv("ECOM_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("ECOM_OUTPUTS_ROOT", str(tmp_path / "outputs" / "tasks"))

    reset_settings_cache()
    asyncio.run(dispose_async_engine())

    async def _init_db() -> None:
        engine = get_async_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db())

    module_names = [
        "backend.services.storage.storage_service",
        "backend.api.v1.storage",
        "backend.api.v1",
        "backend.main",
    ]
    loaded_modules = {}
    for name in module_names:
        module = importlib.import_module(name)
        loaded_modules[name] = importlib.reload(module)

    storage_api = loaded_modules["backend.api.v1.storage"]
    monkeypatch.setattr(storage_api, "service", StorageService(cos_service=FakeCosService()))

    backend_main = loaded_modules["backend.main"]
    with TestClient(backend_main.app) as client:
        yield client

    asyncio.run(dispose_async_engine())
    reset_settings_cache()


def test_presign_and_download_url_are_user_scoped(storage_client: TestClient) -> None:
    token_a = _register_and_get_token(storage_client, "storage-a@example.com")
    token_b = _register_and_get_token(storage_client, "storage-b@example.com")
    task_id = uuid.uuid4()
    asyncio.run(_create_task_for_user("storage-a@example.com", task_id))

    presign_response = storage_client.post(
        "/api/v1/storage/presign",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "task_id": task_id.hex,
            "kind": "inputs",
            "file_name": "white.png",
            "mime_type": "image/png",
            "size_bytes": 9,
            "sha256": "a" * 64,
            "role": "white_bg",
        },
    )
    assert presign_response.status_code == 200
    presign_body = presign_response.json()["data"]
    assert presign_body["cos_key"].startswith("users/")
    assert presign_body["headers"]["x-cos-meta-sha256"] == "a" * 64

    file_id = presign_body["file_id"]
    download_response = storage_client.get(
        f"/api/v1/files/{file_id}/download-url",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert download_response.status_code == 200
    assert download_response.json()["data"]["download_url"].startswith("https://cos.example/download/")

    other_user_response = storage_client.get(
        f"/api/v1/files/{file_id}/download-url",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_user_response.status_code == 404


def _register_and_get_token(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "nickname": email.split("@")[0]},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


async def _create_task_for_user(email: str, task_id: uuid.UUID) -> None:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        user = await UserRepository(session).get_by_email(email)
        assert user is not None
        session.add(
            Task(
                id=task_id,
                user_id=user.id,
                task_type=TaskType.MAIN_IMAGE.value,
                status=TaskStatus.QUEUED.value,
                title="Storage Test",
                progress_percent=0,
                result_summary={"result_count": 0},
            )
        )
        await session.commit()
