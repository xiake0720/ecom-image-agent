"""详情页任务相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.engine.domain.usage import RuntimeUsageSummary


DetailAssetRole = Literal[
    "main_result",
    "packaging",
    "dry_leaf",
    "tea_soup",
    "leaf_bottom",
    "scene_ref",
    "bg_ref",
]

DetailPageRole = Literal[
    "hero_opening",
    "dry_leaf_evidence",
    "tea_soup_evidence",
    "parameter_and_closing",
    "leaf_bottom_process_evidence",
    "brand_trust",
    "gift_openbox_portable",
    "brewing_method_info",
    "scene_value_story",
    "packaging_structure_value",
    "package_closeup_evidence",
    "brand_closing",
]

DetailAssetStrategy = Literal[
    "anchor_required",
    "reference_preferred",
    "ai_supplement_allowed",
    "supplement_only",
]

DetailHeadlineLevel = Literal["primary"]
DetailTaskStatus = Literal["created", "running", "completed", "review_required", "failed"]
DetailRenderStatus = Literal["queued", "running", "completed", "failed"]
DetailQCStatus = Literal["passed", "warning", "failed"]
DetailVisualReviewStatus = Literal["passed", "warning", "failed"]
DetailRetryStrategy = Literal[
    "original_prompt_retry",
    "text_density_reduction",
    "reference_rebinding",
    "packaging_emphasis",
    "style_correction",
]


class DetailPageAssetRef(BaseModel):
    """详情页素材引用。"""

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
    """详情页单屏规划。"""

    screen_id: str
    theme: str
    goal: str
    screen_type: Literal["visual", "info"] = "visual"
    suggested_asset_roles: list[DetailAssetRole] = Field(default_factory=list)
    asset_strategy: DetailAssetStrategy = "reference_preferred"
    anchor_roles: list[DetailAssetRole] = Field(default_factory=list)
    supplement_roles: list[DetailAssetRole] = Field(default_factory=list)
    allow_generated_supporting_materials: bool = False
    material_focus: str = ""
    notes: list[str] = Field(default_factory=list)


class DetailPagePlanPage(BaseModel):
    """单张 3:4 详情图规划。"""

    page_id: str
    title: str
    page_role: DetailPageRole = "hero_opening"
    layout_mode: str = "single_screen_vertical_poster"
    primary_headline_screen_id: str = ""
    style_anchor: str = ""
    narrative_position: int = 1
    asset_strategy: DetailAssetStrategy = "reference_preferred"
    anchor_roles: list[DetailAssetRole] = Field(default_factory=list)
    supplement_roles: list[DetailAssetRole] = Field(default_factory=list)
    allow_generated_supporting_materials: bool = False
    review_focus: list[str] = Field(default_factory=list)
    screens: list[DetailPagePlanScreen] = Field(default_factory=list)


class DetailPagePlanPayload(BaseModel):
    """详情页规划结果。"""

    template_name: str = "tea_tmall_premium_v2"
    category: str = "tea"
    platform: str = "tmall"
    style_preset: str = "tea_tmall_premium_light"
    canvas_aspect_ratio: str = "3:4"
    screens_per_page: int = 1
    layout_mode: str = "single_screen_vertical_poster"
    global_style_anchor: str
    narrative: list[str] = Field(default_factory=list)
    total_screens: int
    total_pages: int
    pages: list[DetailPagePlanPage] = Field(default_factory=list)


class DetailPageCopyBlock(BaseModel):
    """详情页屏级文案结构。"""

    page_id: str
    screen_id: str
    headline_level: DetailHeadlineLevel = "primary"
    headline: str
    subheadline: str = ""
    selling_points: list[str] = Field(default_factory=list)
    body_copy: str = ""
    parameter_copy: str = ""
    cta_copy: str = ""
    notes: str = ""


class DetailCopyPlanResult(BaseModel):
    """文案规划输出容器。"""

    items: list[DetailPageCopyBlock] = Field(default_factory=list)


class DetailPromptDraftItem(BaseModel):
    """Prompt 草案结构。"""

    page_id: str
    page_title: str = ""
    page_role: DetailPageRole = "hero_opening"
    layout_mode: str = "single_screen_vertical_poster"
    primary_headline_screen_id: str = ""
    screen_themes: list[str] = Field(default_factory=list)
    layout_notes: list[str] = Field(default_factory=list)
    prompt: str = ""
    negative_prompt: str = ""
    reference_roles: list[DetailAssetRole] = Field(default_factory=list)


class DetailPromptPlanResult(BaseModel):
    """Prompt 规划输出容器。"""

    items: list[DetailPromptDraftItem] = Field(default_factory=list)


class DetailPagePromptPlanItem(BaseModel):
    """单张详情图最终渲染 Prompt 规划。"""

    page_id: str
    page_title: str
    page_role: DetailPageRole = "hero_opening"
    layout_mode: str = "single_screen_vertical_poster"
    primary_headline_screen_id: str = ""
    global_style_anchor: str
    screen_themes: list[str] = Field(default_factory=list)
    layout_notes: list[str] = Field(default_factory=list)
    title_copy: str = ""
    subtitle_copy: str = ""
    selling_points_for_render: list[str] = Field(default_factory=list)
    prompt: str
    negative_prompt: str
    references: list[DetailPageAssetRef] = Field(default_factory=list)
    asset_strategy: DetailAssetStrategy = "reference_preferred"
    allow_generated_supporting_materials: bool = False
    copy_strategy: str = "strong"
    text_density: str = "low"
    should_render_text: bool = True
    retryable: bool = True
    target_aspect_ratio: str = "3:4"
    target_width: int = 1536
    target_height: int = 2048


class DetailPageRenderResult(BaseModel):
    """单页渲染结果。"""

    render_id: str
    page_id: str
    page_title: str
    page_role: DetailPageRole = "hero_opening"
    status: DetailRenderStatus
    file_name: str = ""
    relative_path: str = ""
    width: int | None = None
    height: int | None = None
    reference_roles: list[str] = Field(default_factory=list)
    provider_name: str = ""
    model_name: str = ""
    error_message: str = ""
    retry_count: int = 0
    retry_strategies: list[DetailRetryStrategy] = Field(default_factory=list)
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
    page_role: DetailPageRole = "hero_opening"
    status: DetailQCStatus = "passed"
    issues: list[str] = Field(default_factory=list)
    reference_roles: list[str] = Field(default_factory=list)
    file_name: str = ""
    width: int | None = None
    height: int | None = None


class DetailPageQCSummary(BaseModel):
    """详情页任务级 QC 摘要。"""

    passed: bool = False
    review_required: bool = False
    warning_count: int = 0
    failed_count: int = 0
    issues: list[str] = Field(default_factory=list)
    checks: list[DetailPageQCCheck] = Field(default_factory=list)
    pages: list[DetailPageQCPageSummary] = Field(default_factory=list)


class DetailPageRuntimeImage(BaseModel):
    """详情页运行时结果图。"""

    image_id: str
    page_id: str
    title: str
    page_role: DetailPageRole = "hero_opening"
    status: DetailRenderStatus
    file_name: str = ""
    image_url: str = ""
    width: int | None = None
    height: int | None = None
    reference_roles: list[str] = Field(default_factory=list)
    error_message: str = ""
    retry_count: int = 0


class DetailPreflightRoleSummary(BaseModel):
    """单类素材的预检摘要。"""

    role: DetailAssetRole
    count: int = 0
    file_names: list[str] = Field(default_factory=list)


class DetailPreflightReport(BaseModel):
    """详情页输入预检。"""

    passed: bool = True
    warnings: list[str] = Field(default_factory=list)
    strong_anchor_roles: list[DetailAssetRole] = Field(
        default_factory=lambda: ["main_result", "packaging", "dry_leaf", "leaf_bottom"]
    )
    ai_supplement_roles: list[DetailAssetRole] = Field(
        default_factory=lambda: ["tea_soup", "scene_ref", "bg_ref"]
    )
    available_roles: list[DetailAssetRole] = Field(default_factory=list)
    missing_required_roles: list[DetailAssetRole] = Field(default_factory=list)
    missing_optional_roles: list[DetailAssetRole] = Field(default_factory=list)
    asset_summary: list[DetailPreflightRoleSummary] = Field(default_factory=list)
    recommended_page_roles: list[DetailPageRole] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DetailDirectorBrief(BaseModel):
    """面向规划与提示词的导演简报。"""

    template_name: str = "tea_tmall_premium_v2"
    category: str = "tea"
    platform: str = "tmall"
    style_preset: str = "tea_tmall_premium_light"
    global_style_anchor: str = ""
    page_rhythm: list[str] = Field(default_factory=list)
    anchor_priority: list[DetailAssetRole] = Field(default_factory=list)
    required_page_roles: list[DetailPageRole] = Field(default_factory=list)
    optional_page_roles: list[DetailPageRole] = Field(default_factory=list)
    ai_supplement_page_roles: list[DetailPageRole] = Field(default_factory=list)
    planning_notes: list[str] = Field(default_factory=list)
    material_notes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class DetailVisualReviewPage(BaseModel):
    """单页视觉审查结果。"""

    page_id: str
    page_role: DetailPageRole = "hero_opening"
    title: str = ""
    status: DetailVisualReviewStatus = "passed"
    findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class DetailVisualReviewReport(BaseModel):
    """生成结果视觉审查。"""

    overall_status: DetailVisualReviewStatus = "passed"
    summary: list[str] = Field(default_factory=list)
    pages: list[DetailVisualReviewPage] = Field(default_factory=list)


class DetailRetryDecisionItem(BaseModel):
    """单页重试决策。"""

    page_id: str
    page_role: DetailPageRole = "hero_opening"
    should_retry: bool = False
    reason: str = ""
    strategies: list[DetailRetryStrategy] = Field(default_factory=list)


class DetailRetryDecisionReport(BaseModel):
    """重试决策集合。"""

    pages: list[DetailRetryDecisionItem] = Field(default_factory=list)


class DetailPageRuntimePayload(BaseModel):
    """详情页任务运行时聚合。"""

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
    preflight_report: DetailPreflightReport | None = None
    director_brief: DetailDirectorBrief | None = None
    visual_review: DetailVisualReviewReport | None = None
    retry_decisions: DetailRetryDecisionReport | None = None
    usage_summary: RuntimeUsageSummary = Field(default_factory=RuntimeUsageSummary)
    qc_summary: DetailPageQCSummary = Field(default_factory=DetailPageQCSummary)
    images: list[DetailPageRuntimeImage] = Field(default_factory=list)
    export_zip_url: str = ""


class DetailPageJobSummary(BaseModel):
    """详情页任务摘要。"""

    task_id: str
    task_type: str = "detail_page_v2"
    status: DetailTaskStatus
    created_at: datetime
    updated_at: datetime
    title: str
    category: str = "tea"
    platform: str = "tmall"
    style_preset: str = "tea_tmall_premium_light"
    target_slice_count: int = 8


class DetailPageJobCreatePayload(BaseModel):
    """详情页任务创建参数。"""

    brand_name: str = ""
    product_name: str = ""
    tea_type: str = "乌龙茶"
    category: str = "tea"
    platform: str = "tmall"
    style_preset: str = "tea_tmall_premium_light"
    price_band: str = ""
    target_slice_count: int = Field(default=8, ge=1, le=12)
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
    """详情页任务创建结果。"""

    task_id: str
    status: DetailTaskStatus
