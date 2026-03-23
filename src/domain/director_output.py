"""v2 电商导演输出 contract。

文件位置：
- `src/domain/director_output.py`

核心职责：
- 定义 `director_v2` 节点输出的数据结构
- 表达面向茶叶电商图组的导演级规划结果，而不是最终生图 prompt

主要调用方：
- 后续 `src/workflows/nodes/director_v2.py`

主要依赖方：
- 后续 `prompt_refine_v2`
- 结果页与落盘调试信息

关键输入/输出：
- 输入来自 v2 导演节点
- 后续预期落盘为 `director_output.json`
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

    @field_validator("selling_points", "compliance_notes", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value: object) -> object:
        """兼容模型输出字符串或列表两种写法。"""
        return _normalize_string_list(value)


class DirectorOutput(BaseModel):
    """整组图片的 v2 导演规划结果。"""

    product_summary: str
    category: str
    platform: str = "tmall"
    visual_style: str
    shots: list[DirectorShot] = Field(default_factory=list)
