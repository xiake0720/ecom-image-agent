"""详情图任务相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DetailAssetRole = Literal[
    "main_result",
    "packaging",
    "dry_leaf",
    "tea_soup",
    "leaf_bottom",
    "scene_ref",
    "bg_ref",
]

DetailTaskStatus = Literal["created", "running", "completed", "review_required", "failed"]
DetailRenderStatus = Literal["queued", "running", "completed", "failed"]
DetailQCStatus = Literal["passed", "warning", "failed"]


class DetailPageAssetRef(BaseModel):
    """详情图素材引用。"""

    asset_id: str
    role: DetailAssetRole
    file_name: str
    relative_path: str
    source_type: str = "upload"
    source_task_id: str = ""
    source_result_file: str = ""
    width: int | None = None
    height: int | None = None


class DetailPagePlanScreen(BaseModel):
    """详情图单屏规划。"""

    screen_id: str
    theme: str
    goal: str
    screen_type: Literal["visual", "info"] = "visual"
    suggested_asset_roles: list[DetailAssetRole] = Field(default_factory=list)


class DetailPagePlanPage(BaseModel):
    """单张 1:3 长图规划。"""

    page_id: str
    title: str
    style_anchor: str = ""
    narrative_position: int = 1
    screens: list[DetailPagePlanScreen] = Field(default_factory=list)


class DetailPagePlanPayload(BaseModel):
    """详情图规划结果。"""

    template_name: str = "tea_tmall_premium_v1"
    category: str = "tea"
    platform: str = "tmall"
    style_preset: str = "tea_tmall_premium_light"
    global_style_anchor: str
    narrative: list[str] = Field(default_factory=list)
    total_screens: int
    total_pages: int
    pages: list[DetailPagePlanPage] = Field(default_factory=list)


class DetailPageCopyBlock(BaseModel):
    """详情图屏级文案结构。"""

    page_id: str
    screen_id: str
    headline: str
    subheadline: str = ""
    selling_points: list[str] = Field(default_factory=list)
    body_copy: str = ""
    parameter_copy: str = ""
    cta_copy: str = ""
    notes: str = ""


class DetailCopyPlanResult(BaseModel):
    """文案模型输出容器。"""

    items: list[DetailPageCopyBlock] = Field(default_factory=list)


class DetailPromptDraftItem(BaseModel):
    """Prompt 草案结构。"""

    page_id: str
    page_title: str = ""
    screen_themes: list[str] = Field(default_factory=list)
    layout_notes: list[str] = Field(default_factory=list)
    prompt: str = ""
    negative_prompt: str = ""
    reference_roles: list[DetailAssetRole] = Field(default_factory=list)


class DetailPromptPlanResult(BaseModel):
    """Prompt 规划模型输出容器。"""

    items: list[DetailPromptDraftItem] = Field(default_factory=list)


class DetailPagePromptPlanItem(BaseModel):
    """单张详情图最终渲染 prompt 规划。"""

    page_id: str
    page_title: str
    global_style_anchor: str
    screen_themes: list[str] = Field(default_factory=list)
    layout_notes: list[str] = Field(default_factory=list)
    prompt: str
    negative_prompt: str
    references: list[DetailPageAssetRef] = Field(default_factory=list)
    target_aspect_ratio: str = "1:3"
    target_width: int = 1080
    target_height: int = 3240


class DetailPageRenderResult(BaseModel):
    """单页渲染结果。"""

    render_id: str
    page_id: str
    page_title: str
    status: DetailRenderStatus
    file_name: str = ""
    relative_path: str = ""
    width: int | None = None
    height: int | None = None
    reference_roles: list[str] = Field(default_factory=list)
    provider_name: str = ""
    model_name: str = ""
    error_message: str = ""
    started_at: str = ""
    completed_at: str = ""


class DetailPageQCCheck(BaseModel):
    """规则型 QC 单项检查。"""

    check_id: str
    check_name: str
    page_id: str = "task"
    status: DetailQCStatus = "passed"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DetailPageQCPageSummary(BaseModel):
    """页面级 QC 摘要。"""

    page_id: str
    title: str = ""
    status: DetailQCStatus = "passed"
    issues: list[str] = Field(default_factory=list)
    reference_roles: list[str] = Field(default_factory=list)
    file_name: str = ""
    width: int | None = None
    height: int | None = None


class DetailPageQCSummary(BaseModel):
    """详情图任务级 QC 摘要。"""

    passed: bool = False
    review_required: bool = False
    warning_count: int = 0
    failed_count: int = 0
    issues: list[str] = Field(default_factory=list)
    checks: list[DetailPageQCCheck] = Field(default_factory=list)
    pages: list[DetailPageQCPageSummary] = Field(default_factory=list)


class DetailPageRuntimeImage(BaseModel):
    """详情图运行时结果图。"""

    image_id: str
    page_id: str
    title: str
    status: DetailRenderStatus
    file_name: str = ""
    image_url: str = ""
    width: int | None = None
    height: int | None = None
    reference_roles: list[str] = Field(default_factory=list)
    error_message: str = ""


class DetailPageRuntimePayload(BaseModel):
    """详情图任务运行时聚合。"""

    task_id: str
    status: DetailTaskStatus
    progress_percent: int
    current_stage: str
    current_stage_label: str
    message: str = ""
    error_message: str = ""
    generated_count: int = 0
    planned_count: int = 0
    plan: DetailPagePlanPayload | None = None
    copy_blocks: list[DetailPageCopyBlock] = Field(default_factory=list)
    prompt_plan: list[DetailPagePromptPlanItem] = Field(default_factory=list)
    qc_summary: DetailPageQCSummary = Field(default_factory=DetailPageQCSummary)
    images: list[DetailPageRuntimeImage] = Field(default_factory=list)
    export_zip_url: str = ""


class DetailPageJobSummary(BaseModel):
    """详情图任务摘要。"""

    task_id: str
    task_type: str = "detail_page_v2"
    status: DetailTaskStatus
    created_at: datetime
    updated_at: datetime
    title: str
    category: str = "tea"
    platform: str = "tmall"
    style_preset: str = "tea_tmall_premium_light"
    target_slice_count: int = 4


class DetailPageJobCreatePayload(BaseModel):
    """详情图任务创建参数。"""

    brand_name: str = ""
    product_name: str = ""
    tea_type: str = "乌龙茶"
    category: str = "tea"
    platform: str = "tmall"
    style_preset: str = "tea_tmall_premium_light"
    price_band: str = ""
    target_slice_count: int = Field(default=4, ge=4, le=6)
    image_size: str = "2K"
    main_image_task_id: str = ""
    selected_main_result_ids: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    specs: dict[str, str] = Field(default_factory=dict)
    style_notes: str = ""
    brew_suggestion: str = ""
    extra_requirements: str = ""
    prefer_main_result_first: bool = True


class DetailPageJobCreateResult(BaseModel):
    """详情图任务创建结果。"""

    task_id: str
    status: DetailTaskStatus
