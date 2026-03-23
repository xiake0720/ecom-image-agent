"""任务 contract。

文件位置：
- `src/domain/task.py`

职责：
- 定义任务输入参数
- 持久化任务进度与最终状态
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举。"""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


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
