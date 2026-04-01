"""任务相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MainImageGeneratePayload(BaseModel):
    """主图生成文本参数。"""

    brand_name: str = Field(default="")
    product_name: str = Field(default="")
    category: str = Field(default="tea")
    platform: str = Field(default="tmall")
    style_type: str = Field(default="高端极简")
    style_notes: str = Field(default="")
    shot_count: int = Field(default=8, ge=1, le=12)
    aspect_ratio: str = Field(default="1:1")
    image_size: str = Field(default="2K")


class TaskSummary(BaseModel):
    """任务摘要，用于任务列表和页面恢复。"""

    task_id: str
    task_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    title: str = ""
    platform: str = ""
    result_path: str = ""
    progress_percent: int = 0
    current_step: str = ""
    current_step_label: str = ""
    result_count_completed: int = 0
    result_count_total: int = 0
    export_zip_path: str = ""
    provider_label: str = ""
    model_label: str = ""
    detail_image_count: int = 0
    background_image_count: int = 0


class TaskRuntimeImage(BaseModel):
    """工作台结果卡片运行时数据。"""

    id: str
    title: str
    subtitle: str = ""
    status: Literal["queued", "running", "completed", "failed"]
    image_url: str = ""
    file_name: str = ""
    width: int | None = None
    height: int | None = None
    generated_at: str = ""


class TaskRuntimeQCSummary(BaseModel):
    """工作台右侧质检摘要。"""

    passed: bool = False
    review_required: bool = False
    warning_count: int = 0
    failed_count: int = 0


class TaskRuntimePayload(BaseModel):
    """主图任务运行时视图。"""

    task_id: str
    status: str
    progress_percent: int = 0
    current_step: str = ""
    current_step_label: str = ""
    message: str = ""
    queue_position: int | None = None
    queue_size: int = 0
    provider_label: str = ""
    model_label: str = ""
    detail_image_count: int = 0
    background_image_count: int = 0
    result_count_completed: int = 0
    result_count_total: int = 0
    export_zip_url: str = ""
    full_bundle_zip_url: str = ""
    qc_summary: TaskRuntimeQCSummary = Field(default_factory=TaskRuntimeQCSummary)
    results: list[TaskRuntimeImage] = Field(default_factory=list)


class DetailPageGenerateRequest(BaseModel):
    """详情页生成请求。"""

    title: str
    subtitle: str = ""
    selling_points: list[str] = Field(default_factory=list)
    category: str = "tea"
    specs: list[dict[str, str]] = Field(default_factory=list)
    price_band: str = ""
    platform: str = "tmall"
    style: str = "premium"
    main_image_task_id: str = ""
    main_images: list[str] = Field(default_factory=list)
    product_images: list[str] = Field(default_factory=list)
    optional_copy: list[str] = Field(default_factory=list)


class DetailPageGenerateResponse(BaseModel):
    """详情页生成结果。"""

    task_id: str
    module_config_path: str
    preview_data: dict[str, object]
    export_assets: list[dict[str, str]]
    modules: list[dict[str, object]]
