"""任务 contract。

文件位置：
- `src/domain/task.py`

职责：
- 定义任务输入参数
- 持久化任务进度与最终状态
- 承载用户可控文案、风格偏好与生成模式
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


def _normalize_string_list(value: object) -> object:
    """把逗号或换行输入统一归一化为字符串列表。"""

    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.replace("\r", "\n")
        chunks: list[str] = []
        for part in normalized.replace("，", ",").split("\n"):
            for inner in part.split(","):
                item = inner.strip()
                if item:
                    chunks.append(item)
        return chunks
    return value


class TaskStatus(str, Enum):
    """任务状态枚举。"""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class CopyMode(str, Enum):
    """图内文案生成模式。"""

    AUTO = "auto"
    MANUAL = "manual"
    MIXED = "mixed"


class Task(BaseModel):
    """任务级输入与运行状态。"""

    task_id: str
    brand_name: str
    product_name: str
    category: str = "tea"
    platform: str = "tmall"
    shot_count: int = 8
    aspect_ratio: str = "1:1"
    image_size: str = "2K"
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_dir: str = ""
    current_step: str = ""
    current_step_label: str = ""
    progress_percent: int = 0
    error_message: str = ""
    title_text: str = ""
    subtitle_text: str = ""
    selling_points: list[str] = Field(default_factory=list)
    copy_mode: CopyMode = CopyMode.MIXED
    style_type: str = "高端极简"
    style_preferences: str = ""
    custom_elements: list[str] = Field(default_factory=list)
    avoid_elements: list[str] = Field(default_factory=list)

    @field_validator("selling_points", "custom_elements", "avoid_elements", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value: object) -> object:
        """兼容 UI 以字符串或列表两种形式提交。"""

        return _normalize_string_list(value)
