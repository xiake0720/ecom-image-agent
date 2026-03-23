<<<<<<< HEAD
"""任务 contract。

文件位置：
- `src/domain/task.py`

核心职责：
- 定义任务级输入参数和任务状态
- 把 workflow 版本、overlay fallback 开关等跨层控制项稳定写进 `task.json`
"""

=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
<<<<<<< HEAD
    """任务运行状态枚举。"""

=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class Task(BaseModel):
<<<<<<< HEAD
    """任务级输入参数与运行状态。"""

=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    task_id: str
    brand_name: str
    product_name: str
    category: str = "tea"
    platform: str
    output_size: str
    shot_count: int
    copy_tone: str
<<<<<<< HEAD
    workflow_version: str = "v1"
    enable_overlay_fallback: bool = False
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_dir: str = ""
=======
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_dir: str = ""

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
