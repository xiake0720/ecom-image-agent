"""API v1 task query schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.db.enums import TaskStatus, TaskType


class TaskListItem(BaseModel):
    """Task list item."""

    task_id: str
    task_type: TaskType
    status: TaskStatus
    title: str | None = None
    platform: str | None = None
    biz_id: str | None = None
    current_step: str | None = None
    progress_percent: float = 0
    result_count: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskListResponse(BaseModel):
    """Paginated task list."""

    items: list[TaskListItem] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0


class TaskDetailResponse(BaseModel):
    """Task detail summary."""

    task_id: str
    task_type: TaskType
    status: TaskStatus
    title: str | None = None
    platform: str | None = None
    biz_id: str | None = None
    source_task_id: str | None = None
    parent_task_id: str | None = None
    current_step: str | None = None
    progress_percent: float = 0
    input_summary: dict[str, Any] | None = None
    params: dict[str, Any] | None = None
    runtime_snapshot: dict[str, Any] | None = None
    result_summary: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskEventResponse(BaseModel):
    """Task event entry."""

    event_id: str
    event_type: str
    level: str
    step: str | None = None
    message: str
    payload: dict[str, Any] | None = None
    created_at: datetime


class TaskRuntimeResponse(BaseModel):
    """Task runtime aggregate response."""

    task: TaskDetailResponse
    runtime: dict[str, Any] | None = None
    events: list[TaskEventResponse] = Field(default_factory=list)


class TaskResultResponse(BaseModel):
    """Task result item."""

    result_id: str
    result_type: str
    page_no: int | None = None
    shot_no: int | None = None
    version_no: int = 1
    parent_result_id: str | None = None
    status: str
    cos_key: str
    mime_type: str
    size_bytes: int
    sha256: str
    width: int | None = None
    height: int | None = None
    prompt_plan: dict[str, Any] | None = None
    prompt_final: dict[str, Any] | None = None
    render_meta: dict[str, Any] | None = None
    qc_status: str | None = None
    qc_score: float | None = None
    is_primary: bool = True
    file_url: str = ""
    download_url_api: str = ""
    created_at: datetime
    updated_at: datetime


class TaskResultsResponse(BaseModel):
    """Task result collection."""

    task_id: str
    items: list[TaskResultResponse] = Field(default_factory=list)
