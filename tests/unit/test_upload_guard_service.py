from __future__ import annotations

import pytest

from backend.core.config import reset_settings_cache
from backend.core.exceptions import AppException
from backend.services.storage.upload_guard_service import UploadGuardService


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    monkeypatch.setenv("ECOM_COS_MAX_IMAGE_SIZE_BYTES", "10")
    monkeypatch.setenv("ECOM_COS_ALLOWED_IMAGE_MIME_TYPES", '["image/png"]')
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_upload_guard_accepts_safe_image_meta() -> None:
    guard = UploadGuardService()

    meta = guard.validate_image_upload(
        file_name="../商品 图.png",
        mime_type="image/png",
        size_bytes=10,
        sha256="a" * 64,
    )

    assert meta.file_name == "商品_图.png"
    assert meta.mime_type == "image/png"
    assert meta.sha256 == "a" * 64


def test_upload_guard_rejects_invalid_mime() -> None:
    guard = UploadGuardService()

    with pytest.raises(AppException):
        guard.validate_image_upload(
            file_name="bad.gif",
            mime_type="image/gif",
            size_bytes=1,
            sha256="a" * 64,
        )


def test_upload_guard_rejects_invalid_sha256() -> None:
    guard = UploadGuardService()

    with pytest.raises(AppException):
        guard.validate_image_upload(
            file_name="bad.png",
            mime_type="image/png",
            size_bytes=1,
            sha256="not-a-sha",
        )
