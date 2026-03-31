"""任务相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MainImageGeneratePayload(BaseModel):
    """主图生成参数。

    说明：文件上传通过 multipart 传输，本文档模型用于记录文本字段含义。
    """

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
    """任务摘要，用于任务列表和详情页导航。"""

    task_id: str
    task_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    title: str = ""
    platform: str = ""
    result_path: str = ""


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
