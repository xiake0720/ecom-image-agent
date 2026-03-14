"""兼容渲染链路的图片 prompt contract。

文件位置：
- `src/domain/image_prompt_plan.py`

核心职责：
- 承载 `build_prompts` 生成的兼容型 prompt plan
- 兼容旧的单层 prompt 渲染链路，同时承载新的 image_edit 字段

主要调用方：
- `src/workflows/nodes/build_prompts.py`

主要依赖方：
- `render_images`
- 单张 shot 调试产物落盘

关键输入/输出：
- 输入来自结构化 spec 映射
- 输出到 `image_prompt_plan.json`
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ImagePrompt(BaseModel):
    """单张图片的兼容型 prompt 对象。

    为什么需要这个类：
    - 历史代码已经围绕 `ImagePromptPlan -> render_images` 组织
    - 当前升级到结构化视觉导演架构后，仍需要一个兼容桥接层
    """

    shot_id: str
    shot_type: str = ""
    prompt: str
    generation_mode: Literal["t2i", "image_edit"] = "t2i"
    edit_instruction: str = ""
    negative_prompt: list[str] = Field(default_factory=list)
    output_size: str
    preserve_rules: list[str] = Field(default_factory=list)
    keep_subject_rules: list[str] = Field(default_factory=list)
    editable_regions: list[str] = Field(default_factory=list)
    locked_regions: list[str] = Field(default_factory=list)
    background_direction: str = ""
    lighting_direction: str = ""
    text_safe_zone: str = ""
    subject_consistency_level: str = "high"
    text_space_hint: str = ""
    composition_notes: list[str] = Field(default_factory=list)
    style_notes: list[str] = Field(default_factory=list)

    @field_validator(
        "negative_prompt",
        "preserve_rules",
        "keep_subject_rules",
        "editable_regions",
        "locked_regions",
        "composition_notes",
        "style_notes",
        mode="before",
    )
    @classmethod
    def _normalize_list_fields(cls, value):
        """兼容模型/代码返回字符串或列表两种写法。"""
        if value is None:
            return []
        if isinstance(value, str):
            normalized = value.replace("\r", "\n")
            chunks = []
            for part in normalized.replace("，", ",").split("\n"):
                for inner in part.split(","):
                    item = inner.strip()
                    if item:
                        chunks.append(item)
            return chunks
        return value


class ImagePromptPlan(BaseModel):
    """整组图片的兼容型 prompt plan。"""

    generation_mode: Literal["t2i", "image_edit"] = "t2i"
    prompts: list[ImagePrompt] = Field(default_factory=list)
