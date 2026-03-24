"""v2 电商导演输出 contract。

文件位置：
- `src/domain/director_output.py`

核心职责：
- 定义 `director_v2` 节点输出的数据结构
- 承载整组图的导演级规划结果，而不是最终 render prompt
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


class DirectorShot(BaseModel):
    """单张图位的导演级规划结果。"""

    shot_id: str
    shot_role: str
    objective: str
    audience: str
    selling_points: list[str] = Field(default_factory=list)
    scene: str
    composition: str
    visual_focus: str
    copy_direction: str
    compliance_notes: list[str] = Field(default_factory=list)
    product_scale_guideline: str = ""
    subject_occupancy_ratio: float | None = None
    layout_hint: str = ""
    typography_hint: str = ""

    @field_validator("selling_points", "compliance_notes", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value: object) -> object:
        """兼容模型输出字符串或列表两种写法。"""

        return _normalize_string_list(value)

    @field_validator("subject_occupancy_ratio")
    @classmethod
    def _normalize_ratio(cls, value: float | None) -> float | None:
        """把主体占比限制在 0 到 1 之间。"""

        if value is None:
            return None
        return max(0.0, min(float(value), 1.0))


class DirectorOutput(BaseModel):
    """整组图片的 v2 导演规划结果。"""

    product_summary: str
    category: str
    platform: str = "tmall"
    visual_style: str
    shots: list[DirectorShot] = Field(default_factory=list)
