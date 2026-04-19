"""上传文件安全校验服务。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from backend.core.config import get_settings
from backend.core.exceptions import AppException


SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
SAFE_NAME_RE = re.compile(r"[^\w.-]+")


@dataclass(frozen=True, slots=True)
class UploadFileMeta:
    """上传前校验后的文件元数据。"""

    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str


class UploadGuardService:
    """集中校验直传文件，避免 route 层散落安全规则。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def validate_image_upload(
        self,
        *,
        file_name: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
    ) -> UploadFileMeta:
        """校验图片上传元数据，并返回安全文件名。"""

        normalized_mime = mime_type.strip().lower()
        if normalized_mime not in set(self.settings.cos_allowed_image_mime_types):
            raise AppException("不支持的图片 MIME 类型", code=4008, status_code=400)
        if size_bytes <= 0 or size_bytes > self.settings.cos_max_image_size_bytes:
            raise AppException("文件大小超出限制", code=4009, status_code=400)
        if not SHA256_RE.match(sha256.strip()):
            raise AppException("SHA256 摘要格式非法", code=4010, status_code=400)
        safe_name = self.sanitize_file_name(file_name)
        return UploadFileMeta(
            file_name=safe_name,
            mime_type=normalized_mime,
            size_bytes=size_bytes,
            sha256=sha256.lower(),
        )

    def sanitize_file_name(self, file_name: str) -> str:
        """清理文件名，禁止路径穿越和空文件名。"""

        raw_name = PurePosixPath(file_name.replace("\\", "/")).name.strip()
        if not raw_name or raw_name in {".", ".."}:
            raise AppException("文件名非法", code=4011, status_code=400)
        safe_name = SAFE_NAME_RE.sub("_", raw_name)
        if safe_name.startswith("."):
            safe_name = f"upload{safe_name}"
        if not safe_name:
            raise AppException("文件名非法", code=4011, status_code=400)
        return safe_name[:255]
