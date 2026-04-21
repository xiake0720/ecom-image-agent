"""v1 file storage orchestration service."""

from __future__ import annotations

import logging
from time import perf_counter
from urllib.parse import quote
import uuid

from backend.core.exceptions import AppException
from backend.core.logging import format_log_event
from backend.db.enums import TaskAssetScanStatus
from backend.db.models.task import TaskAsset
from backend.db.models.user import User
from backend.db.session import get_async_session_factory
from backend.repositories.db.task_asset_repository import TaskAssetRepository
from backend.repositories.db.task_db_repository import TaskDbRepository
from backend.repositories.db.task_result_repository import TaskResultRepository
from backend.schemas.storage import FileDownloadUrlResponse, StoragePresignRequest, StoragePresignResponse
from backend.services.storage.cos_service import CosService
from backend.services.storage.upload_guard_service import UploadGuardService


logger = logging.getLogger(__name__)


class StorageService:
    """Coordinate presigned upload/download URLs and ownership checks."""

    def __init__(
        self,
        *,
        cos_service: CosService | None = None,
        upload_guard: UploadGuardService | None = None,
    ) -> None:
        self.session_factory = get_async_session_factory()
        self.cos_service = cos_service or CosService()
        self.upload_guard = upload_guard or UploadGuardService()

    async def create_presigned_upload(
        self,
        *,
        current_user: User,
        payload: StoragePresignRequest,
    ) -> StoragePresignResponse:
        """Create a browser direct-upload URL and pre-create task asset metadata."""

        started_at = perf_counter()
        task_uuid = self._parse_uuid(payload.task_id, field_name="task_id")
        logger.info(
            format_log_event(
                "storage_lookup_started",
                user_id=current_user.id.hex,
                task_id=task_uuid.hex,
                operation="create_presigned_upload",
                file_name=payload.file_name,
                mime_type=payload.mime_type,
                size_bytes=payload.size_bytes,
            )
        )
        file_meta = self.upload_guard.validate_image_upload(
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            sha256=payload.sha256,
        )

        async with self.session_factory() as session:
            task_repo = TaskDbRepository(session)
            asset_repo = TaskAssetRepository(session)
            task_row = await task_repo.get_by_id_for_user(task_uuid, user_id=current_user.id)
            if task_row is None:
                logger.warning(
                    format_log_event(
                        "storage_lookup_failed",
                        user_id=current_user.id.hex,
                        task_id=task_uuid.hex,
                        operation="create_presigned_upload",
                        reason="task_not_found",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException(f"任务 {payload.task_id} 不存在", code=4044, status_code=404)

            cos_key = self.cos_service.build_task_object_key(
                user_id=current_user.id,
                task_id=task_row.id,
                kind=payload.kind,
                file_name=file_meta.file_name,
            )
            upload_url, headers = self.cos_service.create_presigned_upload_url(
                key=cos_key,
                mime_type=file_meta.mime_type,
                sha256=file_meta.sha256,
            )
            asset_row = TaskAsset(
                id=uuid.uuid4(),
                task_id=task_row.id,
                user_id=current_user.id,
                role=payload.role,
                source_type="cos_presign",
                file_name=file_meta.file_name,
                cos_key=cos_key,
                mime_type=file_meta.mime_type,
                size_bytes=file_meta.size_bytes,
                sha256=file_meta.sha256,
                scan_status=TaskAssetScanStatus.PENDING.value,
                metadata_json={"upload_status": "presigned"},
                sort_order=payload.sort_order,
            )
            asset_repo.add(asset_row)
            await session.commit()

        logger.info(
            format_log_event(
                "storage_lookup_succeeded",
                user_id=current_user.id.hex,
                task_id=task_uuid.hex,
                file_id=asset_row.id.hex,
                operation="create_presigned_upload",
                elapsed_ms=_elapsed_ms(started_at),
            )
        )
        return StoragePresignResponse(
            file_id=asset_row.id.hex,
            task_id=task_uuid.hex,
            cos_key=cos_key,
            upload_url=upload_url,
            headers=headers,
            expires_in=self.cos_service.settings.cos_sign_expire_seconds,
        )

    async def create_download_url(self, *, current_user: User, file_id: str) -> FileDownloadUrlResponse:
        """Resolve an owned asset/result and return a download URL."""

        started_at = perf_counter()
        object_uuid = self._parse_uuid(file_id, field_name="file_id")
        logger.info(
            format_log_event(
                "storage_lookup_started",
                user_id=current_user.id.hex,
                file_id=object_uuid.hex,
                operation="create_download_url",
            )
        )
        async with self.session_factory() as session:
            asset_repo = TaskAssetRepository(session)
            result_repo = TaskResultRepository(session)
            task_repo = TaskDbRepository(session)

            asset_row = await asset_repo.get_by_id_for_user(object_uuid, user_id=current_user.id)
            if asset_row is not None:
                task_row = await task_repo.get_by_id_for_user(asset_row.task_id, user_id=current_user.id)
                if task_row is None:
                    logger.warning(
                        format_log_event(
                            "storage_lookup_failed",
                            user_id=current_user.id.hex,
                            file_id=object_uuid.hex,
                            source_type="asset",
                            reason="task_not_found",
                            elapsed_ms=_elapsed_ms(started_at),
                        )
                    )
                    raise AppException(f"文件 {file_id} 不存在", code=4045, status_code=404)
                download_url = self._build_download_url(task_type=task_row.task_type, task_id=task_row.id.hex, cos_key=asset_row.cos_key)
                logger.info(
                    format_log_event(
                        "storage_lookup_succeeded",
                        user_id=current_user.id.hex,
                        file_id=asset_row.id.hex,
                        task_id=asset_row.task_id.hex,
                        source_type="asset",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                return FileDownloadUrlResponse(
                    file_id=asset_row.id.hex,
                    source_type="asset",
                    task_id=asset_row.task_id.hex,
                    cos_key=asset_row.cos_key,
                    download_url=download_url,
                    expires_in=self.cos_service.settings.cos_sign_expire_seconds,
                )

            result_row = await result_repo.get_by_id_for_user(object_uuid, user_id=current_user.id)
            if result_row is None:
                logger.warning(
                    format_log_event(
                        "storage_lookup_failed",
                        user_id=current_user.id.hex,
                        file_id=object_uuid.hex,
                        operation="create_download_url",
                        reason="file_not_found",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException(f"文件 {file_id} 不存在", code=4045, status_code=404)
            task_row = await task_repo.get_by_id_for_user(result_row.task_id, user_id=current_user.id)
            if task_row is None:
                logger.warning(
                    format_log_event(
                        "storage_lookup_failed",
                        user_id=current_user.id.hex,
                        file_id=object_uuid.hex,
                        source_type="result",
                        reason="task_not_found",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException(f"文件 {file_id} 不存在", code=4045, status_code=404)
            download_url = self._build_download_url(task_type=task_row.task_type, task_id=task_row.id.hex, cos_key=result_row.cos_key)
            logger.info(
                format_log_event(
                    "storage_lookup_succeeded",
                    user_id=current_user.id.hex,
                    file_id=result_row.id.hex,
                    task_id=result_row.task_id.hex,
                    source_type="result",
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            return FileDownloadUrlResponse(
                file_id=result_row.id.hex,
                source_type="result",
                task_id=result_row.task_id.hex,
                cos_key=result_row.cos_key,
                download_url=download_url,
                expires_in=self.cos_service.settings.cos_sign_expire_seconds,
            )

    def _build_download_url(self, *, task_type: str, task_id: str, cos_key: str) -> str:
        """Sign a COS URL when enabled, otherwise return the local compatibility API URL."""

        if self.cos_service.is_enabled() and cos_key.startswith("users/"):
            return self.cos_service.create_presigned_download_url(key=cos_key)
        safe_key = quote(cos_key.replace("\\", "/"), safe="/")
        if task_type == "detail_page":
            return f"/api/detail/jobs/{task_id}/files/{safe_key}"
        return f"/api/tasks/{task_id}/files/{safe_key}"

    def _parse_uuid(self, value: str, *, field_name: str) -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise AppException(f"{field_name} 非法: {value}", code=4007, status_code=400) from exc


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
