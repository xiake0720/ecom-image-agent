"""腾讯云 COS 存储服务封装。"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
import uuid

from backend.core.config import get_settings
from backend.core.exceptions import AppException


class CosService:
    """封装 COS SDK，统一生成对象 key、预签名 URL 和上传对象。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any | None = None

    def is_enabled(self) -> bool:
        """返回当前是否启用真实 COS。"""

        return self.settings.is_cos_ready()

    def build_task_object_key(
        self,
        *,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        kind: str,
        file_name: str,
    ) -> str:
        """按统一规范生成 COS 对象 key。"""

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
        """生成用于浏览器直传的 PUT 预签名 URL。"""

        client = self._get_client()
        headers = {
            "Content-Type": mime_type,
            "x-cos-meta-sha256": sha256,
        }
        url = client.get_presigned_url(
            Bucket=self.settings.cos_bucket,
            Key=key,
            Method="PUT",
            Expired=self.settings.cos_sign_expire_seconds,
            Headers=headers,
        )
        return str(url), headers

    def create_presigned_download_url(self, *, key: str) -> str:
        """生成私有桶对象下载 URL。"""

        client = self._get_client()
        url = client.get_presigned_url(
            Bucket=self.settings.cos_bucket,
            Key=key,
            Method="GET",
            Expired=self.settings.cos_sign_expire_seconds,
        )
        return str(url)

    def upload_file(self, *, local_path: Path, key: str, mime_type: str) -> None:
        """把本地文件上传到 COS，供旧 workflow 兼容写入使用。"""

        client = self._get_client()
        with local_path.open("rb") as file_obj:
            client.put_object(
                Bucket=self.settings.cos_bucket,
                Key=key,
                Body=file_obj,
                ContentType=mime_type,
                EnableMD5=False,
            )

    def _get_client(self) -> Any:
        """延迟创建 COS SDK 客户端，避免无 COS 配置时影响本地开发。"""

        if not self.is_enabled():
            raise AppException("COS 未启用或配置不完整", code=5031, status_code=503)
        if self._client is not None:
            return self._client
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:  # pragma: no cover - 只在缺少可选依赖时触发
            raise AppException("COS SDK 未安装，请安装 cos-python-sdk-v5", code=5032, status_code=503) from exc

        config_kwargs: dict[str, object] = {
            "Region": self.settings.cos_region,
            "SecretId": self.settings.cos_secret_id,
            "SecretKey": self.settings.cos_secret_key,
            "Scheme": "https",
        }
        if self.settings.cos_public_host.strip():
            # COS SDK 的 Domain 用于自定义源站域名签名，不会把 Secret 下发给前端。
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
        """清理对象路径，允许内部同步结果保留子目录结构。"""

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
