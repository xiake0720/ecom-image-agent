from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class Task(BaseModel):
    task_id: str
    brand_name: str
    product_name: str
    category: str = "tea"
    platform: str
    output_size: str
    shot_count: int
    copy_tone: str
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_dir: str = ""

