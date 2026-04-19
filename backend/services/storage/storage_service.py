"""v1 文件存储业务编排服务。"""

from __future__ import annotations

from urllib.parse import quote
import uuid

from backend.core.exceptions import AppException
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


class StorageService:
    """编排预签名上传与签名下载，并保证用户所有权校验。"""

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
        """为当前用户任务生成图片直传 URL，并预写 task_assets 元数据。"""

        task_uuid = self._parse_uuid(payload.task_id, field_name="task_id")
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

        return StoragePresignResponse(
            file_id=asset_row.id.hex,
            task_id=task_uuid.hex,
            cos_key=cos_key,
            upload_url=upload_url,
            headers=headers,
            expires_in=self.cos_service.settings.cos_sign_expire_seconds,
        )

    async def create_download_url(self, *, current_user: User, file_id: str) -> FileDownloadUrlResponse:
        """按 file_id 查询资产或结果，校验归属后返回下载 URL。"""

        object_uuid = self._parse_uuid(file_id, field_name="file_id")
        async with self.session_factory() as session:
            asset_repo = TaskAssetRepository(session)
            result_repo = TaskResultRepository(session)
            task_repo = TaskDbRepository(session)

            asset_row = await asset_repo.get_by_id_for_user(object_uuid, user_id=current_user.id)
            if asset_row is not None:
                task_row = await task_repo.get_by_id_for_user(asset_row.task_id, user_id=current_user.id)
                if task_row is None:
                    raise AppException(f"文件 {file_id} 不存在", code=4045, status_code=404)
                download_url = self._build_download_url(task_type=task_row.task_type, task_id=task_row.id.hex, cos_key=asset_row.cos_key)
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
                raise AppException(f"文件 {file_id} 不存在", code=4045, status_code=404)
            task_row = await task_repo.get_by_id_for_user(result_row.task_id, user_id=current_user.id)
            if task_row is None:
                raise AppException(f"文件 {file_id} 不存在", code=4045, status_code=404)
            download_url = self._build_download_url(task_type=task_row.task_type, task_id=task_row.id.hex, cos_key=result_row.cos_key)
            return FileDownloadUrlResponse(
                file_id=result_row.id.hex,
                source_type="result",
                task_id=result_row.task_id.hex,
                cos_key=result_row.cos_key,
                download_url=download_url,
                expires_in=self.cos_service.settings.cos_sign_expire_seconds,
            )

    def _build_download_url(self, *, task_type: str, task_id: str, cos_key: str) -> str:
        """COS 模式签发 URL；本地兼容模式回退旧文件接口。"""

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
