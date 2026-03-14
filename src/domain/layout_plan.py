"""文字布局与安全区 contract。

文件位置：
- `src/domain/layout_plan.py`

核心职责：
- 定义 `generate_layout` 节点输出的数据结构
- 表达文字块坐标、文字安全区、安全区打分明细

主要调用方：
- `src/workflows/nodes/generate_layout.py`

主要依赖方：
- `build_prompts`
- `overlay_text`
- `run_qc`

关键输入/输出：
- 输入来自规则布局生成器
- 输出到 `layout_plan.json`
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TextSafeZone = Literal[
    "top_left",
    "top_right",
    "right_center",
    "left_center",
    "bottom_left",
    "bottom_right",
]


class LayoutBlock(BaseModel):
    """单个文字块的布局信息。"""

    kind: Literal["title", "subtitle", "bullets", "cta"]
    x: int
    y: int
    width: int
    height: int
    font_size: int = 64
    align: Literal["left", "center"] = "left"


class SafeZoneScore(BaseModel):
    """候选文字安全区的打分摘要。"""

    zone: TextSafeZone
    total_score: float
    distance_from_subject_score: float = 0.0
    background_uniformity_score: float = 0.0
    text_readability_score: float = 0.0
    label_overlap_penalty: float = 0.0
    composition_bias_score: float = 0.0
    rejection_reason: str = ""


class LayoutItem(BaseModel):
    """单张图的布局结果。"""

    shot_id: str
    canvas_width: int
    canvas_height: int
    text_safe_zone: TextSafeZone = "top_right"
    safe_zone_score_breakdown: list[SafeZoneScore] = Field(default_factory=list)
    rejected_zones: list[str] = Field(default_factory=list)
    selection_reason: str = ""
    blocks: list[LayoutBlock] = Field(default_factory=list)


class LayoutPlan(BaseModel):
    """整组图片的布局结果集合。"""

    items: list[LayoutItem] = Field(default_factory=list)
