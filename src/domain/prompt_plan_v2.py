"""v2 最终生图 prompt plan contract。

文件位置：
- `src/domain/prompt_plan_v2.py`

核心职责：
- 定义 `prompt_refine_v2` 节点输出的数据结构
- 承载每张图最终可交给图片模型执行的 prompt、文案和版式提示

主要调用方：
- 后续 `src/workflows/nodes/prompt_refine_v2.py`

主要依赖方：
- 后续 `render_images` 的 v2 分支
- 结果页与调试链路

关键输入/输出：
- 输入来自 v2 prompt 精修节点
- 后续预期落盘为 `prompt_plan_v2.json`
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PromptShot(BaseModel):
    """单张图位的最终生图指令。"""

    shot_id: str
    shot_role: str
    render_prompt: str
    title_copy: str = Field(description="建议控制在 4-8 字，实际弹性约束由业务层负责。")
    subtitle_copy: str = Field(description="建议控制在 8-15 字，实际弹性约束由业务层负责。")
    layout_hint: str = Field(description="描述文案大致区域与留白策略，供图片模型和 overlay fallback 共同使用。")
    aspect_ratio: str = "1:1"
    image_size: str = "2K"


class PromptPlanV2(BaseModel):
    """整组图片的 v2 最终生图计划。"""

    shots: list[PromptShot] = Field(default_factory=list)
