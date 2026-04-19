"""API v1 schemas for result image edits."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.schemas.task_v1 import TaskResultResponse


class RectangleSelection(BaseModel):
    """Normalized rectangle selection in source image coordinates."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    unit: Literal["ratio"] = "ratio"

    @model_validator(mode="after")
    def _validate_bounds(self) -> "RectangleSelection":
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("rectangle selection must stay inside the source image")
        return self


class ImageEditCreateRequest(BaseModel):
    """Create an edit request for a task result image."""

    selection_type: Literal["rectangle"] = "rectangle"
    selection: RectangleSelection
    instruction: str = Field(min_length=3, max_length=1000)


class ImageEditResponse(BaseModel):
    """Image edit record returned by v1 result edit APIs."""

    edit_id: str
    source_result_id: str
    edit_task_id: str
    edited_result_id: str | None = None
    selection_type: str
    selection: dict[str, Any]
    instruction: str
    mode: str
    status: str
    error_message: str | None = None
    metadata: dict[str, Any] | None = None
    edited_result: TaskResultResponse | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ImageEditListResponse(BaseModel):
    """Edit history for one source result."""

    source_result_id: str
    items: list[ImageEditResponse] = Field(default_factory=list)
