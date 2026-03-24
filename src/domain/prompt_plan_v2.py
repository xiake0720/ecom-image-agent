"""v2 最终生图 prompt plan contract。

文件位置：
- `src/domain/prompt_plan_v2.py`

核心职责：
- 定义 `prompt_refine_v2` 节点输出的数据结构
- 承载每张图最终可交给图片模型执行的 prompt、文案和版式提示
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _normalize_string_list(value: object) -> object:
    """兼容模型把列表字段写成字符串的情况。"""

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


class PromptShot(BaseModel):
    """单张图位的最终生图指令。"""

    shot_id: str
    shot_role: str
    render_prompt: str
    title_copy: str = Field(description="建议控制在 4-8 字，用户手动输入时按原文保留。")
    subtitle_copy: str = Field(description="建议控制在 8-15 字，用户手动输入时按原文保留。")
    selling_points_for_render: list[str] = Field(default_factory=list, description="最终需要融入画面的卖点文案。")
    layout_hint: str = Field(description="描述文字区域、留白策略与层级顺序。")
    typography_hint: str = Field(default="", description="描述标题、副标题、卖点的字号层级与风格。")
    copy_source: str = Field(default="auto", description="标记当前图位文案来自用户输入还是自动生成。")
    subject_occupancy_ratio: float | None = Field(default=None, description="主体预期占画面比例，hero 默认约 0.66。")
    aspect_ratio: str = "1:1"
    image_size: str = "2K"

    @field_validator("selling_points_for_render", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value: object) -> object:
        """兼容模型输出字符串或列表两种写法。"""

        return _normalize_string_list(value)


class PromptPlanV2(BaseModel):
    """整组图片的 v2 最终生图计划。"""

    shots: list[PromptShot] = Field(default_factory=list)
