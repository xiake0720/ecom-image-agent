"""文件存储 API schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StoragePresignRequest(BaseModel):
    """申请 COS 预签名上传 URL 的请求。"""

    task_id: str
    kind: str = Field(default="inputs", max_length=50)
    file_name: str = Field(max_length=255)
    mime_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    role: str = Field(default="upload", max_length=50)
    sort_order: int = Field(default=0, ge=0)


class StoragePresignResponse(BaseModel):
    """预签名上传 URL 响应。"""

    file_id: str
    task_id: str
    cos_key: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str] = Field(default_factory=dict)
    expires_in: int


class FileDownloadUrlResponse(BaseModel):
    """签名下载 URL 响应。"""

    file_id: str
    source_type: str
    task_id: str
    cos_key: str
    download_url: str
    expires_in: int
