"""Tencent COS storage service wrapper."""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any
import uuid

from backend.core.config import get_settings
from backend.core.exceptions import AppException
from backend.core.logging import format_log_event


logger = logging.getLogger(__name__)


class CosService:
    """Wrap COS SDK object keys, presigned URLs, and object uploads."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any | None = None

    def is_enabled(self) -> bool:
        """Return whether real COS is enabled and fully configured."""

        return self.settings.is_cos_ready()

    def build_task_object_key(
        self,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        kind: str,
        file_name: str,
    ) -> str:
        """Build a normalized task object key."""

        safe_kind = self._safe_key_segment(kind, fallback="files")
        safe_file = self._safe_object_path(file_name)
        return f"users/{user_id.hex}/tasks/{task_id.hex}/{safe_kind}/{safe_file}"

    def create_presigned_upload_url(
        self,
        *,
        key: str,
        mime_type: str,
        sha256: str,
    ) -> tuple[str, dict[str, str]]:
        """Create a browser direct-upload PUT URL."""

        started_at = perf_counter()
        logger.info(format_log_event("cos_presign_started", operation="upload", key=key, mime_type=mime_type))
        client = self._get_client()
        headers = {
            "Content-Type": mime_type,
            "x-cos-meta-sha256": sha256,
        }
        try:
            url = client.get_presigned_url(
                Bucket=self.settings.cos_bucket,
                Key=key,
                Method="PUT",
                Expired=self.settings.cos_sign_expire_seconds,
                Headers=headers,
            )
        except Exception:
            logger.exception(format_log_event("cos_presign_failed", operation="upload", key=key, elapsed_ms=_elapsed_ms(started_at)))
            raise
        logger.info(
            format_log_event(
                "cos_presign_succeeded",
                operation="upload",
                key=key,
                expires_in=self.settings.cos_sign_expire_seconds,
                elapsed_ms=_elapsed_ms(started_at),
            )
        )
        return str(url), headers

    def create_presigned_download_url(self, *, key: str) -> str:
        """Create a private object download URL."""

        started_at = perf_counter()
        logger.info(format_log_event("cos_presign_started", operation="download", key=key))
        client = self._get_client()
        try:
            url = client.get_presigned_url(
                Bucket=self.settings.cos_bucket,
                Key=key,
                Method="GET",
                Expired=self.settings.cos_sign_expire_seconds,
            )
        except Exception:
            logger.exception(format_log_event("cos_presign_failed", operation="download", key=key, elapsed_ms=_elapsed_ms(started_at)))
            raise
        logger.info(
            format_log_event(
                "cos_download_url_signed",
                key=key,
                expires_in=self.settings.cos_sign_expire_seconds,
                elapsed_ms=_elapsed_ms(started_at),
            )
        )
        return str(url)

    def upload_file(self, *, local_path: Path, key: str, mime_type: str) -> None:
        """Upload a local file to COS for workflow compatibility writes."""

        started_at = perf_counter()
        logger.info(
            format_log_event(
                "cos_upload_started",
                key=key,
                mime_type=mime_type,
                size_bytes=local_path.stat().st_size if local_path.exists() else None,
            )
        )
        client = self._get_client()
        try:
            with local_path.open("rb") as file_obj:
                client.put_object(
                    Bucket=self.settings.cos_bucket,
                    Key=key,
                    Body=file_obj,
                    ContentType=mime_type,
                    EnableMD5=False,
                )
        except Exception:
            logger.exception(format_log_event("cos_upload_failed", key=key, elapsed_ms=_elapsed_ms(started_at)))
            raise
        logger.info(format_log_event("cos_upload_succeeded", key=key, elapsed_ms=_elapsed_ms(started_at)))

    def _get_client(self) -> Any:
        """Lazy-create the COS SDK client so local mode can run without COS config."""

        if not self.is_enabled():
            raise AppException("COS 未启用或配置不完整", code=5031, status_code=503)
        if self._client is not None:
            return self._client
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:  # pragma: no cover
            raise AppException("COS SDK 未安装，请安装 cos-python-sdk-v5", code=5032, status_code=503) from exc

        config_kwargs: dict[str, object] = {
            "Region": self.settings.cos_region,
            "SecretId": self.settings.cos_secret_id,
            "SecretKey": self.settings.cos_secret_key,
            "Scheme": "https",
        }
        if self.settings.cos_public_host.strip():
            config_kwargs["Domain"] = self.settings.cos_public_host.strip().removeprefix("https://").removeprefix("http://")
        config = CosConfig(**config_kwargs)
        self._client = CosS3Client(config)
        return self._client

    def _safe_key_segment(self, value: str, *, fallback: str) -> str:
        segment = value.strip().replace("\\", "/").strip("/")
        if not segment or segment in {".", ".."}:
            return fallback
        return segment.replace("..", "_")

    def _safe_object_path(self, file_name: str) -> str:
        """Clean object path while preserving internal result subdirectories."""

        parts: list[str] = []
        for part in PurePosixPath(file_name.replace("\\", "/")).parts:
            if part in {"", ".", "..", "/"}:
                continue
            cleaned = part.replace("..", "_")
            if cleaned:
                parts.append(cleaned)
        if not parts:
            raise AppException("COS 对象文件名非法", code=4011, status_code=400)
        return "/".join(parts)


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
